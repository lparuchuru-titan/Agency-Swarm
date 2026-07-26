#!/bin/zsh -l
# Scheduled Dev Development Swarm — codebase KB for all three teams (no API key required).
set -euo pipefail

REPO="${AGENCY_SWARM_PROJECT_REPO:-/path/to/your-sfdx-project}"
LOG="$REPO/tools/sfdc-knowledge-swarm/dev-swarm.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') dev swarm starting =====" >> "$LOG"

python3 run.py dev-once >> "$LOG" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') dev swarm finished =====" >> "$LOG"
