"""
LangGraph team nodes — execute agent work via Cursor SDK (Node.js runner).

Each node invokes cursor_agent_runner.js with the agent's skill + task prompt.
Cursor manages the LLM choice; agents run in the repo context (local runtime).

Requires: CURSOR_API_KEY env var (cursor.com/dashboard/integrations)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents_registry import AGENTS, agents_for_team
from config import FLEET_DIR, GLOBAL_SFDC_NOTES_DIR, KB_DIR, REPO_ROOT, get_runtime
from fleet_hooks import append_activity, mark_team_phase, update_agent

FLEET_RUNS = FLEET_DIR / "runs"
_NODE = (
    shutil.which("node")
    or os.environ.get("NODE_PATH", "")
    or "node"
)
_RUNNER = str(Path(__file__).parent / "cursor_agent_runner.js")
_MODEL = os.environ.get("CURSOR_AGENT_MODEL", "auto")
_SF = shutil.which("sf") or "sf"


# ── helpers ────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(run_id: str) -> Path:
    d = FLEET_RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_artifact(run_id: str, name: str, content: str) -> str:
    path = _run_dir(run_id) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _agents_for_team_ids(team_id: str, assigned: List[str]) -> List[Dict[str, Any]]:
    team_agents = agents_for_team(team_id)
    if not assigned:
        return team_agents
    ids = set(assigned)
    picked = [a for a in AGENTS if a["id"] in ids and a.get("team") == team_id]
    return picked or team_agents


def _read_skill(skill_name: str, max_chars: int = 3500) -> str:
    for base in [
        Path.home() / ".cursor" / "skills",
        Path.home() / ".claude" / "skills",
        REPO_ROOT / ".cursor" / "skills",
    ]:
        path = base / skill_name / "SKILL.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")[:max_chars]
    return f"You are an expert Salesforce {skill_name.replace('-', ' ')} agent."


def _read_kb(topics: List[str], max_chars: int = 4000) -> str:
    chunks: List[str] = []
    for topic in topics[:5]:
        key = topic.split("/")[-1]
        for base in [GLOBAL_SFDC_NOTES_DIR, KB_DIR / "sfdc", KB_DIR / "connected"]:
            path = base / f"{key}.md"
            if path.is_file():
                chunks.append(f"### {key}\n{path.read_text(encoding='utf-8')[:1500]}")
                break
    return "\n\n".join(chunks)[:max_chars]


def _accumulate_usage(run_id: str, agent_id: str, usage: Dict[str, Any], cost_usd: float) -> None:
    """Add agent usage to the run-level totals file."""
    totals_path = _run_dir(run_id) / "USAGE.json"
    try:
        data = json.loads(totals_path.read_text(encoding="utf-8")) if totals_path.exists() else {"agents": [], "totals": {}}
    except Exception:  # noqa: BLE001
        data = {"agents": [], "totals": {}}

    data["agents"].append({
        "agent_id": agent_id,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost_usd": round(cost_usd, 6),
    })
    # Recompute totals
    t = {
        "input_tokens": sum(a["input_tokens"] for a in data["agents"]),
        "output_tokens": sum(a["output_tokens"] for a in data["agents"]),
        "cache_read_tokens": sum(a["cache_read_tokens"] for a in data["agents"]),
        "total_tokens": sum(a["total_tokens"] for a in data["agents"]),
        "cost_usd": round(sum(a["cost_usd"] for a in data["agents"]), 6),
        "agent_count": len(data["agents"]),
    }
    data["totals"] = t
    totals_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _retrieve_metadata(
    org: str, metadata_specs: List[str], label: str,
    run_id: str, agent_id: str, max_files: int = 10, max_chars_per_file: int = 2500,
) -> str:
    """Retrieve actual metadata source from the org and return file contents as context."""
    if not shutil.which("sf"):
        return f"_{label}: sf CLI not found_"
    append_activity(run_id, agent_id, f"📥 Retrieving {label} from {org}…")
    meta_args: List[str] = []
    for spec in metadata_specs:
        meta_args += ["--metadata", spec]
    try:
        r = subprocess.run(
            [_SF, "project", "retrieve", "start", "--target-org", org, "--json"] + meta_args,
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(r.stdout or "{}")
        files_retrieved = data.get("result", {}).get("files", []) or []
        if not files_retrieved:
            return f"_{label}: nothing retrieved_"
    except Exception as exc:  # noqa: BLE001
        return f"_{label}: retrieve failed — {exc}_"

    sections = [f"## Retrieved: {label} ({len(files_retrieved)} files)"]
    read_count = 0
    for fi in files_retrieved[:max_files]:
        fp = Path(fi.get("filePath", ""))
        if not fp.is_absolute():
            fp = REPO_ROOT / fp
        if not fp.is_file() or fp.suffix in (".xml",) and not fi.get("type","").startswith("Custom"):
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")[:max_chars_per_file]
            sections.append(f"### {fp.name}\n```\n{content}\n```")
            read_count += 1
        except Exception:  # noqa: BLE001
            pass
    if read_count == 0:
        names = [f.get("filePath","?") for f in files_retrieved[:15]]
        sections.append("Files retrieved:\n" + "\n".join(f"- {n}" for n in names))
    append_activity(run_id, agent_id, f"  ✅ Read {read_count} files from org")
    return "\n\n".join(sections)


# ── Full org baseline scan — always runs regardless of domain ──────────────
# These queries run on EVERY research request to give the agent a complete
# picture of the org before it does any domain-specific deep dive.
_BASELINE_SOQL: List[Dict[str, str]] = [
    # Objects & schema
    {"label": "Custom Objects", "q": "SELECT Label, QualifiedApiName, KeyPrefix, Description FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' ORDER BY QualifiedApiName LIMIT 80"},
    {"label": "Custom Metadata Types", "q": "SELECT Label, QualifiedApiName FROM EntityDefinition WHERE IsCustomSetting = false AND IsCustomizable = true AND QualifiedApiName LIKE '%__mdt' ORDER BY QualifiedApiName LIMIT 30"},
    {"label": "Custom Settings", "q": "SELECT Label, QualifiedApiName FROM EntityDefinition WHERE IsCustomSetting = true ORDER BY QualifiedApiName LIMIT 20"},
    # Apex
    {"label": "Apex Classes (by size)", "q": "SELECT Name, ApiVersion, LengthWithoutComments, Status FROM ApexClass WHERE NamespacePrefix = null ORDER BY LengthWithoutComments DESC LIMIT 50"},
    {"label": "Apex Triggers", "q": "SELECT Name, TableEnumOrId, Status, ApiVersion FROM ApexTrigger WHERE NamespacePrefix = null ORDER BY TableEnumOrId LIMIT 40"},
    {"label": "Test Coverage Summary", "q": "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered FROM ApexCodeCoverageAggregate WHERE NumLinesUncovered > 0 ORDER BY NumLinesUncovered DESC LIMIT 20"},
    # Automation
    {"label": "Active Flows (all types)", "q": "SELECT MasterLabel, ProcessType, TriggerType, ApiVersion, Status FROM Flow WHERE Status = 'Active' ORDER BY ProcessType, MasterLabel LIMIT 60"},
    {"label": "Validation Rules", "q": "SELECT EntityDefinition.QualifiedApiName, ValidationName, Active FROM ValidationRule WHERE Active = true ORDER BY EntityDefinition.QualifiedApiName LIMIT 50"},
    {"label": "Workflow Rules (active)", "q": "SELECT Name, TableEnumOrId FROM WorkflowRule WHERE Metadata.active = true LIMIT 20"},
    # UI & Components
    {"label": "LWC Components", "q": "SELECT DeveloperName, MasterLabel FROM LightningComponentBundle ORDER BY DeveloperName LIMIT 60"},
    {"label": "Aura Bundles", "q": "SELECT DeveloperName FROM AuraDefinitionBundle ORDER BY DeveloperName LIMIT 30"},
    {"label": "Visualforce Pages", "q": "SELECT Name, ApiVersion FROM ApexPage WHERE NamespacePrefix = null ORDER BY Name LIMIT 30"},
    # Security & Permissions
    {"label": "Custom Permission Sets", "q": "SELECT Name, Label, Description FROM PermissionSet WHERE IsOwnedByProfile = false AND NamespacePrefix = null ORDER BY Name LIMIT 40"},
    {"label": "Profiles", "q": "SELECT Name, UserType FROM Profile ORDER BY Name LIMIT 30"},
    {"label": "Permission Set Groups", "q": "SELECT MasterLabel, DeveloperName FROM PermissionSetGroup ORDER BY MasterLabel LIMIT 20"},
    # Integration
    {"label": "Named Credentials", "q": "SELECT DeveloperName, Endpoint, AuthProtocol FROM NamedCredential ORDER BY DeveloperName LIMIT 20"},
    {"label": "Connected Apps", "q": "SELECT Name, ContactEmail FROM ConnectedApplication ORDER BY Name LIMIT 20"},
    # Configuration
    {"label": "Custom Labels", "q": "SELECT Name, Value, Category FROM ExternalString ORDER BY Name LIMIT 40"},
    {"label": "Custom Metadata Records", "q": "SELECT Label, QualifiedApiName FROM CustomObjectDefinition WHERE DeveloperName LIKE '%__mdt' LIMIT 10"},
    # Reports & Dashboards
    {"label": "Reports", "q": "SELECT Name, DeveloperName, FolderName FROM Report ORDER BY Name LIMIT 30"},
    {"label": "Dashboards", "q": "SELECT Title, DeveloperName, FolderName FROM Dashboard ORDER BY Title LIMIT 20"},
    # Packages
    {"label": "Installed Packages", "q": "SELECT SubscriberPackage.Name, SubscriberPackageVersion.MajorVersion, SubscriberPackageVersion.MinorVersion FROM InstalledSubscriberPackage ORDER BY SubscriberPackage.Name LIMIT 20"},
]

# Domain config: what to retrieve + discovery SOQL
_DOMAIN_CONFIG: Dict[str, Dict[str, Any]] = {
    "cpq": {
        "retrieve": ["CustomObject:SBQQ__Quote__c", "CustomObject:SBQQ__QuoteLine__c", "CustomObject:SBQQ__PriceRule__c"],
        "soql": [
            {"label": "Active Price Rules", "q": "SELECT Name, SBQQ__EvaluationEvent__c, SBQQ__EvaluationOrder__c FROM SBQQ__PriceRule__c WHERE SBQQ__Active__c = true ORDER BY SBQQ__EvaluationOrder__c LIMIT 20"},
            {"label": "CPQ Products", "q": "SELECT ProductCode, Name, SBQQ__ConfigurationType__c FROM Product2 WHERE IsActive = true AND ProductCode != null ORDER BY ProductCode LIMIT 30"},
            {"label": "Product Features", "q": "SELECT Name, SBQQ__ConfiguredSKU__r.ProductCode, SBQQ__MinOptionCount__c, SBQQ__MaxOptionCount__c FROM SBQQ__ProductFeature__c ORDER BY Name LIMIT 20"},
        ],
    },
    "billing": {
        "retrieve": ["CustomObject:blng__Invoice__c", "CustomObject:blng__BillingRule__c"],
        "soql": [
            {"label": "Billing Rules", "q": "SELECT Name, blng__Active__c, blng__BillingDayOfMonth__c FROM blng__BillingRule__c WHERE blng__Active__c = true LIMIT 20"},
            {"label": "Finance Books", "q": "SELECT Name, blng__Status__c FROM blng__FinanceBook__c LIMIT 10"},
        ],
    },
    "apex": {
        "soql": [
            {"label": "Largest Apex classes", "q": "SELECT Name, ApiVersion, LengthWithoutComments FROM ApexClass WHERE NamespacePrefix = null ORDER BY LengthWithoutComments DESC LIMIT 15"},
            {"label": "Apex triggers", "q": "SELECT Name, TableEnumOrId, Status FROM ApexTrigger WHERE NamespacePrefix = null ORDER BY Name LIMIT 20"},
            {"label": "Test coverage gaps", "q": "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered FROM ApexCodeCoverageAggregate ORDER BY NumLinesCovered ASC LIMIT 15"},
        ],
        "retrieve_soql_names": True,   # retrieve top classes discovered by SOQL
    },
    "lwc": {
        "soql": [{"label": "LWC Components", "q": "SELECT DeveloperName FROM LightningComponentBundle ORDER BY DeveloperName LIMIT 30"}],
        "retrieve_soql_names": True,
    },
    "flow": {
        "soql": [{"label": "Active Flows", "q": "SELECT MasterLabel, ProcessType, TriggerType FROM Flow WHERE Status = 'Active' ORDER BY MasterLabel LIMIT 30"}],
        "retrieve_soql_names": True,
    },
    "objects": {
        "soql": [{"label": "Custom objects", "q": "SELECT Label, QualifiedApiName FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' ORDER BY QualifiedApiName LIMIT 30"}],
        "retrieve_soql_names": True,
    },
    "security": {
        # No hardcoded retrieve specs — dynamically discover and retrieve the top permission sets
        "retrieve_soql_names": True,
        "soql": [
            {"label": "Custom permission sets", "q": "SELECT Name, Label FROM PermissionSet WHERE IsOwnedByProfile = false AND NamespacePrefix = null ORDER BY Name LIMIT 20"},
            {"label": "Profiles with ModifyAll", "q": "SELECT Name FROM Profile WHERE PermissionsModifyAllData = true LIMIT 10"},
            {"label": "Permission set groups", "q": "SELECT MasterLabel, DeveloperName FROM PermissionSetGroup ORDER BY MasterLabel LIMIT 20"},
        ],
        # Dynamic: retrieve the top 5 custom permission sets discovered by SOQL
        "_retrieve_type": "PermissionSet",
        "_retrieve_name_field": "Name",
    },
}

# Keep old _DOMAIN_QUERIES name as alias for backward compat
_DOMAIN_QUERIES = {k: v.get("soql", []) for k, v in _DOMAIN_CONFIG.items()}


def _soql(org: str, query: str, label: str = "") -> str:
    """Run a SOQL query and return formatted results as a markdown table snippet."""
    try:
        r = subprocess.run(
            [_SF, "data", "query", "--query", query, "--target-org", org, "--json"],
            capture_output=True, text=True, timeout=20,
        )
        data = json.loads(r.stdout or "{}")
        records = data.get("result", {}).get("records", [])
        if not records:
            return f"_{label}: no records found_"
        # Format first 30 records as a simple list
        lines = [f"**{label}** ({len(records)} records):"]
        for rec in records[:30]:
            # Pick the most informative fields
            parts = []
            for k, v in rec.items():
                if k.startswith("attributes"):
                    continue
                if v and str(v) not in ("None", "null", "false", "0"):
                    parts.append(f"{k}={v}")
            lines.append("  - " + "  |  ".join(parts[:6]))
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"_{label}: query failed — {exc}_"


# Domain → SOQL queries to run before the agent
_DOMAIN_QUERIES: Dict[str, List[Dict[str, str]]] = {
    "cpq": [
        {"label": "CPQ Products (active)", "q": "SELECT ProductCode, Name, SBQQ__ConfigurationType__c, SBQQ__ChargeType__c FROM Product2 WHERE IsActive = true AND ProductCode != null ORDER BY ProductCode LIMIT 50"},
        {"label": "CPQ Price Rules (active)", "q": "SELECT Name, SBQQ__Active__c, SBQQ__EvaluationEvent__c, SBQQ__EvaluationOrder__c FROM SBQQ__PriceRule__c WHERE SBQQ__Active__c = true ORDER BY SBQQ__EvaluationOrder__c LIMIT 30"},
        {"label": "CPQ Product Features", "q": "SELECT Name, SBQQ__ConfiguredSKU__r.ProductCode, SBQQ__MinOptionCount__c, SBQQ__MaxOptionCount__c FROM SBQQ__ProductFeature__c ORDER BY Name LIMIT 30"},
        {"label": "CPQ Summary Variables", "q": "SELECT Name, SBQQ__AggregateFunction__c, SBQQ__TargetObject__c FROM SBQQ__SummaryVariable__c ORDER BY Name LIMIT 20"},
        {"label": "CustomScript (QCP)", "q": "SELECT Name, SBQQ__QuoteFields__c, SBQQ__QuoteLineFields__c FROM SBQQ__CustomScript__c LIMIT 5"},
    ],
    "billing": [
        {"label": "Billing Rules", "q": "SELECT Name, blng__Active__c, blng__BillingDayOfMonth__c, blng__InitialBillingDayOfMonth__c FROM blng__BillingRule__c WHERE blng__Active__c = true LIMIT 20"},
        {"label": "Revenue Recognition Rules", "q": "SELECT Name, blng__Active__c, blng__RecognitionMethod__c FROM blng__RevenueRecognitionRule__c WHERE blng__Active__c = true LIMIT 20"},
        {"label": "Tax Rules", "q": "SELECT Name, blng__Active__c FROM blng__TaxRule__c WHERE blng__Active__c = true LIMIT 10"},
        {"label": "Finance Books", "q": "SELECT Name, blng__Status__c FROM blng__FinanceBook__c LIMIT 10"},
        {"label": "Recent Invoices", "q": "SELECT Name, blng__Account__r.Name, blng__Status__c, blng__InvoiceDate__c, blng__TotalAmount__c FROM blng__Invoice__c ORDER BY CreatedDate DESC LIMIT 10"},
    ],
    "apex": [
        {"label": "Apex Classes (custom, by size)", "q": "SELECT Name, ApiVersion, LengthWithoutComments FROM ApexClass WHERE NamespacePrefix = null ORDER BY LengthWithoutComments DESC LIMIT 40"},
        {"label": "Apex Triggers", "q": "SELECT Name, TableEnumOrId, Status FROM ApexTrigger WHERE NamespacePrefix = null ORDER BY Name LIMIT 30"},
        {"label": "Test Coverage (lowest)", "q": "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered FROM ApexCodeCoverageAggregate ORDER BY NumLinesCovered ASC LIMIT 20"},
    ],
    "lwc": [
        {"label": "LWC Components", "q": "SELECT DeveloperName, MasterLabel FROM LightningComponentBundle ORDER BY DeveloperName LIMIT 60"},
        {"label": "Aura Bundles", "q": "SELECT DeveloperName FROM AuraDefinitionBundle ORDER BY DeveloperName LIMIT 30"},
    ],
    "flow": [
        {"label": "Active Flows", "q": "SELECT MasterLabel, ProcessType, TriggerType, ApiVersion FROM Flow WHERE Status = 'Active' ORDER BY MasterLabel LIMIT 40"},
    ],
    "objects": [
        {"label": "Custom Objects", "q": "SELECT Label, QualifiedApiName, KeyPrefix FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' ORDER BY QualifiedApiName LIMIT 60"},
    ],
    "security": [
        {"label": "Permission Sets (custom)", "q": "SELECT Name, Label FROM PermissionSet WHERE IsOwnedByProfile = false AND NamespacePrefix = null ORDER BY Name LIMIT 30"},
        {"label": "Profiles with ModifyAll", "q": "SELECT Name FROM Profile WHERE PermissionsModifyAllData = true ORDER BY Name LIMIT 10"},
    ],
}

_KEYWORD_MAP = {
    "cpq": ["cpq", "quote", "quoting", "bundle", "product", "price", "sbqq", "discount", "revenue cloud"],
    "billing": ["billing", "invoice", "revenue", "blng", "tax", "payment", "finance", "order"],
    "apex": ["apex", "trigger", "class", "code", "coverage"],
    "lwc": ["lwc", "lightning", "component", "aura", "ui", "frontend"],
    "flow": ["flow", "automation", "declarative", "process"],
    "objects": ["object", "field", "schema", "data model", "metadata"],
    "security": ["security", "permission", "profile", "sharing", "fls", "access"],
}

# Keywords that indicate the task is about the SWARM ITSELF, not the Salesforce org
_SWARM_SELF_KEYWORDS = [
    "swarm", "agent", "orchestrat", "fleet", "skill", "intent router",
    "agentic", "multi-agent", "agency", "cursor sdk", "llm", "routing",
    "improve.*swarm", "make.*swarm", "swarm.*better", "swarm.*powerful",
    "modern.*agent", "agent.*framework", "contest.*team", "split.*team",
]


def _is_about_swarm(user_input: str) -> bool:
    """True when the user is asking about the swarm/agent framework, not the Salesforce org."""
    import re as _re
    text = user_input.lower()
    return any(_re.search(kw, text) for kw in _SWARM_SELF_KEYWORDS)


def _swarm_self_context(run_id: str, agent_id: str) -> str:
    """
    Build context by reading the swarm's own codebase — used when the task
    is about improving/analyzing the swarm itself, not the Salesforce org.
    """
    append_activity(run_id, agent_id, "🔍 Reading swarm codebase (self-analysis)…")
    swarm_dir = Path(__file__).parent
    sections: List[str] = ["## Swarm self-context (your own codebase)\n"]

    # agents_registry.py — what agents exist
    reg_path = swarm_dir / "agents_registry.py"
    if reg_path.exists():
        sections.append(f"### agents_registry.py (teams + agents)\n{reg_path.read_text(encoding='utf-8')[:3000]}")

    # intent_router.py — how routing works
    router_path = swarm_dir / "intent_router.py"
    if router_path.exists():
        sections.append(f"### intent_router.py (routing logic)\n{router_path.read_text(encoding='utf-8')[:2000]}")

    # Agent instructions — what each agent is told to do
    agency_dir = REPO_ROOT / ".cursor" / "agency"
    if agency_dir.is_dir():
        for instr in sorted(agency_dir.rglob("instructions.md"))[:6]:
            agent_name = instr.parent.name
            text = instr.read_text(encoding="utf-8")[:800]
            sections.append(f"### .cursor/agency/{agent_name}/instructions.md\n{text}")

    # Skill feed registry — what each agent knows
    feed_reg = swarm_dir / "skill_feed_registry.py"
    if feed_reg.exists():
        sections.append(f"### skill_feed_registry.py (agent knowledge feeds)\n{feed_reg.read_text(encoding='utf-8')[:1500]}")

    # Latest skill KB files summary
    kb_sfdc = REPO_ROOT / "knowledge-base" / "sfdc"
    if kb_sfdc.is_dir():
        topics = sorted(kb_sfdc.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for t in topics:
            sections.append(f"### KB: {t.name}\n{t.read_text(encoding='utf-8')[:400]}")

    append_activity(run_id, agent_id, f"  Read {len(sections)-1} swarm source files")
    return "\n\n".join(sections)[:8000]


def _live_org_context(user_input: str, org: str, run_id: str, agent_id: str) -> str:
    """
    Return context appropriate for the request:
    - If request is about the swarm itself → read swarm source files
    - If request is about the Salesforce org → run SOQL queries
    """
    # Self-referential: task is about the swarm/agents, not the org
    if _is_about_swarm(user_input):
        append_activity(run_id, agent_id, "🧠 Task is about the swarm itself — reading swarm source")
        return _swarm_self_context(run_id, agent_id)

    # Org task: detect domains
    text = user_input.lower()
    domains: List[str] = []
    for domain, keywords in _KEYWORD_MAP.items():
        if any(kw in text for kw in keywords):
            domains.append(domain)

    if not domains:
        return (
            "_No specific Salesforce domain detected. "
            "Provide analysis based on general Salesforce best practices._"
        )

    if not org:
        return "_No org configured — run `sfdc-swarm context` to set target org._"

    append_activity(run_id, agent_id, f"🔍 Connecting to {org} — full metadata scan + domain deep-dive: {', '.join(domains) if domains else 'general'}")
    sections: List[str] = [f"## Live org data from {org}\n"]

    # ── Phase 1: Full baseline scan (every org, every request) ───────────────
    append_activity(run_id, agent_id, "📋 Running full baseline metadata scan…")
    baseline_success = 0
    for q in _BASELINE_SOQL:
        result = _soql(org, q["q"], q["label"])
        if "no records found" not in result and "failed" not in result:
            sections.append(result)
            baseline_success += 1
    append_activity(run_id, agent_id, f"  ✅ Baseline: {baseline_success}/{len(_BASELINE_SOQL)} metadata types scanned")

    # ── Phase 2: Domain-specific deep dive (retrieve actual source) ──────────
    if domains:
        append_activity(run_id, agent_id, f"🔬 Domain deep-dive: {', '.join(domains)}")
    for domain in domains:
        cfg = _DOMAIN_CONFIG.get(domain, {})

        # 1. Discovery SOQL — find out what exists
        for q in cfg.get("soql", []):
            result = _soql(org, q["q"], q["label"])
            sections.append(result)
            append_activity(run_id, agent_id, f"  {result.split(chr(10))[0][:100]}")

        # 2. Retrieve actual metadata source files for fixed specs
        fixed_specs = cfg.get("retrieve", [])
        if fixed_specs:
            retrieved = _retrieve_metadata(org, fixed_specs, domain, run_id, agent_id)
            sections.append(retrieved)

        # 3. For dynamic domains: retrieve top items found by SOQL
        if cfg.get("retrieve_soql_names"):
            soql_res = cfg.get("soql", [])
            if soql_res:
                # Get names from the first SOQL result to drive targeted retrieve
                try:
                    r = subprocess.run(
                        [_SF, "data", "query", "--query", soql_res[0]["q"],
                         "--target-org", org, "--json"],
                        capture_output=True, text=True, timeout=20,
                    )
                    records = json.loads(r.stdout or "{}").get("result", {}).get("records", [])
                    # Map domain → metadata type + name field
                    type_map = {
                        "apex": ("ApexClass", "Name"),
                        "lwc": ("LightningComponentBundle", "DeveloperName"),
                        "flow": ("Flow", "MasterLabel"),
                        "objects": ("CustomObject", "QualifiedApiName"),
                    }
                    if domain in type_map and records:
                        meta_type, name_field = type_map[domain]
                        # Take top 5 most relevant
                        specs = [f"{meta_type}:{r.get(name_field, '')}" for r in records[:5] if r.get(name_field)]
                        if specs:
                            append_activity(run_id, agent_id, f"  📥 Retrieving top {len(specs)} {domain} items…")
                            retrieved = _retrieve_metadata(org, specs, f"Top {domain}", run_id, agent_id)
                            sections.append(retrieved)
                except Exception:  # noqa: BLE001
                    pass

    return "\n\n".join(sections)


def _read_prior_artifacts(run_id: str, names: List[str], max_chars: int = 4000) -> str:
    parts: List[str] = []
    run_path = _run_dir(run_id)
    for name in names:
        p = run_path / name
        if p.exists():
            parts.append(f"### {name}\n{p.read_text(encoding='utf-8')[:2000]}")
    return "\n\n".join(parts)[:max_chars]


def _invoke_cursor_agent(
    run_id: str,
    agent_id: str,
    prompt: str,
    timeout: int = 120,
) -> str:
    """
    Invoke the Cursor SDK agent runner (Node.js) and return the response text.
    Streams each line to the fleet activity feed.
    Falls back gracefully if CURSOR_API_KEY is not set.
    """
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key:
        msg = (
            "⚠️  CURSOR_API_KEY not configured. "
            "Set it in FleetView Settings or: export CURSOR_API_KEY=cursor_... "
            "(get yours at cursor.com/dashboard/integrations)"
        )
        append_activity(run_id, agent_id, msg)
        return msg

    cmd = [
        _NODE, _RUNNER,
        "--api-key", api_key,
        "--model", _MODEL,
        "--cwd", str(REPO_ROOT),
        "--agent-id", agent_id,
        "--prompt", prompt,
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(REPO_ROOT),
        )
        output_text = ""
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            raw_line = raw_line.rstrip()
            if not raw_line:
                continue
            try:
                ev = json.loads(raw_line)
                ev_type = ev.get("type", "")

                if ev_type == "agent_start":
                    model_label = ev.get("model", "auto")
                    append_activity(run_id, agent_id,
                        f"🤖 Agent: {ev.get('agent_id','?')} · LLM: {model_label}")
                    # Store model on agent record so UI can display it
                    update_agent(run_id, agent_id, {"model": model_label})

                elif ev_type == "model_resolved":
                    model_label = ev.get("model", "")
                    if model_label:
                        append_activity(run_id, agent_id, f"🧠 LLM resolved: {model_label}")
                        update_agent(run_id, agent_id, {"model": model_label})

                elif ev_type == "text":
                    chunk = ev.get("text", "")
                    output_text += chunk
                    first = chunk.strip().split("\n")[0][:200]
                    if first:
                        append_activity(run_id, agent_id, first)

                elif ev_type == "done":
                    output_text = ev.get("result", output_text)
                    model_done = ev.get("model", "")
                    usage = ev.get("usage", {})
                    duration_ms = ev.get("duration_ms", 0)
                    if model_done:
                        update_agent(run_id, agent_id, {"model": model_done})
                    if usage:
                        total = usage.get("total_tokens", 0)
                        inp   = usage.get("input_tokens", 0)
                        out   = usage.get("output_tokens", 0)
                        cache = usage.get("cache_read_tokens", 0)
                        # Estimate cost: ~$3/M input, ~$15/M output (rough Cursor estimate)
                        cost_usd = (inp / 1_000_000 * 3.0) + (out / 1_000_000 * 15.0)
                        dur_s = duration_ms / 1000
                        summary = (
                            f"✅ {total:,} tokens "
                            f"({inp:,} in · {out:,} out · {cache:,} cache) "
                            f"≈ ${cost_usd:.4f} · {dur_s:.1f}s"
                        )
                        append_activity(run_id, agent_id, summary)
                        update_agent(run_id, agent_id, {
                            "usage": usage,
                            "cost_usd": round(cost_usd, 6),
                            "duration_ms": duration_ms,
                        })
                        # Accumulate run-level totals
                        _accumulate_usage(run_id, agent_id, usage, cost_usd)

                elif ev_type == "error":
                    append_activity(run_id, agent_id, "❌ " + ev.get("text", ""))
                    return ev.get("text", "Agent error")
            except json.JSONDecodeError:
                append_activity(run_id, agent_id, raw_line[:200])

        proc.wait(timeout=timeout)
        return output_text.strip() or "_Agent completed with no text output._"

    except subprocess.TimeoutExpired:
        proc.kill()
        return "_Agent timed out_"
    except Exception as exc:  # noqa: BLE001
        return f"_Runner error: {exc}_"


# ── team nodes ─────────────────────────────────────────────────────────────

def run_requirements_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "requirements", "gathering requirements", "requirements_team")
    assigned = state.get("assigned_agents", [])
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []

    for agent in _agents_for_team_ids("requirements", assigned):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "requirements"})
        append_activity(run_id, agent["id"], f"Requirements agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["jira-subtask-workflow"])[0])
        jira_keys = re.findall(r"[A-Z]+-\d+", state["user_input"])
        jira_note = f"\nJira tickets detected: {', '.join(jira_keys)}" if jira_keys else ""

        prompt = f"""You are a Salesforce requirements analyst.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Analyse this Salesforce request and produce clear requirements.{jira_note}

