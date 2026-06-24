"""Sync skill manifests with knowledge-base paths — no LLM."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from agents_registry import AGENTS
from config import CLAUDE_HOME, KB_DIR, REPO_ROOT, ensure_dirs
from skill_feed_registry import kb_paths_for_skill, skill_names
from skill_schedule_config import SKILLS_MANIFEST_NAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skill_dirs() -> List[Path]:
    dirs: List[Path] = []
    for root in [REPO_ROOT / ".cursor" / "skills", Path.home() / ".cursor" / "skills", CLAUDE_HOME / "skills"]:
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.is_dir() and (child / "SKILL.md").is_file():
                    dirs.append(child)
    return dirs


def _kb_paths_for_skill(skill_name: str) -> List[str]:
    return kb_paths_for_skill(skill_name)


def refresh_skill_manifest() -> Dict[str, Any]:
    """Write central manifest + per-skill KNOWLEDGE-LINKS.md (tiny pointer files)."""
    ensure_dirs()
    skills_dir = KB_DIR / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_names_set = set(skill_names())
    for s in _skill_dirs():
        skill_names_set.add(s.name)
    for agent in AGENTS:
        for s in agent.get("skills", []):
            skill_names_set.add(s)
    skill_names_list = sorted(skill_names_set)

    rows: List[Dict[str, Any]] = []
    for name in skill_names_list:
        kb_paths = _kb_paths_for_skill(name)
        exists = sum(1 for p in kb_paths if not p.startswith("skill:") and Path(p).exists())
        rows.append({"skill": name, "kb_links": len(kb_paths), "kb_present": exists})

        link_body = [
            f"# Knowledge links for `{name}`",
            f"_Synced {_now()} · restricted feeds only — see also skills/feeds/{name}.md_",
            "",
        ]
        for p in kb_paths[:24]:
            link_body.append(f"- `{p}`")
        link_body.append("")
        link_body.append("Refresh: `sfdc-swarm skill-refresh --tier weekly`")

        for root in [REPO_ROOT / ".cursor" / "skills" / name, Path.home() / ".cursor" / "skills" / name]:
            if root.is_dir():
                (root / "KNOWLEDGE-LINKS.md").write_text("\n".join(link_body) + "\n", encoding="utf-8")

    manifest_lines = [
        "# Agent skills — knowledge manifest",
        f"_Synced {_now()} · per-skill restricted feeds (open + codebase + connected + project)_",
        "",
        "| Skill | KB links | On disk | Open topics |",
        "| --- | --- | --- | --- |",
    ]
    from skill_feed_registry import feeds_for_skill

    for row in rows:
        spec = feeds_for_skill(row["skill"])
        open_ct = len(spec.get("open_topics", []))
        manifest_lines.append(
            f"| `{row['skill']}` | {row['kb_links']} | {row['kb_present']} | {open_ct} |"
        )

    manifest_lines.extend(
        [
            "",
            "## Per-skill feed maps",
            f"- Directory: `{KB_DIR / 'skills' / 'feeds'}/`",
            "",
            "## Schedules (token tiers)",
            "- **codebase** daily — static scan",
            "- **connected** weekly — Jira/Confluence/Drive indexes (skill-restricted)",
            "- **open_light** weekly — public Salesforce docs (skill-restricted topics)",
            "- **open_deep** monthly — stale-only LLM synthesis",
            "",
            "## Connected indexes",
            f"- `{KB_DIR / 'connected' / 'INDEX.md'}`",
        ]
    )

    manifest_path = skills_dir / SKILLS_MANIFEST_NAME
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    state_path = skills_dir / "sync-state.json"
    state_path.write_text(
        json.dumps({"last_sync": _now(), "skills": len(rows), "manifest": str(manifest_path)}, indent=2),
        encoding="utf-8",
    )

    return {
        "tier": "manifest",
        "token_cost": 0,
        "skills": len(rows),
        "manifest_path": str(manifest_path),
    }
