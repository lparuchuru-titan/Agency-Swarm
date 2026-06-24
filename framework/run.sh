#!/bin/zsh -l
# Run the global SFDC agent swarm CLI from any Salesforce DX project.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

export SFDC_SWARM_PROJECT_ROOT="$PROJECT_ROOT"
export SFDC_SWARM_HOME="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"

if [[ ! -d "$SFDC_SWARM_HOME" ]]; then
  echo "Global swarm not installed. Run: $SCRIPT_DIR/install-global.sh"
  exit 1
fi

cd "$PROJECT_ROOT"
exec python3 "$SFDC_SWARM_HOME/run.py" "$@"