REQUEST: {state['user_input']}

Produce:
1. **Goal** — one sentence what this delivers
2. **Acceptance criteria** — 5-8 specific, user-testable bullet points
3. **Scope** — what is in and out of scope
4. **Salesforce metadata needed** — objects, fields, classes, LWC affected
5. **Dependencies** — packages, Jira tickets, external systems
6. **Open questions** — what needs clarification before dev starts"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"requirements-{agent['id']}.md",
            f"# Requirements — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"],
            {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "status": "done", "artifact": path})

    return {"phase": "requirements_done", "artifacts": outcomes}


def run_research_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "research", "KB + live org research", "research_team")
    agent_id = "org-scout"
    update_agent(run_id, agent_id, {"status": "running", "started_at": _now(), "team_id": "research"})
    ctx = get_runtime()
    org = ctx.get("targetOrgAlias", "")

    # Step 1: query the live org
    append_activity(run_id, agent_id, f"Querying live org: {org}")
    org_data = _live_org_context(state["user_input"], org, run_id, agent_id)

    skill = _read_skill("codebase-explainer")

    conn_parts: List[str] = []
    conn = KB_DIR / "connected"
    if conn.is_dir():
        for p in sorted(conn.glob("*.md")):
            if p.name != "INDEX.md":
                conn_parts.append(f"### {p.name}\n{p.read_text(encoding='utf-8')[:1000]}")
    connected_ctx = "\n\n".join(conn_parts)[:2000] or ""

    connected_section = ("Connected indexes:\n" + connected_ctx) if connected_ctx else ""

    prompt = f"""You are a Salesforce analyst with live access to org data.
Project: {ctx.get('projectName','—')} · Org: {org}

{skill}

---

TASK: Analyze this request using the REAL org data below.

REQUEST: {state['user_input']}

=== LIVE ORG DATA (queried right now from {org}) ===
{org_data}
=== END ORG DATA ===

{connected_section}

Based on the ACTUAL data above, produce:
1. **What exists in this org** — specific components, classes, objects found (cite actual names from the data)
2. **How it works** — explain the actual implementation based on what you see
3. **Key components** — list the most important pieces with their purpose
4. **Gaps or issues** — anything missing, stale, or risky you see in the data
5. **Recommendations** — specific, actionable next steps based on what's actually there

Be specific. Reference actual class names, object names, and record counts from the org data."""

    output = _invoke_cursor_agent(run_id, agent_id, prompt)
    path = _write_artifact(run_id, "RESEARCH.md",
        f"# Live Org Research\n\n**Request:** {state['user_input']}\n**Org:** {org}\n\n{output}")
    update_agent(run_id, agent_id, {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
    return {"phase": "research_done", "delivery_path": path,
            "artifacts": [{"agent": agent_id, "artifact": path}]}


def run_design_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "design", "architecture design", "design_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["RESEARCH.md"])

    for agent in _agents_for_team_ids("design", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "design"})
        append_activity(run_id, agent["id"], f"Architect designing: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["sfdc-cta-mentor"])[0])
        kb = _read_kb(["well-architected", "apex-design-patterns", "data-modelling"])

        prompt = f"""You are a Salesforce Technical Architect.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Produce an architecture design for this Salesforce request.

REQUEST: {state['user_input']}

Research context:
{prior or 'No prior research — design from first principles.'}

Architecture knowledge:
{kb}

Produce:
1. **Chosen approach** — the architecture decision and why
2. **Trade-offs** — alternatives considered and why rejected
3. **Data model** — objects, fields, relationships, any schema changes
4. **Automation design** — triggers vs flows, where to use Apex service layer
5. **Security model** — sharing rules, FLS, permission set changes
6. **Integration points** — any external systems, named credentials, callouts
7. **Scalability** — governor limits, LDV, async patterns if needed"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"design-{agent['id']}.md",
            f"# Architecture Design — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "design_done", "artifacts": outcomes}


def run_development_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "development", "implementing", "development_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["RESEARCH.md", "PLAN.md", "design-technical-architect.md"])

    for agent in _agents_for_team_ids("development", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "development"})
        append_activity(run_id, agent["id"], f"Developer implementing: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["advanced-salesforce-developer"])[0])
        kb = _read_kb(["apex-design-patterns", "security-sharing", "governor-limits"])

        prompt = f"""You are an expert Salesforce developer. Write production-ready, bulkified, secure code.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

Key Salesforce knowledge:
{kb}

---

TASK: Implement this Salesforce feature.

REQUEST: {state['user_input']}

Prior research and design:
{prior or 'No prior context — implement following best practices.'}

Produce the full implementation:
1. **sf retrieve command** — exact command to retrieve the metadata you need first
2. **Implementation code** — actual Apex class/trigger, LWC HTML+JS, Flow design, or metadata XML
   - Apex: handler pattern, explicit `with sharing`, CRUD/FLS via stripInaccessible, no SOQL/DML in loops
   - LWC: error handling on all wire calls, no hardcoded IDs
   - Tests: @TestSetup, positive + negative + bulk scenario, assertions with messages
3. **Deploy command** — exact `sf project deploy start` command (user will review and run)
4. **Verification SOQL** — queries to confirm the change worked after deploy

Write actual working code. The developer will copy this directly."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"work-{agent['id']}.md",
            f"# Implementation — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "development_done", "artifacts": outcomes}


def run_admin_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "admin", "metadata & deployment", "admin_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["work-apex-developer.md", "work-codebase-worker.md"])

    for agent in _agents_for_team_ids("admin", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "admin"})
        append_activity(run_id, agent["id"], f"Admin agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["sfdc-metadata-sync"])[0])

        prompt = f"""You are a Salesforce admin and deployment specialist.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Produce metadata and deployment plan for this change.

REQUEST: {state['user_input']}

Implementation produced:
{prior or 'No implementation yet — provide general deployment guidance.'}

Produce:
1. **Metadata to retrieve** — exact `sf project retrieve start --metadata "Type:Name"` commands
2. **FLS updates** — which permission sets need field permissions and the exact `<fieldPermissions>` XML
3. **package.xml** — the deployment manifest entries
4. **Deploy command** — exact `sf project deploy start` command
5. **Manual steps** — what cannot be deployed (data records, Connected App settings, etc.)
6. **Rollback** — how to revert this change if it fails"""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"admin-{agent['id']}.md",
            f"# Admin / Deployment Plan — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "admin_done", "artifacts": outcomes}



def run_review_team(state: Dict[str, Any]) -> Dict[str, Any]:
    """PR / change-set review gate (no implementation)."""
    run_id = state["run_id"]
    mark_team_phase(run_id, "review", "reviewing", "review_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    agents = _agents_for_team_ids("review", state.get("assigned_agents", []))
    if not agents:
        agents = [a for a in AGENTS if a.get("id") == "pr-reviewer"] or agents_for_team("review")

    for agent in agents:
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "review"})
        append_activity(run_id, agent["id"], "Running structured code review…")
        skill = _read_skill((agent.get("skills") or ["advanced-salesforce-developer"])[0])
        prompt = f"""You are a Salesforce PR reviewer for project {ctx.get('projectName','—')}.
{skill}

REQUEST: {state['user_input']}

Produce a structured review with:
1. Decision: APPROVE | REQUEST CHANGES | BLOCK
2. Findings by severity (Critical / Major / Minor)
3. Apex/LWC/Flow/Metadata checklist notes
4. Required follow-ups before deploy

Do not implement changes — review only."""
        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"REVIEW-{agent['id']}.md", output)
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "review_done", "artifacts": outcomes}


