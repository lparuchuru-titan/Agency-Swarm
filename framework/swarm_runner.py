"""Background swarm runner for FleetView UI."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

_lock = threading.Lock()
_running = False
_last_error: Optional[str] = None
_orchestrator_input: Optional[str] = None


def swarm_is_running() -> bool:
    with _lock:
        return _running


def start_swarm_background(
    force: bool = False,
    deep: bool = False,
    team_ids: Optional[list] = None,
) -> Dict[str, Any]:
    global _running, _last_error
    with _lock:
        if _running:
            return {"ok": False, "error": "Swarm already running"}
        _running = True
        _last_error = None

    def worker() -> None:
        global _running, _last_error
        try:
            from config import init_runtime

            init_runtime(force=True)
            from langgraph_dev_swarm import run_langgraph_dev_swarm

            run_langgraph_dev_swarm(team_ids=team_ids, force=force, deep=deep)
        except Exception as exc:  # noqa: BLE001
            _last_error = str(exc)
        finally:
            with _lock:
                _running = False

    threading.Thread(target=worker, name="dev-swarm", daemon=True).start()
    return {"ok": True, "status": "started", "message": "LangGraph codebase swarm running — watch agents below"}


def start_orchestrator_background(user_input: str) -> Dict[str, Any]:
    global _running, _last_error, _orchestrator_input
    with _lock:
        if _running:
            return {"ok": False, "error": "Orchestrator already running"}
        _running = True
        _last_error = None
        _orchestrator_input = user_input

    def worker() -> None:
        global _running, _last_error
        run_id: Optional[str] = None
        try:
            from config import init_runtime

            init_runtime(force=True)
            from langgraph_orchestrator import run_orchestrator

            result = run_orchestrator(user_input)
            run_id = result.get("run_id")
        except Exception as exc:  # noqa: BLE001
            _last_error = str(exc)
            if run_id:
                from fleet_hooks import mark_run_failed

                mark_run_failed(run_id, str(exc))
        finally:
            with _lock:
                _running = False

    threading.Thread(target=worker, name="agent-orchestrator", daemon=True).start()
    return {
        "ok": True,
        "status": "started",
        "message": "Supervisor orchestrator running — agents executing in pipeline",
    }


def swarm_status() -> Dict[str, Any]:
    with _lock:
        status = {
            "worker_running": _running,
            "last_error": _last_error,
            "orchestrator_input": _orchestrator_input,
        }
    from fleet_hooks import is_run_active

    status["fleet_run_active"] = is_run_active()
    return status
