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
PROJECT_NOTES_DIR_ALIAS = KB_DIR / "project"  # legacy alias kept for older imports
FLEET_DIR = ROOT / ".fleet"
FLEET_STATE = FLEET_DIR / "state.json"
SCHEDULE_STATE = FLEET_DIR / "schedule.json"

# Mirror topics from .claude/workflows/sfdc-knowledge-swarm.js (shared open resources)
TOPICS: List[Dict[str, Any]] = [
    # ── Core Apex & development ───────────────────────────────────────────────
    {
        "key": "apex-design-patterns",
        "title": "Apex Design Patterns & Trigger Frameworks",
        "focus": "Trigger handler frameworks, FFLIB enterprise patterns, service/selector/domain layers, bulkification, recursion control.",
        "docs": [
            # Official Salesforce docs
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_triggers_bestpract.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_best_practices.htm",
            # Open-source framework READMEs (raw GitHub — always fetchable)
            "https://raw.githubusercontent.com/apex-enterprise-patterns/fflib-apex-common/master/README.md",
            "https://raw.githubusercontent.com/kevinohara80/sfdc-trigger-framework/master/README.md",
            "https://raw.githubusercontent.com/mitchspano/apex-trigger-actions-framework/main/README.md",
            "https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/README.md",
            # Architect hub
            "https://architect.salesforce.com/design/decision-guides/build-vs-buy",
            # Community blog
            "https://developer.salesforce.com/blogs/2018/06/trigger-frameworks-and-apex-trigger-best-practices",
        ],
    },
    {
        "key": "governor-limits",
        "title": "Governor Limits & Large Data Volumes",
        "focus": "Per-transaction limits, async Apex (Batch/Queueable/Future), LDV strategies, selective queries, skinny tables.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_async_overview.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/langCon_apex_loops.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_batch_interface.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_queueing_jobs.htm",
            "https://architect.salesforce.com/fundamentals/large-data-volumes",
            # GitHub: LDV and performance recipes
            "https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Async%20Apex%20Recipes/QueueableRecipes.cls",
        ],
    },
    {
        "key": "lwc-fundamentals",
        "title": "Lightning Web Components",
        "focus": "LWC lifecycle, @wire vs imperative Apex, reactivity, events, performance, accessibility, Jest testing.",
        "docs": [
            "https://developer.salesforce.com/docs/platform/lwc/guide/create-lifecycle-hooks.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/data-wire-service-about.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/events-create-dispatch.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/javascript-intro.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/accessibility.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/unit-testing-using-jest-introduction.html",
            # Trailhead app recipes (raw GitHub)
            "https://raw.githubusercontent.com/trailheadapps/lwc-recipes/main/README.md",
            # Community patterns
            "https://developer.salesforce.com/blogs/2020/01/lightning-web-components-best-practices",
        ],
    },
    {
        "key": "security-sharing",
        "title": "Security, Sharing & FLS",
        "focus": "CRUD/FLS, WITH USER_MODE, stripInaccessible, sharing models, perm sets vs profiles, without sharing antipatterns.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_keywords_sharing.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_security_fls.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.securityImplGuide.meta/securityImplGuide/security_intro.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.securityImplGuide.meta/securityImplGuide/security_sharing_overview.htm",
            "https://architect.salesforce.com/fundamentals/salesforce-security-model",
            # Community: common FLS mistakes and fixes
            "https://developer.salesforce.com/blogs/2022/01/protecting-your-data-with-security-and-field-level-security",
            # GitHub: security recipes
            "https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Security%20Recipes/CanTheUserRecipes.cls",
        ],
    },
    {
        "key": "integration-patterns",
        "title": "Integration Patterns",
        "focus": "REST/SOAP callouts, named credentials, Platform Events, CDC, Bulk API, MuleSoft, event-driven architecture.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.integration_patterns_and_practices.meta/integration_patterns_and_practices/integ_pat_intro_overview.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.platform_events.meta/platform_events/platform_events_intro.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.change_data_capture.meta/change_data_capture/cdc_intro.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.api_asynch.meta/api_asynch/asynch_api_intro.htm",
            "https://architect.salesforce.com/decision-guides/integrate-salesforce",
            "https://architect.salesforce.com/fundamentals/event-driven-architecture",
            # GitHub: integration recipes
            "https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Integration%20Recipes/RestClient.cls",
            # Named Credentials best practices
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_named_credentials.htm",
        ],
    },
    {
        "key": "cpq-fundamentals",
        "title": "Salesforce CPQ (SteelBrick) Fundamentals",
        "focus": "Quote/QuoteLine model, bundles, product rules, price rules, lookup data.",
        "docs": [
            "https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/quote-calculator-plugin.html",
            "https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/pricing_waterfall.html",
            "https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/product_rules.html",
            "https://developer.salesforce.com/docs/revenue/cpq-developer-guide/guide/bundle_configuration.html",
        ],
    },
    {
        "key": "flows-automation",
        "title": "Flow & Declarative Automation",
        "focus": "Record-triggered flows, before/after-save, subflows, flow vs Apex.",
        "docs": [
            "https://help.salesforce.com/s/articleView?id=sf.flow.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.flow_ref_elements_actions_apex.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.flow_build_best_practices.htm&type=5",
            "https://architect.salesforce.com/decision-guides/automate-salesforce",
            "https://developer.salesforce.com/blogs/2021/09/best-practices-for-flow-in-salesforce",
        ],
    },
    {
        "key": "testing-deployment",
        "title": "Testing & Deployment (SFDX/CI)",
        "focus": "Apex tests, TestDataFactory, mock frameworks, sf CLI deploy/retrieve, CI/CD, GitHub Actions for Salesforce.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing_best_practices.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing_stub_api.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_intro.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_ci.htm",
            "https://developer.salesforce.com/tools/salesforcecli/sf-deploy-retrieve",
            # GitHub Actions for Salesforce DX
            "https://raw.githubusercontent.com/forcedotcom/salesforcedx-actions/main/README.md",
            # Community: CI/CD patterns
            "https://developer.salesforce.com/blogs/2021/07/how-to-implement-ci-cd-with-salesforce",
        ],
    },
    # ── New: CTA / Architect level ────────────────────────────────────────────
    {
        "key": "well-architected",
        "title": "Salesforce Well-Architected Framework",
        "focus": "Trusted, easy, adaptable pillars. Architecture principles, decision guides, trade-off analysis, CTA thinking.",
        "docs": [
            "https://architect.salesforce.com/well-architected/overview",
            "https://architect.salesforce.com/well-architected/trusted/compliant",
            "https://architect.salesforce.com/well-architected/easy/scalable",
            "https://architect.salesforce.com/well-architected/efficient",
            "https://architect.salesforce.com/fundamentals",
            "https://architect.salesforce.com/design/decision-guides",
            "https://architect.salesforce.com/decision-guides/build-vs-buy",
            "https://architect.salesforce.com/decision-guides/choose-between-aura-and-lwc",
        ],
    },
    {
        "key": "platform-events-cdc",
        "title": "Platform Events, Change Data Capture & Event-Driven Architecture",
        "focus": "Pub/Sub API, Platform Events, CDC, event replay, EDA patterns, decoupled integrations.",
        "docs": [
            # GitHub raw: event-driven recipes and patterns (always fetchable)
            "https://raw.githubusercontent.com/trailheadapps/event-driven-recipes/main/README.md",
            "https://raw.githubusercontent.com/trailheadapps/apex-recipes/main/force-app/main/default/classes/Platform%20Event%20Recipes/PlatformEventPublishCallback.cls",
            # Salesforce REST API for platform events (fetchable static docs)
            "https://raw.githubusercontent.com/salesforce/salesforcedx-vscode/develop/packages/salesforcedx-vscode-apex/README.md",
            # EDA pattern guide (architect hub — plain HTML)
            "https://architect.salesforce.com/fundamentals/event-driven-architecture",
        ],
    },
    {
        "key": "salesforce-releases",
        "title": "Salesforce Release Notes & New Features",
        "focus": "Latest platform changes, new APIs, deprecated features, migration guidance across Spring/Summer/Winter releases.",
        "docs": [
            # GitHub CHANGELOGs (raw, always fetchable)
            "https://raw.githubusercontent.com/salesforce/salesforcedx-vscode/develop/CHANGELOG.md",
            "https://raw.githubusercontent.com/forcedotcom/cli/main/CHANGELOG.md",
            "https://raw.githubusercontent.com/salesforcecli/plugin-deploy-retrieve/main/CHANGELOG.md",
            # Salesforce DX release notes (GitHub raw)
            "https://raw.githubusercontent.com/forcedotcom/salesforcedx-apex/main/CHANGELOG.md",
        ],
    },
    # ── New topics: Org Analyst ────────────────────────────────────────────────
    {
        "key": "org-health-assessment",
        "title": "Salesforce Org Health Assessment & Technical Debt",
        "focus": "Measuring org health: coverage, dead code, deprecated API, duplicate automation, technical debt scoring.",
        "docs": [
            "https://architect.salesforce.com/well-architected/overview",
            "https://architect.salesforce.com/well-architected/reliable/resilient",
            "https://architect.salesforce.com/well-architected/efficient",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_testing_code_coverage.htm",
            "https://help.salesforce.com/s/articleView?id=sf.code_builder_overview.htm&type=5",
        ],
    },
    {
        "key": "security-vulnerability-scanning",
        "title": "Salesforce Security Vulnerabilities & Static Analysis",
        "focus": "PMD rules for Apex, SOQL injection, XSS in LWC, over-permissioned profiles, guest user exposure, ISV security review.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.securityImplGuide.meta/securityImplGuide/security_apex_soql_injection.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.securityImplGuide.meta/securityImplGuide/security_apex_cross_site.htm",
            "https://developer.salesforce.com/tools/vscode/en/codeanalyzerplugin/gettingstarted",
            "https://developer.salesforce.com/docs/atlas.en-us.packagingGuide.meta/packagingGuide/security_review_guidelines.htm",
            "https://pmd.github.io/pmd/pmd_rules_apex_security.html",
            "https://pmd.github.io/pmd/pmd_rules_apex_bestpractices.html",
            "https://pmd.github.io/pmd/pmd_rules_apex_performance.html",
        ],
    },
    {
        "key": "permission-model",
        "title": "Salesforce Permission Model & Access Control",
        "focus": "Permission sets vs profiles, muting sets, permission set groups, OWD, sharing rules, role hierarchy.",
        "docs": [
            "https://help.salesforce.com/s/articleView?id=sf.perm_sets_overview.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.perm_set_groups.htm&type=5",
            "https://developer.salesforce.com/docs/atlas.en-us.securityImplGuide.meta/securityImplGuide/security_data_access.htm",
            "https://architect.salesforce.com/fundamentals/salesforce-security-model",
            "https://help.salesforce.com/s/articleView?id=sf.security_sharing_owd_about.htm&type=5",
        ],
    },
    # ── New topics: Reverse Engineer ──────────────────────────────────────────
    {
        "key": "metadata-model",
        "title": "Salesforce Metadata API & Object Model",
        "focus": "Metadata types, sfdx-project.json, package.xml, custom objects, fields, relationships, retrieve/deploy.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_intro.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_field_types.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_customobject.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_source_file_format.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_list.htm",
        ],
    },
    {
        "key": "data-modelling",
        "title": "Salesforce Data Modelling & Schema Design",
        "focus": "Object relationships, junction objects, external IDs, rollup summaries, schema best practices, data dictionary patterns.",
        "docs": [
            "https://architect.salesforce.com/fundamentals/data-modeling",
            "https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/relationships_and_custom_objects.htm",
            "https://help.salesforce.com/s/articleView?id=sf.relationships_considerations.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.customize_objectcreating.htm&type=5",
            "https://architect.salesforce.com/decision-guides/build-vs-buy",
        ],
    },
    # ── New topics: PR Reviewer ────────────────────────────────────────────────
    {
        "key": "apex-code-review",
        "title": "Apex Code Review Checklist & Best Practices",
        "focus": "Code review criteria: bulkification, SOQL/DML in loops, handler pattern, null safety, test quality, hardcoded IDs.",
        "docs": [
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_best_practices.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_bulk_process.htm",
            "https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_dml_exceptions.htm",
            "https://pmd.github.io/pmd/pmd_rules_apex.html",
            "https://developer.salesforce.com/blogs/2022/01/from-good-to-great-writing-high-quality-apex-code",
        ],
    },
    {
        "key": "lwc-code-review",
        "title": "LWC Code Review & Accessibility",
        "focus": "LWC review criteria: error handling, reactivity, accessibility, no DOM mutation, no hardcoded values.",
        "docs": [
            "https://developer.salesforce.com/docs/platform/lwc/guide/accessibility.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/js-best-practices.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/debug-intro.html",
            "https://developer.salesforce.com/docs/platform/lwc/guide/security-lwc.html",
        ],
    },
    {
        "key": "flow-review",
        "title": "Salesforce Flow Code Review & Best Practices",
        "focus": "Flow review: null-safety on Get Records, fault paths, bulk-safety, no duplicate automation, before vs after save.",
        "docs": [
            "https://help.salesforce.com/s/articleView?id=sf.flow_build_best_practices.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.flow_ref_elements_data_get.htm&type=5",
            "https://help.salesforce.com/s/articleView?id=sf.flow_ref_fault.htm&type=5",
            "https://developer.salesforce.com/blogs/2021/05/flow-best-practices-and-considerations",
            "https://architect.salesforce.com/decision-guides/automate-salesforce",
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
    global PROJECT_NOTES_DIR, PROJECT_NOTES_DIR_ALIAS, FLEET_DIR, FLEET_STATE, SCHEDULE_STATE
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
    PROJECT_NOTES_DIR_ALIAS = PROJECT_NOTES_DIR
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
