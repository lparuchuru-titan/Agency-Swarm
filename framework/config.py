"""Runtime configuration — resolves per Cursor project + Salesforce org."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Framework code location (this directory or ~/.cursor/sfdc-knowledge-swarm after install)
ROOT = Path(__file__).resolve().parent

_runtime: Optional[Dict[str, Any]] = None


def _swarm_home() -> Path:
    env = os.environ.get("SFDC_SWARM_HOME")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p.resolve()
    global_home = Path.home() / ".cursor" / "sfdc-knowledge-swarm"
    if global_home.is_dir() and ROOT != global_home:
        return global_home.resolve()
    return ROOT.resolve()


SWARM_HOME = _swarm_home()

SWARM_MODEL = os.environ.get("SWARM_MODEL", "claude-sonnet-4-20250514")
REFRESH_AFTER_DAYS = int(os.environ.get("REFRESH_AFTER_DAYS", "14"))
SWARM_CRON = os.environ.get("SWARM_CRON", "02:00")
MAX_PARALLEL = int(os.environ.get("SWARM_MAX_PARALLEL", "4"))
ORCHESTRATOR_STEP_DELAY_MS = int(os.environ.get("ORCHESTRATOR_STEP_DELAY_MS", "600"))
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")).expanduser()

# Legacy module-level paths — updated by init_runtime()
REPO_ROOT = ROOT.parent.parent
KB_DIR = ROOT / "knowledge-base"
GLOBAL_KB_DIR = SWARM_HOME / "knowledge-base"
SFDC_NOTES_DIR = KB_DIR / "sfdc"
GLOBAL_SFDC_NOTES_DIR = GLOBAL_KB_DIR / "sfdc"
CODEBASE_NOTES_DIR = KB_DIR / "codebase"
PROJECT_NOTES_DIR = KB_DIR / "project"
NEXTGEN2_NOTES_DIR = KB_DIR / "project"  # alias for legacy imports
FLEET_DIR = ROOT / ".fleet"
FLEET_STATE = FLEET_DIR / "state.json"
SCHEDULE_STATE = FLEET_DIR / "schedule.json"

# Mirror topics from .claude/workflows/sfdc-knowledge-swarm.js (shared open resources)
TOPICS: List[Dict[str, Any]] = [
    {
        "key": "apex-design-patterns",
        "title": "Apex Design Patterns & Trigger Frameworks",
        "focus": "Trigger handler frameworks, service/selector/domain layers, bulkification, recursion control.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers.htm",
        ],
    },
    {
        "key": "governor-limits",
        "title": "Governor Limits & Large Data Volumes",
        "focus": "Per-transaction limits, async Apex, LDV strategies, selective queries.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_async_overview.htm",
        ],
    },
    {
        "key": "lwc-fundamentals",
        "title": "Lightning Web Components",
        "focus": "LWC lifecycle, @wire vs imperative Apex, reactivity, events, performance.",
        "docs": [
            "https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks.html",
        ],
    },
    {
        "key": "security-sharing",
        "title": "Security, Sharing & FLS",
        "focus": "CRUD/FLS, WITH USER_MODE, stripInaccessible, sharing models, perm sets vs profiles.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_keywords_sharing.htm",
        ],
    },
    {
        "key": "integration-patterns",
        "title": "Integration Patterns",
        "focus": "REST/SOAP callouts, named credentials, Platform Events, CDC, Bulk API.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.integration_patterns_and_practices.meta/integration_patterns_and_practices/integ_pat_intro_overview.htm",
        ],
    },
    {
        "key": "cpq-fundamentals",
        "title": "Salesforce CPQ (SteelBrick) Fundamentals",
        "focus": "Quote/QuoteLine model, bundles, product rules, price rules, lookup data.",
        "docs": [
            "https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/quote-calculator-plugin.html",
        ],
    },
    {
        "key": "flows-automation",
        "title": "Flow & Declarative Automation",
        "focus": "Record-triggered flows, before/after-save, subflows, flow vs Apex.",
        "docs": [
            "https://help.salesforce.com/s/articleView?id=sf.flow.htm&type=5",
        ],
    },
    {
        "key": "testing-deployment",
        "title": "Testing & Deployment (SFDX/CI)",
        "focus": "Apex tests, TestDataFactory, sf CLI deploy/retrieve, CI/CD.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing.htm",
        ],
    },
]


def init_runtime(
    start: Optional[Path] = None,
    target_org_override: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Resolve project root, KB paths, and Salesforce org from cwd / env."""
    global _runtime, REPO_ROOT, KB_DIR, SFDC_NOTES_DIR, CODEBASE_NOTES_DIR
    global PROJECT_NOTES_DIR, NEXTGEN2_NOTES_DIR, FLEET_DIR, FLEET_STATE, SCHEDULE_STATE
    global GLOBAL_KB_DIR, GLOBAL_SFDC_NOTES_DIR

    if _runtime and not force:
        return _runtime

    env_root = os.environ.get("SFDC_SWARM_PROJECT_ROOT")
    if start is None and env_root:
        start = Path(env_root).expanduser()

    from project_context import resolve_swarm_context
    from project_registry import register_project

    ctx = resolve_swarm_context(start=start, target_org_override=target_org_override)
    register_project(ctx)

    REPO_ROOT = Path(ctx["repoRoot"])
    KB_DIR = Path(ctx["kbDir"])
    GLOBAL_KB_DIR = Path(ctx["globalKbDir"])
    SFDC_NOTES_DIR = KB_DIR / "sfdc"
    GLOBAL_SFDC_NOTES_DIR = GLOBAL_KB_DIR / "sfdc"
    CODEBASE_NOTES_DIR = KB_DIR / "codebase"
    PROJECT_NOTES_DIR = KB_DIR / "project"
    NEXTGEN2_NOTES_DIR = PROJECT_NOTES_DIR
    FLEET_DIR = Path(ctx["fleetDir"])
    FLEET_STATE = FLEET_DIR / "state.json"
    SCHEDULE_STATE = FLEET_DIR / "schedule.json"

    _runtime = ctx
    return ctx


def get_runtime() -> Dict[str, Any]:
    if _runtime is None:
        return init_runtime()
    return _runtime


def get_sf_context() -> Dict[str, Any]:
    return get_runtime()


def target_org_alias() -> Optional[str]:
    return get_runtime().get("targetOrgAlias")


def project_topics() -> List[Dict[str, Any]]:
    return get_runtime().get("projectTopics") or []


def ensure_dirs() -> None:
    init_runtime()
    GLOBAL_SFDC_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    SFDC_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    (KB_DIR / "connected").mkdir(parents=True, exist_ok=True)
    CODEBASE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    FLEET_DIR.mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "docs" / "swarm-deliveries").mkdir(parents=True, exist_ok=True)


# Initialize on import when inside a Salesforce project or env is set
try:
    init_runtime()
except Exception:  # noqa: BLE001 — allow import outside SFDC project (e.g. install script)
    pass
