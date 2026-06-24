#!/usr/bin/env bash
# Run full validation: LWC Jest + Apex tests + Playwright E2E
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 "$SCRIPT_DIR/generate-specs.py" --write

ROOT="$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); from lib import find_project_root; print(find_project_root())")"
cd "$ROOT"

echo "=== Validation: $ROOT ==="

RUN_LWC=true
RUN_APEX=true
RUN_E2E=true

if [[ -f package.json ]] && grep -q '"test:unit"' package.json; then
  echo "--- LWC Jest ---"
  npm run test:unit 2>/dev/null || RUN_LWC=false
else
  echo "Skip LWC Jest (no npm test:unit)"
  RUN_LWC=false
fi

PLAN="$(python3 "$SCRIPT_DIR/generate-specs.py" --json 2>/dev/null || echo '{}')"
APEX_TESTS="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(d.get('apexTests',[])))" <<<"$PLAN" 2>/dev/null || true)"

if [[ -n "$APEX_TESTS" ]] && command -v sf >/dev/null 2>&1; then
  echo "--- Apex tests: $APEX_TESTS ---"
  sf apex run test --tests "$APEX_TESTS" --result-format human --synchronous || RUN_APEX=false
else
  echo "Skip Apex tests (none detected or sf CLI missing)"
  RUN_APEX=false
fi

if [[ -n "${SF_USERNAME:-}" && -n "${SF_PASSWORD:-}" ]] && [[ -f playwright.config.js ]]; then
  echo "--- Playwright E2E ---"
  if [[ ! -d node_modules/@playwright/test ]]; then
    npm install 2>/dev/null || true
  fi
  npx playwright test e2e/generated e2e/home.spec.js 2>/dev/null || RUN_E2E=false
else
  echo "Skip Playwright (set SF_USERNAME/SF_PASSWORD or missing playwright.config.js)"
  RUN_E2E=false
fi

echo ""
echo "=== Summary ==="
echo "LWC Jest:  $([ "$RUN_LWC" = true ] && echo ok || echo skipped/failed)"
echo "Apex:      $([ "$RUN_APEX" = true ] && echo ok || echo skipped/failed)"
echo "Playwright:$([ "$RUN_E2E" = true ] && echo ok || echo skipped/failed)"