def run_qa_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "qa", "testing", "qa_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    prior = _read_prior_artifacts(run_id, ["work-apex-developer.md", "RESEARCH.md"])

    for agent in _agents_for_team_ids("qa", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "qa"})
        append_activity(run_id, agent["id"], f"QA agent: {agent['name']}")

        skill = _read_skill(agent.get("skills", ["playwright-e2e-validation"])[0])

        prompt = f"""You are a Salesforce QA engineer specialising in Apex tests and E2E testing.
Project: {ctx.get('projectName','—')} · Org: {ctx.get('targetOrgAlias','—')}

{skill}

---

TASK: Write a concrete test plan for this Salesforce change.

REQUEST: {state['user_input']}

Implementation context:
{prior or 'No implementation context — write general test approach.'}

Produce:
1. **Apex test class** — complete skeleton with @TestSetup, positive test, negative test, bulk (200-record) test
   Each assert: `System.assertEquals(expected, actual, 'descriptive message')`
2. **SOQL verification** — queries to run post-deploy to confirm data state
3. **Manual UI test steps** — numbered step-by-step in the sandbox
4. **Edge cases** — 5 specific scenarios to test (nulls, zero quantities, max records, etc.)
5. **Playwright stub** — `test('scenario', async ({{page}}) => {{...}})` skeleton if the UI is involved

Write actual code stubs."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)
        path = _write_artifact(run_id, f"qa-{agent['id']}.md",
            f"# QA Plan — {agent['name']}\n\n**Request:** {state['user_input']}\n\n{output}")
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": path, "note_path": path})
        outcomes.append({"agent": agent["id"], "artifact": path})

    return {"phase": "qa_done", "artifacts": outcomes}


def run_documentation_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "documentation", "documenting", "documentation_team")
    ctx = get_runtime()
    outcomes: List[Dict[str, Any]] = []
    run_path = _run_dir(run_id)

    # Gather all work produced
    artifacts = [p for p in sorted(run_path.glob("*.md")) if p.name != "DELIVERY.md"]
    artifact_content = ""
    for p in artifacts:
        artifact_content += f"\n\n### {p.name}\n{p.read_text(encoding='utf-8')[:1500]}"

    for agent in _agents_for_team_ids("documentation", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "documentation"})
        append_activity(run_id, agent["id"], "Writing documentation from live org data…")

        skill = _read_skill("codebase-explainer")
        org = ctx.get("targetOrgAlias", "")

        # If no prior agents ran, query the org now (documentation-only request)
        if not artifact_content:
            append_activity(run_id, agent["id"], f"No prior analysis — querying org: {org}")
            org_data = _live_org_context(state["user_input"], org, run_id, agent["id"])
        else:
            org_data = ""

        org_section = (
            "=== LIVE ORG DATA ===\n" + org_data + "\n=== END ==="
            if org_data else ""
        )
        prior_section = artifact_content[:5000] or "No prior analysis available."

        prompt = f"""You are a Salesforce technical documentation specialist.
