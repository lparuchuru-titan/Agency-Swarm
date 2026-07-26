"""Tiered skill refresh schedule — token-cost defaults."""
from __future__ import annotations

import os

# Stale detection (shared with codebase + open docs)
REFRESH_AFTER_DAYS = int(os.environ.get("REFRESH_AFTER_DAYS", "14"))

# Cron times (24h HH:MM) — override via env for launchd alignment
CRON_CODEBASE_DAILY = os.environ.get("SKILL_CRON_CODEBASE", "02:00")
CRON_SKILL_MANIFEST = os.environ.get("SKILL_CRON_MANIFEST", "02:30")
CRON_CONNECTED = os.environ.get("SKILL_CRON_CONNECTED", "03:00")
CRON_OPEN_LIGHT = os.environ.get("SKILL_CRON_OPEN_LIGHT", "03:15")
CRON_OPEN_DEEP = os.environ.get("SKILL_CRON_OPEN_DEEP", "04:00")

# Deep (LLM) refresh: monthly day-of-month (1–28) and max topics per run
DEEP_REFRESH_DAY_OF_MONTH = int(os.environ.get("SKILL_DEEP_DAY", "1"))
DEEP_MAX_TOPICS_PER_RUN = int(os.environ.get("SKILL_DEEP_MAX_TOPICS", "2"))

# Cap raw excerpt size in static open-doc notes (chars) — keeps files small for agent context
OPEN_DOC_STATIC_MAX_CHARS = int(os.environ.get("SKILL_OPEN_STATIC_MAX", "6000"))

# Connected resource catalogs (titles/links only — no full page bodies)
CONNECTED_MAX_ITEMS = int(os.environ.get("SKILL_CONNECTED_MAX_ITEMS", "40"))

# Jira project keys to index when credentials are set
JIRA_PROJECT_KEYS = [k for k in os.environ.get("JIRA_PROJECT_KEYS", "").split(",") if k]

# Paths
CONNECTED_KB_DIR_NAME = "connected"
SKILLS_MANIFEST_NAME = "MANIFEST.md"

TIER_DESCRIPTIONS = {
    "codebase": "Daily · static force-app scan · 0 tokens",
    "manifest": "Daily/weekly · skill ↔ KB link manifest · 0 tokens",
    "connected": "Weekly · Jira/Confluence/Drive/Sheets indexes · 0 tokens (REST) or MCP checklist",
    "open_light": "Weekly · public Salesforce doc static fetch · 0 tokens",
    "open_deep": "Monthly · stale-only LLM synthesis · uses API tokens",
}
