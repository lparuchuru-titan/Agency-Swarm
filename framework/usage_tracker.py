"""Track LLM token usage and estimated USD cost for swarm runs."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import FLEET_DIR, SWARM_MODEL, ensure_dirs

_lock = threading.Lock()
USAGE_FILE = FLEET_DIR / "usage.json"

# USD per 1M tokens (approximate — update if pricing changes)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "default": {"input": 3.0, "output": 15.0},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pricing(model: str) -> Dict[str, float]:
    return MODEL_PRICING.get(model, MODEL_PRICING["default"])


def estimate_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = _pricing(model)
    return round((input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000, 6)


def extract_tokens_from_message(msg: Any) -> tuple[int, int]:
    """Pull token counts from LangChain AIMessage usage_metadata."""
    input_tokens = 0
    output_tokens = 0
    meta = getattr(msg, "usage_metadata", None) or getattr(msg, "response_metadata", {}).get("usage", {})
    if meta:
        input_tokens = int(meta.get("input_tokens", meta.get("prompt_tokens", 0)) or 0)
        output_tokens = int(meta.get("output_tokens", meta.get("completion_tokens", 0)) or 0)
    if not input_tokens and not output_tokens and hasattr(msg, "content"):
        # rough fallback when provider omits usage
        text = str(msg.content)
        output_tokens = max(len(text) // 4, 0)
        input_tokens = max(output_tokens * 2, 100)
    return input_tokens, output_tokens


def record_llm_call(
    source: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    run_id: Optional[str] = None,
    note: str = "",
) -> Dict[str, Any]:
    ensure_dirs()
    entry = {
        "at": _now(),
        "source": source,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "usd": estimate_usd(model, input_tokens, output_tokens),
        "run_id": run_id,
        "note": note,
    }
    with _lock:
        data = _load()
        data.setdefault("events", []).insert(0, entry)
        data["events"] = data["events"][:500]
        data["updated"] = _now()
        _save(data)
    return entry


def record_from_message(
    source: str,
    model: str,
    msg: Any,
    run_id: Optional[str] = None,
    note: str = "",
) -> Dict[str, Any]:
    inp, out = extract_tokens_from_message(msg)
    return record_llm_call(source, model, inp, out, run_id=run_id, note=note)


def _load() -> Dict[str, Any]:
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"events": [], "updated": None}


def _save(data: Dict[str, Any]) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def usage_for_run(run_id: str) -> Dict[str, Any]:
    events = [e for e in _load().get("events", []) if e.get("run_id") == run_id]
    usd = sum(e.get("usd", 0) for e in events)
    inp = sum(e.get("input_tokens", 0) for e in events)
    out = sum(e.get("output_tokens", 0) for e in events)
    return {"run_id": run_id, "usd": round(usd, 4), "input_tokens": inp, "output_tokens": out, "calls": len(events)}


def usage_summary() -> Dict[str, Any]:
    import os

    events = _load().get("events", [])
    total_usd = sum(e.get("usd", 0) for e in events)
    total_in = sum(e.get("input_tokens", 0) for e in events)
    total_out = sum(e.get("output_tokens", 0) for e in events)
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    month_events = [e for e in events if str(e.get("at", "")).startswith(month_prefix)]
    month_usd = sum(e.get("usd", 0) for e in month_events)

    return {
        "total_usd": round(total_usd, 4),
        "month_usd": round(month_usd, 4),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "llm_calls": len(events),
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "model": SWARM_MODEL,
        "recent": events[:12],
        "pricing_note": "Estimates based on Anthropic Sonnet list pricing; actual billing may differ.",
    }
