"""Orchestrate tiered skill refresh — cost-effective token usage."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import FLEET_DIR, ensure_dirs, init_runtime
from dev_swarm import record_schedule_run, start_dev_swarm
from open_resources import refresh_open_docs_static, stale_open_topic_keys
from skill_schedule_config import (
    DEEP_MAX_TOPICS_PER_RUN,
    DEEP_REFRESH_DAY_OF_MONTH,
    TIER_DESCRIPTIONS,
)

SCHEDULE_LOG = FLEET_DIR / "skill-refresh-log.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_run(entry: Dict[str, Any]) -> None:
    ensure_dirs()
    history: List[Dict[str, Any]] = []
    if SCHEDULE_LOG.exists():
        try:
            history = json.loads(SCHEDULE_LOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.insert(0, entry)
    SCHEDULE_LOG.write_text(json.dumps(history[:100], indent=2), encoding="utf-8")


def run_tier_codebase(force: bool = False, deep: bool = False) -> Dict[str, Any]:
    """Daily: stale-only codebase KB refresh (static scan; deep optional)."""
    result = start_dev_swarm(force=force, deep=deep and bool(__import__("os").environ.get("ANTHROPIC_API_KEY")))
    out = {
        "tier": "codebase",
        "token_cost": "high" if deep else 0,
        "run_id": result.get("run_id"),
        "teams": result.get("teams"),
        "results_count": len(result.get("results", [])),
    }
    if result.get("run_id"):
        record_schedule_run(result["run_id"], "complete", out["results_count"])
    return out


def run_tier_manifest() -> Dict[str, Any]:
    from skill_sync import refresh_skill_manifest

    return refresh_skill_manifest()


def run_tier_connected() -> Dict[str, Any]:
    from connected_resources import refresh_all_connected

    return refresh_all_connected()


def run_tier_open_light(force: bool = False) -> Dict[str, Any]:
    from skill_feed_registry import refresh_skill_open_feeds

    return refresh_skill_open_feeds(force=force)


def run_tier_open_deep(force: bool = False, max_topics: Optional[int] = None) -> Dict[str, Any]:
    """
    Monthly: LLM synthesis for stale open-doc topics only.
    Skips if no ANTHROPIC_API_KEY.
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "tier": "open_deep",
            "token_cost": 0,
            "skipped": True,
            "reason": "ANTHROPIC_API_KEY not set — use open_light tier instead",
        }

    limit = max_topics or DEEP_MAX_TOPICS_PER_RUN
    stale = stale_open_topic_keys()[:limit]
    if not stale and not force:
        return {"tier": "open_deep", "token_cost": 0, "skipped": True, "reason": "no stale open-doc topics"}

    from swarm import start_run

    result = start_run(topic_keys=stale or None, force=force)
    return {
        "tier": "open_deep",
        "token_cost": "high",
        "topics": stale,
        "run_id": result.get("run_id"),
        "results": result.get("results", []),
    }


def run_skill_refresh_all_projects(tier: str = "daily", force: bool = False) -> Dict[str, Any]:
    """Run skill refresh for every registered Salesforce project."""
    from project_registry import discover_sfdc_projects, list_projects, register_project

    from project_context import resolve_swarm_context

    outcomes: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for entry in list_projects():
        root = entry.get("projectRoot")
        if root and root not in seen:
            seen.add(root)
            try:
                ctx = resolve_swarm_context(start=Path(root))
                register_project(ctx)
                init_runtime(start=Path(root), force=True)
                outcomes.append({"project": ctx.get("projectName"), "org": ctx.get("targetOrgAlias"), **run_skill_refresh(tier, force)})
            except Exception as exc:  # noqa: BLE001
                outcomes.append({"project": root, "error": str(exc)})

    for root in discover_sfdc_projects():
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        try:
            ctx = resolve_swarm_context(start=root)
            register_project(ctx)
            init_runtime(start=root, force=True)
            outcomes.append(
                {"project": ctx.get("projectName"), "org": ctx.get("targetOrgAlias"), **run_skill_refresh(tier, force)}
            )
        except Exception as exc:  # noqa: BLE001
            outcomes.append({"project": str(root), "error": str(exc)})

    return {"ok": True, "tier": tier, "projects": len(outcomes), "outcomes": outcomes}


