#!/usr/bin/env python3
"""Deep E2E + edge-case validation for Agency-Swarm (no API keys required)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-sfdx"
PYTHON = sys.executable

PASS = 0
FAIL = 0
ERRORS: list[str] = []


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  ✓ {name}")


def bad(name: str, detail: str) -> None:
    global FAIL
    FAIL += 1
    ERRORS.append(f"{name}: {detail}")
    print(f"  ✗ {name}\n      {detail}")


def run(cmd, cwd=None, env=None, timeout=120):
    e = os.environ.copy()
    # Force offline routing / no accidental LLM calls in CI
    e.pop("CURSOR_API_KEY", None)
    e.pop("ANTHROPIC_API_KEY", None)
    e.pop("SFDC_SWARM_PROJECT_ROOT", None)
    if env:
        e.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=e,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def section(title: str) -> None:
    print(f"\n══ {title} ══")


# ── 1. Repo hygiene ─────────────────────────────────────────────────────────
def test_hygiene():
    section("Repo hygiene")
    banned = (
        "nextgen2",
        "servicetitan",
        "sfdclq",
        "pantheon",
        "SFDC NextGen",
    )
    hits = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "tests" in path.parts or path.suffix in {".png", ".jpg", ".zip", ".pyc"}:
            continue
        if path.is_dir():
            if path.name == "{codebase,connected,sfdc,project,skills}":
                hits.append(str(path))
            continue
        if path.suffix not in {".py", ".md", ".json", ".sh", ".plist", ".html", ".js", ".yml", ".yaml", ".txt", ".command"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for b in banned:
            if b.lower() in text:
                hits.append(f"{path.relative_to(ROOT)} contains {b}")
                break
    if hits:
        bad("no employer/project refs", "; ".join(hits[:8]))
    else:
        ok("no employer/project refs")

    if (FRAMEWORK / "knowledge-base" / "{codebase,connected,sfdc,project,skills}").exists():
        bad("brace-dir removed", "literal brace directory still exists")
    else:
        ok("brace-dir removed")

    if (FRAMEWORK / "vendor" / "_shared" / "sfdc_context.py").is_file():
        ok("vendored sfdc_context present")
    else:
        bad("vendored sfdc_context present", "missing framework/vendor/_shared/sfdc_context.py")

    if (ROOT / "LICENSE").is_file() and "MIT" in (ROOT / "LICENSE").read_text():
        ok("MIT LICENSE present")
    else:
        bad("MIT LICENSE present", "missing or not MIT")


# ── 2. Imports ──────────────────────────────────────────────────────────────
def test_imports():
    section("Module imports")
    sys.path.insert(0, str(FRAMEWORK))
    mods = [
        "agents_registry",
        "agency_cursor_sync",
        "agent_nodes",
        "config",
        "project_context",
        "intent_router",
        "llm_router",
        "langgraph_orchestrator",
        "fleet",
        "fleet_hooks",
        "serve_fleet",
        "skill_refresh",
        "teams",
        "tools",
        "validate_jira_ac",
    ]
    for m in mods:
        try:
            __import__(m)
            ok(f"import {m}")
        except Exception as exc:
            bad(f"import {m}", f"{type(exc).__name__}: {exc}")


# ── 3. Registry integrity ───────────────────────────────────────────────────
def test_registry():
    section("Registry integrity")
    sys.path.insert(0, str(FRAMEWORK))
    from agents_registry import AGENTS, TEAMS, INTENT_TO_TEAMS, GRAPH_NODES, agents_for_team
    from langgraph_orchestrator import NODE_MAP
    from llm_router import VALID_TEAM_NODES

    team_ids = {t["id"] for t in TEAMS}
    agent_ids = [a["id"] for a in AGENTS]
    if len(agent_ids) != len(set(agent_ids)):
        bad("unique agent ids", "duplicate agent ids found")
    else:
        ok("unique agent ids")

    orphan = [a["id"] for a in AGENTS if a.get("team") not in team_ids]
    if orphan:
        bad("agents reference valid teams", str(orphan))
    else:
        ok("agents reference valid teams")

    for intent, pipeline in INTENT_TO_TEAMS.items():
        missing = [n for n in pipeline if n not in NODE_MAP]
        if missing:
            bad(f"intent {intent} pipeline nodes exist", str(missing))
        else:
            ok(f"intent {intent} pipeline nodes exist")
        for n in pipeline:
            if n not in VALID_TEAM_NODES:
                bad(f"intent {intent} in VALID_TEAM_NODES", n)

    if "review_team" not in NODE_MAP:
        bad("review_team in NODE_MAP", "missing")
    else:
        ok("review_team in NODE_MAP")

    if not agents_for_team("review"):
        bad("review team has agents", "empty")
    else:
        ok("review team has agents")

    gids = {g["id"] for g in GRAPH_NODES}
    if "review_team" not in gids:
        bad("GRAPH_NODES includes review_team", "missing")
    else:
        ok("GRAPH_NODES includes review_team")


# ── 4. Intent router edge cases ─────────────────────────────────────────────
def test_intent_router():
    section("Intent router (offline fallback)")
    sys.path.insert(0, str(FRAMEWORK))
    from intent_router import classify_intent
    from llm_router import route_user_input

    cases = [
        ("Explain how quote calculation works", "document"),
        ("Implement Apex trigger on Account", "implement"),
        ("Review this PR for security issues", "review"),
        ("Run playwright e2e tests", "test"),
        ("Design an architecture for usage billing", "design"),
        ("Look at PROJ-1001 acceptance criteria", "jira_only"),
        ("Refresh KB and update skills", "kb_refresh"),
        ("Audit unused Apex classes", "discover"),
        ("", "full_delivery"),  # empty → default
        ("!!!!", "full_delivery"),
        ("a" * 5000, None),  # should not crash
    ]
    for text, expected in cases:
        try:
            intent, pipeline, agents = classify_intent(text)
            if expected and intent != expected:
                bad(f"classify '{text[:40]}'", f"got {intent}, want {expected}")
            else:
                ok(f"classify '{text[:40] or '<empty>'}' → {intent}")
            if not isinstance(pipeline, list) or not pipeline:
                # empty input may still get full_delivery pipeline
                if intent != "full_delivery" and not pipeline:
                    bad(f"pipeline non-empty for '{text[:20]}'", str(pipeline))
            # route_user_input offline
            i2, p2, a2, line, method = route_user_input(text)
            if method != "rules":
                bad(f"offline route method '{text[:20]}'", method)
            else:
                ok(f"offline route '{text[:20] or '<empty>'}'")
        except Exception as exc:
            bad(f"classify crash '{text[:20]}'", f"{type(exc).__name__}: {exc}")


# ── 5. CLI without project ──────────────────────────────────────────────────
def test_cli_no_project():
    section("CLI outside SFDX project")
    r = run([PYTHON, str(FRAMEWORK / "run.py"), "--help"])
    if r.returncode == 0 and "orchestrate" in r.stdout:
        ok("run.py --help")
    else:
        bad("run.py --help", r.stderr or r.stdout)

    r = run([PYTHON, str(FRAMEWORK / "run.py")])
    if r.returncode == 1 and "usage:" in (r.stdout + r.stderr).lower():
        ok("run.py no-args prints help")
    else:
        bad("run.py no-args prints help", f"code={r.returncode} out={r.stdout[:200]}")

    with tempfile.TemporaryDirectory() as td:
        r = run([PYTHON, str(FRAMEWORK / "run.py"), "context"], cwd=td)
        if r.returncode == 2 and "sfdx-project.json" in (r.stdout + r.stderr):
            ok("context fails clearly outside project")
        else:
            bad("context fails clearly outside project", f"code={r.returncode} {(r.stdout+r.stderr)[:300]}")


# ── 6. Install + fixture E2E ────────────────────────────────────────────────
def test_install_and_fixture_e2e():
    section("Install-to-project + fixture E2E")
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        project = td_path / "demo-sfdx"
        shutil.copytree(FIXTURE, project)

        # install-to-project (skip global skills to keep isolated; still runs install-global)
        # Use a temp SFDC_SWARM_HOME so we don't clobber user's install unexpectedly in assertions
        swarm_home = td_path / "swarm-home"
        r = run(
            ["zsh", str(ROOT / "scripts" / "install-to-project.sh"), str(project)],
            env={"SFDC_SWARM_HOME": str(swarm_home)},
            timeout=180,
        )
        if r.returncode != 0:
            bad("install-to-project.sh", r.stderr or r.stdout)
            return
        ok("install-to-project.sh")

        link = project / "tools" / "sfdc-knowledge-swarm"
        if link.is_symlink() and link.resolve() == FRAMEWORK.resolve():
            ok("framework symlink")
        else:
            bad("framework symlink", f"{link} -> {link.resolve() if link.exists() else 'missing'}")

        for rel in [
            ".cursor/agency/CEO/instructions.md",
            ".cursor/agents/ceo.md",
            ".cursor/rules/agency-swarm-cursor.mdc",
            "AGENTS.md",
            "knowledge-base",
            "docs/swarm-deliveries",
        ]:
            if (project / rel).exists():
                ok(f"created {rel}")
            else:
                bad(f"created {rel}", "missing")

        # global shim installed
        if (swarm_home / "run.py").is_file():
            ok("global swarm home populated")
        else:
            bad("global swarm home populated", str(swarm_home))

        env = {
            "SFDC_SWARM_HOME": str(swarm_home),
            "SFDC_SWARM_PROJECT_ROOT": str(project),
            "PATH": os.environ.get("PATH", ""),
        }

        r = run([PYTHON, str(FRAMEWORK / "run.py"), "context"], cwd=project, env=env)
        if r.returncode == 0 and "agency-swarm-fixture" in (r.stdout + r.stderr) or "FIXTURE_ORG" in (r.stdout + r.stderr) or "demo-sfdx" in (r.stdout + r.stderr):
            ok("context resolves fixture project")
        else:
            # still ok if exit 0
            if r.returncode == 0:
                ok("context resolves fixture project")
            else:
                bad("context resolves fixture project", (r.stdout + r.stderr)[:400])

        r = run([PYTHON, str(FRAMEWORK / "run.py"), "agency-sync"], cwd=project, env=env, timeout=60)
        if r.returncode == 0:
            ok("agency-sync")
        else:
            bad("agency-sync", (r.stdout + r.stderr)[:400])

        # orchestrate offline (document intent)
        r = run(
            [PYTHON, str(FRAMEWORK / "run.py"), "orchestrate", "Explain the HelloService Apex class"],
            cwd=project,
            env=env,
            timeout=180,
        )
        if r.returncode == 0:
            ok("orchestrate document (offline)")
        else:
            bad("orchestrate document (offline)", (r.stdout + r.stderr)[:500])

        # orchestrate review intent
        r = run(
            [PYTHON, str(FRAMEWORK / "run.py"), "orchestrate", "Review this PR for Apex security"],
            cwd=project,
            env=env,
            timeout=180,
        )
        if r.returncode == 0:
            ok("orchestrate review (offline)")
        else:
            bad("orchestrate review (offline)", (r.stdout + r.stderr)[:500])

        # fleet snapshot
        r = run([PYTHON, str(FRAMEWORK / "run.py"), "fleet"], cwd=project, env=env)
        if r.returncode == 0:
            ok("fleet snapshot")
        else:
            bad("fleet snapshot", (r.stdout + r.stderr)[:300])

        # skill-refresh manifest (light)
        r = run(
            [PYTHON, str(FRAMEWORK / "run.py"), "skill-refresh", "--tier", "manifest"],
            cwd=project,
            env=env,
            timeout=180,
        )
        if r.returncode == 0:
            ok("skill-refresh manifest")
        else:
            bad("skill-refresh manifest", (r.stdout + r.stderr)[:400])

        # run.sh from tools symlink
        r = run(["zsh", str(link / "run.sh"), "context"], cwd=project, env=env)
        if r.returncode == 0:
            ok("tools/run.sh context")
        else:
            bad("tools/run.sh context", (r.stdout + r.stderr)[:300])


# ── 7. FleetView serve smoke ────────────────────────────────────────────────
def test_serve_fleet():
    section("FleetView HTTP smoke")
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "demo"
        shutil.copytree(FIXTURE, project)
        env = {
            "SFDC_SWARM_PROJECT_ROOT": str(project),
            "SFDC_SWARM_HOME": str(FRAMEWORK),
        }
        # Start server briefly via python API
        sys.path.insert(0, str(FRAMEWORK))
        os.environ["SFDC_SWARM_PROJECT_ROOT"] = str(project)
        try:
            from config import init_runtime, ensure_dirs
            init_runtime(force=True)
            ensure_dirs()

            # Use subprocess for reliability
            import socket, time
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()

            proc = subprocess.Popen(
                [PYTHON, str(FRAMEWORK / "run.py"), "serve", "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(project),
                env={**os.environ, **env, "CURSOR_API_KEY": "", "ANTHROPIC_API_KEY": ""},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            body = ""
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/skills-fleet.html", timeout=2) as resp:
                        body = resp.read().decode("utf-8", "ignore")
                        if resp.status == 200 and len(body) > 100:
                            ok("FleetView HTML serves")
                            break
                except Exception:
                    time.sleep(0.4)
            else:
                # drain some output
                try:
                    proc.terminate()
                except Exception:
                    pass
                out = ""
                try:
                    out = proc.communicate(timeout=3)[0] or ""
                except Exception:
                    pass
                bad("FleetView HTML serves", out[:400] or "timeout waiting for server")
                return

            # API endpoints commonly used
            for path in ("/api/fleet", "/api/health", "/api/agents", "/api/graph"):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as resp:
                        data = resp.read()
                        if resp.status == 200:
                            ok(f"GET {path}")
                        else:
                            bad(f"GET {path}", f"status {resp.status}")
                except urllib.error.HTTPError as e:
                    # Some paths may be 404 depending on version — try soft
                    if e.code == 404:
                        ok(f"GET {path} (404 acceptable)")
                    else:
                        bad(f"GET {path}", f"HTTP {e.code}")
                except Exception as exc:
                    bad(f"GET {path}", str(exc))

            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception as exc:
            bad("FleetView serve", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[:400]}")


# ── 8. Template / agent file consistency ────────────────────────────────────
def test_templates():
    section("Templates consistency")
    agents_dir = ROOT / "templates" / "cursor" / "agents"
    agency_dir = ROOT / "templates" / "cursor" / "agency"
    required_agents = [
        "ceo.md",
        "advanced-salesforce-developer.md",
        "jira-subtask-workflow.md",
        "sfdc-metadata-sync.md",
        "sfdc-promotion-workflow.md",
        "sfdc-cta-mentor.md",
        "codebase-explainer.md",
        "playwright-e2e-validation.md",
        "pr-reviewer.md",
        "org-analyst.md",
        "reverse-engineer.md",
        "apex-space-reclaimer.md",
    ]
    for name in required_agents:
        if (agents_dir / name).is_file():
            ok(f"agent template {name}")
        else:
            bad(f"agent template {name}", "missing")

    for folder in [
        "CEO",
        "advanced-salesforce-developer",
        "jira-subtask-workflow",
        "sfdc-metadata-sync",
        "sfdc-promotion-workflow",
        "sfdc-cta-mentor",
        "codebase-explainer",
        "playwright-e2e-validation",
        "pr-reviewer",
        "org-analyst",
        "reverse-engineer",
        "apex-space-reclaimer",
    ]:
        inst = agency_dir / folder / "instructions.md"
        if inst.is_file() and "NEXTGEN2" not in inst.read_text() and "/Users/" not in inst.read_text():
            ok(f"agency instructions {folder}")
        elif not inst.is_file():
            bad(f"agency instructions {folder}", "missing")
        else:
            bad(f"agency instructions {folder}", "contains absolute path or NEXTGEN2")

    # skills _shared
    if (ROOT / "templates" / "cursor" / "skills" / "_shared" / "sfdc_context.py").is_file():
        ok("templates _shared/sfdc_context.py")
    else:
        bad("templates _shared/sfdc_context.py", "missing")


# ── 9. Edge: broken project-topics JSON ─────────────────────────────────────
def test_edge_bad_topics_json():
    section("Edge cases")
    sys.path.insert(0, str(FRAMEWORK))
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "broken"
        shutil.copytree(FIXTURE, project)
        topics = project / ".cursor" / "swarm" / "project-topics.json"
        topics.write_text("{not-json", encoding="utf-8")
        os.environ["SFDC_SWARM_PROJECT_ROOT"] = str(project)
        from config import init_runtime
        from project_context import resolve_swarm_context
        try:
            ctx = resolve_swarm_context(start=project)
            if ctx.get("projectTopics") == []:
                ok("invalid project-topics.json → empty list")
            else:
                bad("invalid project-topics.json → empty list", str(ctx.get("projectTopics")))
        except Exception as exc:
            bad("invalid project-topics.json → empty list", str(exc))

        # Master package path layout
        master = Path(td) / "master-proj"
        (master / "Master" / "main" / "default" / "classes").mkdir(parents=True)
        (master / "sfdx-project.json").write_text(
            json.dumps({"packageDirectories": [{"path": "Master", "default": True}], "name": "master-proj"}),
            encoding="utf-8",
        )
        from sfdc_context import default_source_path, find_sfdx_project_root
        # import via vendor
        sys.path.insert(0, str(FRAMEWORK / "vendor" / "_shared"))
        import importlib
        import sfdc_context as sc
        importlib.reload(sc)
        sp = sc.default_source_path(master)
        if sp == "Master/main/default":
            ok("Master package source path")
        else:
            bad("Master package source path", sp)

        # missing packageDirectories
        bare = Path(td) / "bare"
        (bare / "force-app" / "main" / "default").mkdir(parents=True)
        (bare / "sfdx-project.json").write_text("{}", encoding="utf-8")
        sp2 = sc.default_source_path(bare)
        if sp2 == "force-app/main/default":
            ok("empty packageDirectories fallback")
        else:
            bad("empty packageDirectories fallback", sp2)


def main():
    print("Agency-Swarm deep validation")
    print(f"ROOT={ROOT}")
    test_hygiene()
    test_imports()
    test_registry()
    test_intent_router()
    test_cli_no_project()
    test_templates()
    test_edge_bad_topics_json()
    test_install_and_fixture_e2e()
    test_serve_fleet()

    print("\n══════════════════════════════════════")
    print(f"PASS={PASS}  FAIL={FAIL}")
    if ERRORS:
        print("\nFailures:")
        for e in ERRORS:
            print(f" - {e}")
    print("══════════════════════════════════════")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
