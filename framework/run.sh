#!/bin/zsh -l
# Run the Agency-Swarm CLI. Prefer an SFDX project root; fall back to cwd.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

find_sfdx_root() {
  local dir="$1"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/sfdx-project.json" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# 1) Explicit override
# 2) Walk up from cwd
# 3) Walk up from symlink location (tools/sfdc-knowledge-swarm → project)
# 4) cwd
if [[ -n "${SFDC_SWARM_PROJECT_ROOT:-}" && -f "${SFDC_SWARM_PROJECT_ROOT}/sfdx-project.json" ]]; then
  PROJECT_ROOT="$(cd "$SFDC_SWARM_PROJECT_ROOT" && pwd)"
elif PROJECT_ROOT="$(find_sfdx_root "$(pwd)")"; then
  :
elif PROJECT_ROOT="$(find_sfdx_root "$SCRIPT_DIR")"; then
  :
else
  echo "No sfdx-project.json found. cd into a Salesforce DX project or set SFDC_SWARM_PROJECT_ROOT." >&2
  exit 2
fi

export SFDC_SWARM_PROJECT_ROOT="$PROJECT_ROOT"
export SFDC_SWARM_HOME="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"

# Prefer local framework (this script's directory) over global install when present
RUN_PY="$SCRIPT_DIR/run.py"
if [[ ! -f "$RUN_PY" && -f "$SFDC_SWARM_HOME/run.py" ]]; then
  RUN_PY="$SFDC_SWARM_HOME/run.py"
fi

cd "$PROJECT_ROOT"
exec python3 "$RUN_PY" "$@"