def run_skill_refresh(
    tier: str = "weekly",
    force: bool = False,
    deep: bool = False,
) -> Dict[str, Any]:
    """
    Run refresh tiers.

    tier values:
      - codebase | manifest | connected | open_light | open_deep
      - daily (codebase + manifest)
      - weekly (manifest + connected + open_light)
      - monthly (open_deep if day matches + stale only)
      - all_light (everything except LLM)
    """
    started = _now()
    outcomes: List[Dict[str, Any]] = []
    init_runtime(force=True)

    if tier == "codebase":
        outcomes.append(run_tier_codebase(force=force, deep=deep))
    elif tier == "manifest":
        outcomes.append(run_tier_manifest())
    elif tier == "connected":
        outcomes.append(run_tier_connected())
    elif tier == "open_light":
        outcomes.append(run_tier_open_light(force=force))
    elif tier == "open_deep":
        outcomes.append(run_tier_open_deep(force=force))
    elif tier == "daily":
        outcomes.append(run_tier_codebase(force=False, deep=False))
        outcomes.append(run_tier_manifest())
    elif tier == "weekly":
        outcomes.append(run_tier_manifest())
        outcomes.append(run_tier_connected())
        outcomes.append(run_tier_open_light(force=False))
    elif tier == "monthly":
        today = datetime.now(timezone.utc).day
        if today == DEEP_REFRESH_DAY_OF_MONTH or force:
            outcomes.append(run_tier_open_deep(force=force))
        else:
            outcomes.append(
                {
                    "tier": "open_deep",
                    "skipped": True,
                    "reason": f"deep refresh runs on day {DEEP_REFRESH_DAY_OF_MONTH} (today={today})",
                }
            )
    elif tier == "all_light":
        outcomes.append(run_tier_codebase(force=False, deep=False))
        outcomes.append(run_tier_manifest())
        outcomes.append(run_tier_connected())
        outcomes.append(run_tier_open_light(force=False))
    else:
        return {"ok": False, "error": f"unknown tier {tier}", "valid": list(TIER_DESCRIPTIONS.keys())}

    summary = {
        "ok": True,
        "started_at": started,
        "finished_at": _now(),
        "tier": tier,
        "outcomes": outcomes,
    }
    _log_run(summary)
    return summary


def schedule_info() -> Dict[str, Any]:
    """Extended schedule metadata for FleetView."""
    from skill_schedule_config import (
        CRON_CODEBASE_DAILY,
        CRON_CONNECTED,
        CRON_OPEN_DEEP,
        CRON_OPEN_LIGHT,
        CRON_SKILL_MANIFEST,
        DEEP_MAX_TOPICS_PER_RUN,
        DEEP_REFRESH_DAY_OF_MONTH,
        REFRESH_AFTER_DAYS,
    )

    last: Dict[str, Any] = {}
    if SCHEDULE_LOG.exists():
        try:
            hist = json.loads(SCHEDULE_LOG.read_text(encoding="utf-8"))
            if hist:
                last = hist[0]
        except json.JSONDecodeError:
            pass

    return {
        "tiers": TIER_DESCRIPTIONS,
        "refresh_after_days": REFRESH_AFTER_DAYS,
        "cron": {
            "codebase_daily": CRON_CODEBASE_DAILY,
            "skill_manifest": CRON_SKILL_MANIFEST,
            "connected_weekly": CRON_CONNECTED,
            "open_light_weekly": CRON_OPEN_LIGHT,
            "open_deep_monthly": CRON_OPEN_DEEP,
        },
        "deep_refresh_day_of_month": DEEP_REFRESH_DAY_OF_MONTH,
        "deep_max_topics_per_run": DEEP_MAX_TOPICS_PER_RUN,
        "last_skill_refresh": last,
        "log_path": str(SCHEDULE_LOG),
    }
