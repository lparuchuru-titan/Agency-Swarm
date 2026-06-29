#!/bin/bash
# Start FleetView — run this ONCE in your own Terminal (not Cursor chat).
# It stays running until you close the Terminal tab or press Ctrl+C.
#
# Reads CURSOR_API_KEY from:
#   1. Environment (export CURSOR_API_KEY=cursor_...)
#   2. .env file in project root
#   3. ~/.cursor/swarm.env

set -e
cd "$(dirname "$0")"

# Load API key from .env files if not already in environment
if [ -z "$CURSOR_API_KEY" ]; then
  for env_file in ".env" "$HOME/.cursor/swarm.env"; do
    if [ -f "$env_file" ]; then
      export $(grep -v '^#' "$env_file" | grep CURSOR_API_KEY | xargs) 2>/dev/null
      [ -n "$CURSOR_API_KEY" ] && echo "Loaded CURSOR_API_KEY from $env_file" && break
    fi
  done
fi

if [ -z "$CURSOR_API_KEY" ]; then
  echo "⚠️  CURSOR_API_KEY not set."
  echo "   Set it via: export CURSOR_API_KEY=cursor_..."
  echo "   Or create a .env file with: CURSOR_API_KEY=cursor_..."
  echo "   Get your key at: cursor.com/dashboard/integrations"
  echo "   Continuing without it — set it in FleetView UI after launch."
fi

# Kill any stale instance
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
sleep 1

echo "=============================================="
echo "  SFDC Agent Swarm — FleetView"
echo "  http://127.0.0.1:8765/dev-swarm.html"
echo "  Org: $(sf config get target-org --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get(\"result\",[{}])[0].get(\"value\",\"—\"))' 2>/dev/null || echo '—')"
echo "  Press Ctrl+C to stop"
echo "=============================================="

python3 ~/.cursor/sfdc-knowledge-swarm/serve_fleet.py
