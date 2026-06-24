#!/bin/zsh -l
# Start Multi-Agent FleetView (kills stale server on port 8765 first).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PORT="${FLEET_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/"

export SFDC_SWARM_PROJECT_ROOT="$PROJECT_ROOT"
export SFDC_SWARM_HOME="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"

if [[ ! -d "$SFDC_SWARM_HOME" ]]; then
  echo "Global swarm not installed. Run: $SCRIPT_DIR/install-global.sh"
  exit 1
fi

# Stop old FleetView on this port
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "Stopping existing server on port $PORT…"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

cd "$PROJECT_ROOT"
exec python3 "$SFDC_SWARM_HOME/serve_fleet.py" --host 127.0.0.1 --port "$PORT"
