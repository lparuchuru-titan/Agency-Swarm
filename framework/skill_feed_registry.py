"""Per-skill knowledge feed registry — each skill gets only its allowed sources."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config import GLOBAL_SFDC_NOTES_DIR, KB_DIR, TOPICS, ensure_dirs

# Restricted feeds per skill (open SFDC topics = keys in config.TOPICS)
SKILL_FEEDS: Dict[str, Dict[str, List[str]]] = {
    "advanced-salesforce-developer": {
        "open_topics": [
            "apex-design-patterns",
            "governor-limits",
            "security-sharing",
            "testing-deployment",
            "lwc-fundamentals",
            "cpq-fundamentals",
        ],
        "codebase": ["apex-services", "triggers-automation", "pantheon-cpq-backend", "security-fls"],
        "connected": [],
        "project": ["pantheon-2026-cpq", "nextgen-quoting-runtime"],
    },
    "codebase-explainer": {
        "open_topics": ["flows-automation"],
        "codebase": [
            "lwc-catalog",
            "pantheon-ui",
            "apex-services",
            "nextgen-quoting-runtime",
            "pantheon-cpq-backend",
            "aura-flexipages",
        ],
        "connected": ["confluence-index.md", "gdrive-gsheets-index.md"],
        "project": ["00-architecture-overview", "pantheon-2026-cpq"],
    },
    "jira-subtask-workflow": {
        "open_topics": [],
        "codebase": [],
        "connected": ["jira-index.md"],
        "project": [],
    },
    "playwright-e2e-validation": {
        "open_topics": ["lwc-fundamentals", "testing-deployment"],
        "codebase": ["lwc-catalog", "pantheon-ui", "aura-flexipages"],
        "connected": [],
        "project": ["pantheon-2026-cpq"],
    },
    "sfdc-cta-mentor": {
        "open_topics": [
            "integration-patterns",
            "governor-limits",
            "apex-design-patterns",
            "cpq-fundamentals",
            "security-sharing",
            "flows-automation",
        ],
        "codebase": ["nextgen-quoting-runtime", "pantheon-cpq-backend", "metadata-model"],
        "connected": [],
        "project": ["00-architecture-overview", "pantheon-2026-cpq", "data-model-and-automation"],
    },
    "sfdc-metadata-sync": {
        "open_topics": ["flows-automation", "testing-deployment", "security-sharing"],
        "codebase": ["metadata-model", "security-fls", "flows-declarative", "promotion-manifest"],
        "connected": [],
        "project": ["data-model-and-automation"],
    },
    "sfdc-promotion-workflow": {
        "open_topics": ["testing-deployment"],
        "codebase": ["promotion-manifest"],
        "connected": [],
        "project": [],
    },
    # ── New generic lifecycle agents ─────────────────────────────────────────
    "org-analyst": {
        "open_topics": [
            # Dedicated org-health topics
            "org-health-assessment",
            "security-vulnerability-scanning",
            "permission-model",
            # Supporting topics
            "security-sharing",
            "testing-deployment",
            "governor-limits",
            "flows-automation",
        ],
        "codebase": ["security-fls", "metadata-model", "apex-services"],
        "connected": [],
        "project": ["data-model-and-automation"],
    },
    "reverse-engineer": {
        "open_topics": [
            # Dedicated reverse-engineering topics
            "metadata-model",
            "data-modelling",
            # Supporting topics
            "flows-automation",
            "apex-design-patterns",
            "integration-patterns",
        ],
        "codebase": [
            "metadata-model",
            "apex-services",
            "lwc-catalog",
            "flows-declarative",
            "triggers-automation",
        ],
        "connected": ["confluence-index.md", "gdrive-gsheets-index.md"],
        "project": ["00-architecture-overview", "data-model-and-automation"],
    },
    "pr-reviewer": {
        "open_topics": [
            # Dedicated code-review topics
            "apex-code-review",
            "lwc-code-review",
            "flow-review",
            # Supporting topics
            "security-vulnerability-scanning",
            "security-sharing",
            "testing-deployment",
            "governor-limits",
        ],
        "codebase": ["apex-services", "triggers-automation", "security-fls"],
        "connected": [],
        "project": [],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def skill_names() -> List[str]:
    return sorted(SKILL_FEEDS.keys())


def feeds_for_skill(skill_name: str) -> Dict[str, List[str]]:
    return SKILL_FEEDS.get(skill_name, {"open_topics": [], "codebase": [], "connected": [], "project": []})


def all_open_topic_keys() -> List[str]:
    keys: Set[str] = set()
    for spec in SKILL_FEEDS.values():
        keys.update(spec.get("open_topics", []))
    return sorted(keys)


def kb_paths_for_skill(skill_name: str) -> List[str]:
    """Resolve filesystem paths this skill is allowed to read."""
    spec = feeds_for_skill(skill_name)
    paths: List[str] = []

    feed_doc = KB_DIR / "skills" / "feeds" / f"{skill_name}.md"
    if feed_doc.is_file():
        paths.append(str(feed_doc))

    for topic in spec.get("open_topics", []):
        paths.append(str(GLOBAL_SFDC_NOTES_DIR / f"{topic}.md"))
        paths.append(str(KB_DIR / "sfdc" / f"{topic}.md"))

    for key in spec.get("codebase", []):
        paths.append(str(KB_DIR / "codebase" / f"{key}.md"))

    for name in spec.get("connected", []):
        paths.append(str(KB_DIR / "connected" / name))

    for key in spec.get("project", []):
        paths.append(str(KB_DIR / "project" / f"{key}.md"))

    return list(dict.fromkeys(paths))


def _topic_meta(topic_key: str) -> Optional[Dict[str, Any]]:
    return next((t for t in TOPICS if t["key"] == topic_key), None)


def write_skill_feed_doc(skill_name: str) -> str:
    """Write per-skill OPEN-SOURCES index (restricted list + URLs)."""
    ensure_dirs()
    spec = feeds_for_skill(skill_name)
    feeds_dir = KB_DIR / "skills" / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    path = feeds_dir / f"{skill_name}.md"

    lines = [
        f"# Open & local feeds for `{skill_name}`",
        f"_Synced {_now()} · restricted feed map — only these sources apply to this skill_",
        "",
        "## Allowed open-source Salesforce docs",
    ]
    if spec.get("open_topics"):
        for key in spec["open_topics"]:
            topic = _topic_meta(key)
            note = GLOBAL_SFDC_NOTES_DIR / f"{key}.md"
            title = topic["title"] if topic else key
            lines.append(f"- **{title}** (`{key}`) → `{note}`")
            if topic:
                for url in topic.get("docs", []):
                    lines.append(f"  - {url}")
    else:
        lines.append("- _No public doc topics — uses connected/codebase/project only_")

    lines.extend(["", "## Codebase KB (project scan)"])
    for key in spec.get("codebase", []):
        lines.append(f"- `{KB_DIR / 'codebase' / f'{key}.md'}`")

    lines.extend(["", "## Connected indexes"])
    for name in spec.get("connected", []):
        lines.append(f"- `{KB_DIR / 'connected' / name}`")

    lines.extend(["", "## Project topics"])
    for key in spec.get("project", []):
        lines.append(f"- `{KB_DIR / 'project' / f'{key}.md'}`")

    lines.extend(
        [
            "",
            "## Refresh",
            "- Open docs: `sfdc-swarm skill-refresh --tier open_light`",
            "- Full manifest: `sfdc-swarm skill-refresh --tier manifest`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def refresh_skill_open_feeds(force: bool = False) -> Dict[str, Any]:
    """
    Fetch open-source Salesforce docs for the union of skill-specific topics,
    then write per-skill feed docs and return summary.
    """
    from open_resources import refresh_open_docs_static

    ensure_dirs()
    topic_keys = all_open_topic_keys()
    open_result = refresh_open_docs_static(topic_keys=topic_keys, force=force)

    feed_docs: List[Dict[str, Any]] = []
    for name in skill_names():
        doc_path = write_skill_feed_doc(name)
        spec = feeds_for_skill(name)
        feed_docs.append(
            {
                "skill": name,
                "open_topics": len(spec.get("open_topics", [])),
                "codebase": len(spec.get("codebase", [])),
                "connected": len(spec.get("connected", [])),
                "project": len(spec.get("project", [])),
                "feed_doc": doc_path,
            }
        )

    return {
        "tier": "skill_open_feeds",
        "token_cost": 0,
        "open_topics_refreshed": topic_keys,
        "open_fetch": open_result,
        "skills": feed_docs,
    }


def feed_registry_snapshot() -> Dict[str, Any]:
    """API snapshot for FleetView."""
    items = []
    for name in skill_names():
        spec = feeds_for_skill(name)
        paths = kb_paths_for_skill(name)
        present = sum(1 for p in paths if Path(p).is_file())
        items.append(
            {
                "skill": name,
                "open_topics": spec.get("open_topics", []),
                "codebase": spec.get("codebase", []),
                "connected": spec.get("connected", []),
                "project": spec.get("project", []),
                "path_count": len(paths),
                "paths_present": present,
                "feed_doc": str(KB_DIR / "skills" / "feeds" / f"{name}.md"),
            }
        )
    return {
        "timestamp": _now(),
        "skills": items,
        "union_open_topics": all_open_topic_keys(),
    }
