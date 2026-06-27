"""Zero-dependency local server for the unified Dev Swarm FleetView."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Tuple

from fleet import unified_snapshot

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class FleetHandler(BaseHTTPRequestHandler):
    server_version = "DevSwarmFleet/3.0"

    def log_message(self, fmt: str, *args: Tuple) -> None:
        print(f"[fleet] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/context":
            from config import get_runtime

            self._json(get_runtime())
            return
        if path == "/api/fleet":
            self._json(unified_snapshot())
            return
        if path == "/api/fleet/active":
            self._json(unified_snapshot(active_only=True))
            return
        if path == "/api/kb":
            from dev_swarm import kb_catalog

            self._json(kb_catalog())
            return
        if path == "/api/teams":
            from dev_swarm import teams_snapshot

            self._json({"teams": teams_snapshot()})
            return
        if path == "/api/graph/diagram":
            import json as _json
            from graph_viz import graph_diagram

            active = None
            pipeline = None
            router_method = None
            from config import FLEET_STATE

            if FLEET_STATE.exists():
                try:
                    state = _json.loads(FLEET_STATE.read_text(encoding="utf-8"))
                    run = next(
                        (r for r in state.get("runs", []) if r.get("status") == "running"),
                        state.get("runs", [{}])[0] if state.get("runs") else None,
                    )
                    if run:
                        active = run.get("active_graph_node")
                        pipeline = run.get("pipeline")
                        router_method = run.get("router_method")
                except _json.JSONDecodeError:
                    pass
            self._json(graph_diagram(active_node=active, pipeline=pipeline, router_method=router_method))
            return
        if path == "/api/graph":
            try:
                from langgraph_orchestrator import graph_structure

                self._json(graph_structure())
            except ImportError:
                from dev_swarm import graph_structure

                self._json(graph_structure())
            return
        if path == "/api/agents":
            from agents_registry import AGENTS, GRAPH_NODES, TEAMS as ORCH_TEAMS

            self._json({"teams": ORCH_TEAMS, "agents": AGENTS, "graph_nodes": GRAPH_NODES})
            return
        if path == "/api/usage":
            from usage_tracker import usage_summary

            self._json(usage_summary())
            return
        if path == "/api/swarm/status":
            from swarm_runner import swarm_status

            self._json(swarm_status())
            return
        if path == "/api/skill/feeds":
            from skill_feed_registry import feed_registry_snapshot

            self._json(feed_registry_snapshot())
            return
        if path == "/api/cursor-fleet":
            from cursor_fleet import cursor_fleet_snapshot

            self._json(cursor_fleet_snapshot())
            return
        if path == "/api/skill/sync":
            # SSE stream — EventSource uses GET; emits live progress lines
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def _emit(msg: str) -> None:
                line = f"data: {json.dumps({'msg': msg})}\n\n"
                try:
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
                except Exception:  # noqa: BLE001
                    pass

            try:
                _emit("⏳ Starting skill-refresh …")
                from skill_sync import refresh_skill_manifest
                _emit("📋 Syncing skill manifest …")
                result = refresh_skill_manifest()
                skill_rows = result.get("skills", []) if isinstance(result, dict) else []
                if isinstance(skill_rows, list):
                    for row in skill_rows:
                        if not isinstance(row, dict):
                            continue
                        present = row.get("kb_present", 0)
                        total = row.get("kb_links", 0)
                        _emit(f"  ✅ {row.get('skill','?')} — {present}/{total} KB paths present")
                _emit("📂 Writing per-skill feed docs …")
                from skill_feed_registry import refresh_skill_open_feeds
                feed_result = refresh_skill_open_feeds(force=False)
                skill_list = feed_result.get("skills", []) if isinstance(feed_result, dict) else []
                if isinstance(skill_list, list):
                    for s in skill_list:
                        if not isinstance(s, dict):
                            continue
                        topics = s.get("open_topics", 0)
                        codebase = s.get("codebase", 0)
                        # open_topics/codebase may be int (count) or list — handle both
                        t = len(topics) if isinstance(topics, list) else int(topics)
                        c = len(codebase) if isinstance(codebase, list) else int(codebase)
                        _emit(f"  📄 {s.get('skill','?')} — {t} open topics, {c} codebase feeds")
                manifest_path = result.get("manifest_path", "") if isinstance(result, dict) else ""
                _emit(f"✅ Done — manifest at {manifest_path}" if manifest_path else "✅ Skill sync complete")
                _emit("__DONE__")
            except Exception as exc:  # noqa: BLE001
                _emit(f"❌ Error: {exc}")
                _emit("__DONE__")
            return
        if path in ("/skills-fleet.html", "/skills"):
            self._file(STATIC / "skills-fleet.html", "text/html; charset=utf-8")
            return
        if path in ("/", "/index.html", "/swarm-fleet.html", "/dev-swarm.html"):
            self._file(STATIC / "dev-swarm.html", "text/html; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/swarm/run":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}
            from swarm_runner import start_swarm_background

            result = start_swarm_background(
                force=bool(payload.get("force")),
                deep=bool(payload.get("deep")),
                team_ids=payload.get("teams"),
            )
            self._json(result)
            return
        if path == "/api/orchestrate":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}
            user_input = (payload.get("input") or payload.get("user_input") or "").strip()
            if not user_input:
                self._json({"ok": False, "error": "Missing input — provide { \"input\": \"your request\" }"})
                return
            from swarm_runner import start_orchestrator_background

            result = start_orchestrator_background(user_input)
            self._json(result)
            return
        if path == "/api/skill/sync":
            # POST kept for backward compat — live stream is on GET /api/skill/sync
            self._json({"ok": True, "note": "Use GET /api/skill/sync for live SSE stream"})
            return
        self.send_error(404)

    def _json(self, data: dict) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            legacy = STATIC / "swarm-fleet.html"
            if legacy.is_file():
                self._file(legacy, content_type)
                return
            self.send_error(404, f"missing {path.name}")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    from config import FLEET_STATE, init_runtime

    ctx = init_runtime(force=True)
    print(f"Project: {ctx.get('projectName')} · org: {ctx.get('targetOrgAlias')}")
    print(f"Fleet state: {FLEET_STATE}")
    try:
        server = ThreadingHTTPServer((host, port), FleetHandler)
    except OSError as exc:
        print(f"ERROR: Cannot bind {host}:{port} — {exc}")
        print("Try: lsof -ti:8765 | xargs kill -9   then run again")
        raise SystemExit(1) from exc

    url = f"http://{host}:{port}/"
    if host == "0.0.0.0":
        url = f"http://127.0.0.1:{port}/"
    print("==============================================")
    print(" Multi-Agent Dev Swarm FleetView is RUNNING")
    print(f" Open: {url}")
    print(" Keep this terminal open. Ctrl+C to stop.")
    print("==============================================")

    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev Swarm FleetView")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
