#!/bin/zsh -l
# Deep E2E validation for Agency-Swarm. Exit 0 only when all checks pass.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Checking Python deps (import langgraph/rich)…"
python3 - <<'PY'
import importlib
for m in ("rich", "langgraph", "langchain_core"):
    importlib.import_module(m)
    print(" ", m, "ok")
PY

echo "→ Running deep test suite…"
python3 tests/test_framework.py