Project: {ctx.get('projectName','—')} · Org: {org}

{skill}

---

TASK: Produce comprehensive documentation based on REAL org data and analysis.

REQUEST: {state['user_input']}

{org_section}

Prior agent analysis:
{prior_section}

Produce detailed documentation:
1. **Overview** — what this functionality does in this org (2-3 paragraphs)
2. **Architecture** — how the components connect (describe the actual components found)
3. **Key components** — table with: Component Name | Type | Purpose | Key Logic
4. **Data model** — objects involved and how they relate
5. **Integration points** — external systems, APIs, or package boundaries
6. **Configuration** — key settings, custom metadata, picklist values
7. **Known patterns** — recurring design patterns seen in the code
8. **Limitations & risks** — technical debt, gaps, or risks identified

Base every section on ACTUAL component names and data from the org. No generic advice."""

        output = _invoke_cursor_agent(run_id, agent["id"], prompt)

        delivery_lines = [
            "# Delivery Summary",
            f"**Request:** {state['user_input']}",
            f"**Run:** {run_id}",
            f"**Org:** {ctx.get('targetOrgAlias','—')}",
            "",
            output,
            "",
            "## Work order files",
        ]
        for p in artifacts:
            delivery_lines.append(f"- `.cursor/swarm/.fleet/runs/{run_id}/{p.name}`")

        delivery_content = "\n".join(delivery_lines)
        delivery_path = _write_artifact(run_id, "DELIVERY.md", delivery_content)

        docs_dir = REPO_ROOT / "docs" / "swarm-deliveries"
        docs_dir.mkdir(parents=True, exist_ok=True)
        dest = docs_dir / f"{run_id}-delivery.md"
        dest.write_text(delivery_content, encoding="utf-8")

        update_agent(run_id, agent["id"],
            {"status": "done", "ended_at": _now(), "summary": str(dest), "note_path": str(dest)})
        outcomes.append({"agent": agent["id"], "artifact": str(dest)})

    return {"phase": "documentation_done", "delivery_path": str(dest), "artifacts": outcomes}


def run_training_team(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state["run_id"]
    mark_team_phase(run_id, "training", "refreshing skill manifest", "training_team")
    outcomes = []
    for agent in _agents_for_team_ids("training", state.get("assigned_agents", [])):
        update_agent(run_id, agent["id"], {"status": "running", "started_at": _now(), "team_id": "training"})
        try:
            from skill_refresh import run_skill_refresh
            run_skill_refresh("manifest")
            summary = "manifest refreshed"
        except Exception as exc:  # noqa: BLE001
            summary = f"skip: {exc}"
        update_agent(run_id, agent["id"], {"status": "done", "ended_at": _now(), "summary": summary})
        outcomes.append({"agent": agent["id"], "summary": summary})
    return {"phase": "training_done", "artifacts": outcomes}
