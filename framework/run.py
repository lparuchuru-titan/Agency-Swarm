"""CLI entrypoint for LangChain swarm and FleetView monitor."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta

from rich.console import Console
from rich.live import Live
from rich.table import Table

from config import GLOBAL_SFDC_NOTES_DIR, REFRESH_AFTER_DAYS, SWARM_CRON, TOPICS, ensure_dirs, get_runtime, init_runtime
from fleet import fleet_snapshot

console = Console()


def cmd_fleet(_: argparse.Namespace) -> None:
    snap = fleet_snapshot()
    health = snap["health"]
    console.print(f"[bold]Fleet health:[/] {health['overall']} ({health['score']}%)")
    table = Table(title="Recent swarm runs")
    table.add_column("Source")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Agents")
    for run in snap.get("runs", [])[:10]:
        agents = run.get("agents", [])
        running = sum(1 for a in agents if a.get("status") == "running")
        table.add_row(
            run.get("source", ""),
            run.get("run_id", ""),
            run.get("status", ""),
            f"{len(agents)} ({running} running)",
        )
    console.print(table)


def cmd_fleet_watch(_: argparse.Namespace) -> None:
    def render():
        snap = fleet_snapshot()
        health = snap["health"]
        table = Table(title=f"SFDC Agent Fleet — {health['overall']} ({health['score']}%)")
        table.add_column("Run")
        table.add_column("Agent")
        table.add_column("Status")
        table.add_column("Summary")
        for run in snap.get("runs", [])[:5]:
            for agent in run.get("agents", []):
                table.add_row(
                    f"{run.get('source')}:{run.get('run_id', '')[:8]}",
                    agent.get("label", agent.get("id", "")),
                    agent.get("status", ""),
                    (agent.get("summary") or "")[:60],
                )
        return table

    with Live(render(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(render())
            time.sleep(2)


def cmd_serve(args: argparse.Namespace) -> None:
    from serve_fleet import run_server

    run_server(args.host, args.port)


def cmd_once(args: argparse.Namespace) -> None:
    from swarm import start_run

    keys = args.topics or None
    if not keys and not args.force:
        stale = []
        for t in TOPICS:
            path = GLOBAL_SFDC_NOTES_DIR / f"{t['key']}.md"
            if not path.exists():
                stale.append(t["key"])
            else:
                age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
                if age > timedelta(days=REFRESH_AFTER_DAYS):
                    stale.append(t["key"])
        if stale:
            keys = stale
            console.print(f"[yellow]Refreshing {len(stale)} stale/missing topics[/]")
        else:
            console.print("[green]All notes fresh; use --force to refresh all[/]")
            return

    console.print("[bold]Starting LangChain swarm…[/] (requires ANTHROPIC_API_KEY)")
    result = start_run(topic_keys=keys, force=args.force)
    console.print(f"Run {result['run_id']} complete.")
    for r in result.get("results", []):
        console.print(f"  {r.get('key')}: {r.get('status')}")


def cmd_list(_: argparse.Namespace) -> None:
    from config import SFDC_NOTES_DIR

    table = Table(title="Knowledge topics")
    table.add_column("Key")
    table.add_column("Title")
    table.add_column("Note")
    for t in TOPICS:
        path = SFDC_NOTES_DIR / f"{t['key']}.md"
        table.add_row(t["key"], t["title"], "yes" if path.exists() else "missing")
    console.print(table)


def cmd_schedule(_: argparse.Namespace) -> None:
    import schedule

    from dev_swarm import start_dev_swarm
    from swarm import start_run

    def job_docs():
        console.print(f"[cyan]Scheduled doc swarm at {datetime.now()}[/]")
        start_run()

    def job_dev():
        console.print(f"[cyan]Scheduled dev swarm at {datetime.now()}[/]")
        start_dev_swarm()

    schedule.every().day.at(SWARM_CRON).do(job_dev)
  # doc swarm 30 min after dev swarm
    hour, minute = SWARM_CRON.split(":")
    doc_min = (int(minute) + 30) % 60
    doc_hour = int(hour) + (1 if int(minute) + 30 >= 60 else 0)
    schedule.every().day.at(f"{doc_hour:02d}:{doc_min:02d}").do(job_docs)

    console.print(f"Scheduler running — dev swarm daily at {SWARM_CRON}. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


def cmd_dev_once(args: argparse.Namespace) -> None:
    from dev_swarm import start_dev_swarm

    console.print("[bold]Starting Dev Development Swarm…[/] (codebase scan, no API key required)")
    result = start_dev_swarm(
        team_ids=args.teams or None,
        topic_keys=args.topics or None,
        force=args.force,
        deep=args.deep,
    )
    console.print(f"Run {result['run_id']} · teams: {', '.join(result.get('teams', []))}")
    for r in result.get("results", []):
        console.print(f"  {r.get('key')}: {r.get('status')} — {r.get('summary', '')[:60]}")


def cmd_orchestrate(args: argparse.Namespace) -> None:
    from langgraph_orchestrator import run_orchestrator

    user_input = args.input.strip()
    if not user_input:
        console.print("[red]Provide input text, e.g. orchestrate \"Implement quote line editor view\"[/]")
        sys.exit(1)
    console.print(f"[bold]Orchestrator[/] — routing: {user_input[:80]}…")
    result = run_orchestrator(user_input)
    console.print(f"Run {result['run_id']} · intent: {result.get('intent')}")
    console.print(f"Pipeline: {' → '.join(result.get('pipeline', []))}")
    if result.get("delivery_path"):
        console.print(f"Delivery: {result['delivery_path']}")
    console.print(f"Artifacts: tools/sfdc-knowledge-swarm/.fleet/runs/{result['run_id']}/")


def cmd_agency_sync(_: argparse.Namespace) -> None:
    from agency_cursor_sync import sync_agency_cursor

    result = sync_agency_cursor()
    console.print("[green]Agency sync complete[/]")
    console.print(f"  agency_dir: {result['agency_dir']}")
    console.print(f"  agents: {', '.join(result['agents'])}")
    console.print(f"  AGENTS.md: {result['agents_md']}")


def cmd_context(_: argparse.Namespace) -> None:
    ctx = get_runtime()
    console.print(f"[bold]Project:[/] {ctx.get('projectName')} ({ctx.get('repoRoot')})")
    console.print(f"[bold]Target org:[/] {ctx.get('targetOrgAlias')} ({ctx.get('targetOrgSource')})")
    console.print(f"[bold]Source path:[/] {ctx.get('sourcePath')}")
    console.print(f"[bold]KB dir:[/] {ctx.get('kbDir')}")
    console.print(f"[bold]Swarm home:[/] {ctx.get('swarmHome')}")
    console.print(f"[bold]Deploy:[/] {ctx.get('deployCommandTemplate')}")


def cmd_skill_refresh_all(args: argparse.Namespace) -> None:
    from skill_refresh import run_skill_refresh_all_projects

    tier = args.tier or "daily"
    console.print(f"[bold]Skill refresh all projects[/] tier={tier}")
    result = run_skill_refresh_all_projects(tier=tier, force=args.force)
    for outcome in result.get("outcomes", []):
        name = outcome.get("project", "?")
        if outcome.get("error"):
            console.print(f"  [red]{name}: {outcome['error']}[/]")
        else:
            console.print(f"  {name} ({outcome.get('org', '')}) — ok")


def cmd_skill_refresh(args: argparse.Namespace) -> None:
    from skill_refresh import run_skill_refresh, schedule_info

    tier = args.tier or "weekly"
    console.print(f"[bold]Skill refresh[/] tier={tier} (see skill_schedule_config for token costs)")
    result = run_skill_refresh(tier=tier, force=args.force, deep=args.deep)
    if not result.get("ok"):
        console.print(f"[red]{result.get('error')}[/]")
        sys.exit(1)
    for outcome in result.get("outcomes", []):
        t = outcome.get("tier", "?")
        cost = outcome.get("token_cost", outcome.get("skipped", ""))
        console.print(f"  {t}: token_cost={cost}")
        if outcome.get("manifest_path"):
            console.print(f"    manifest → {outcome['manifest_path']}")
        if outcome.get("master_index"):
            console.print(f"    connected → {outcome['master_index']}")
        if outcome.get("reason"):
            console.print(f"    {outcome['reason']}")
    info = schedule_info()
    console.print(f"[dim]Log: {info.get('log_path')}[/]")


def cmd_skill_refresh_schedule(_: argparse.Namespace) -> None:
    import schedule

    from skill_refresh import run_skill_refresh
    from skill_schedule_config import (
        CRON_CODEBASE_DAILY,
        CRON_CONNECTED,
        CRON_OPEN_DEEP,
    )

    def job_daily():
        console.print(f"[cyan]Daily skill refresh {datetime.now()}[/]")
        run_skill_refresh("daily")

    def job_weekly():
        console.print(f"[cyan]Weekly connected + open light {datetime.now()}[/]")
        run_skill_refresh("weekly")

    def job_monthly():
        console.print(f"[cyan]Monthly open deep check {datetime.now()}[/]")
        run_skill_refresh("monthly")

    schedule.every().day.at(CRON_CODEBASE_DAILY).do(job_daily)
    schedule.every().sunday.at(CRON_CONNECTED).do(job_weekly)
    schedule.every().day.at(CRON_OPEN_DEEP).do(job_monthly)

    console.print(
        f"Skill refresh scheduler — daily {CRON_CODEBASE_DAILY} (codebase+manifest), "
        f"weekly Sun {CRON_CONNECTED} (+connected+open static), "
        f"deep check daily {CRON_OPEN_DEEP} (runs LLM only on day 1). Ctrl+C to stop."
    )
    while True:
        schedule.run_pending()
        time.sleep(30)


def cmd_dev_schedule(_: argparse.Namespace) -> None:
    import schedule

    from dev_swarm import start_dev_swarm

    def job():
        console.print(f"[cyan]Scheduled dev swarm at {datetime.now()}[/]")
        start_dev_swarm(deep=bool(__import__("os").environ.get("ANTHROPIC_API_KEY")))

    schedule.every().day.at(SWARM_CRON).do(job)
    console.print(f"Dev swarm scheduler — daily at {SWARM_CRON}. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agency-Swarm — Salesforce multi-agent CLI (FleetView, orchestrator, skill refresh)",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("fleet", help="Print fleet snapshot").set_defaults(func=cmd_fleet)
    sub.add_parser("watch", help="Live terminal fleet view").set_defaults(func=cmd_fleet_watch)
    p_serve = sub.add_parser("serve", help="Web FleetView dashboard")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=cmd_serve)

    p_once = sub.add_parser("once", help="Run LangChain swarm once")
    p_once.add_argument("--force", action="store_true")
    p_once.add_argument("--topics", nargs="*", help="Topic keys to refresh")
    p_once.set_defaults(func=cmd_once)

    sub.add_parser("list", help="List topics and note status").set_defaults(func=cmd_list)
    sub.add_parser("schedule", help="Run doc + dev swarm on SWARM_CRON daily").set_defaults(func=cmd_schedule)

    p_dev = sub.add_parser("dev-once", help="Run dev swarm (codebase KB, all teams)")
    p_dev.add_argument("--force", action="store_true")
    p_dev.add_argument("--deep", action="store_true", help="LangChain synthesis if ANTHROPIC_API_KEY set")
    p_dev.add_argument("--teams", nargs="*", help="Team ids: ui-ux salesforce-dev salesforce-admin")
    p_dev.add_argument("--topics", nargs="*", help="Codebase topic keys")
    p_dev.set_defaults(func=cmd_dev_once)

    sub.add_parser("dev-schedule", help="Schedule dev swarm only daily").set_defaults(func=cmd_dev_schedule)

    p_skill = sub.add_parser("skill-refresh", help="Tiered skill/KB refresh (token-aware)")
    p_skill.add_argument(
        "--tier",
        default="weekly",
        choices=[
            "codebase",
            "manifest",
            "connected",
            "open_light",
            "open_deep",
            "daily",
            "weekly",
            "monthly",
            "all_light",
        ],
        help="Refresh tier (default weekly = manifest + connected + open static)",
    )
    p_skill.add_argument("--force", action="store_true", help="Ignore stale checks")
    p_skill.add_argument("--deep", action="store_true", help="Allow LLM on codebase tier")
    p_skill.set_defaults(func=cmd_skill_refresh)

    sub.add_parser("skill-refresh-schedule", help="Run all skill refresh cron jobs in-process").set_defaults(
        func=cmd_skill_refresh_schedule
    )

    p_skill_all = sub.add_parser("skill-refresh-all", help="Skill refresh every registered SFDC project")
    p_skill_all.add_argument("--tier", default="daily", choices=["daily", "weekly", "monthly", "all_light"])
    p_skill_all.add_argument("--force", action="store_true")
    p_skill_all.set_defaults(func=cmd_skill_refresh_all)

    sub.add_parser("context", help="Show resolved project + Salesforce org").set_defaults(func=cmd_context)

    p_orch = sub.add_parser("orchestrate", help="Run supervisor orchestrator on user input")
    p_orch.add_argument("input", help="User request (e.g. Implement quote line editor for PROJ-1234)")
    p_orch.set_defaults(func=cmd_orchestrate)

    sub.add_parser("agency-sync", help="Sync Agency Swarm-style .cursor/agency folders").set_defaults(
        func=cmd_agency_sync
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    # Resolve project context only after argparse (so --help works anywhere).
    try:
        init_runtime(force=True)
        ensure_dirs()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/]")
        console.print(
            "[dim]Run from a Salesforce DX project (folder with sfdx-project.json), "
            "or set SFDC_SWARM_PROJECT_ROOT.[/]"
        )
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to resolve project context:[/] {exc}")
        sys.exit(2)

    args.func(args)


if __name__ == "__main__":
    main()
