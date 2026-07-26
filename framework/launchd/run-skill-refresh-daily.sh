#!/bin/zsh -l
# Daily skill refresh — codebase static scan + skill manifest (0 tokens).
set -euo pipefail

REPO="${AGENCY_SWARM_PROJECT_REPO:-/path/to/your-sfdx-project}"
LOG="$REPO/tools/sfdc-knowledge-swarm/skill-refresh-daily.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily skill refresh =====" >> "$LOG"
python3 run.py skill-refresh --tier daily >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily done =====" >> "$LOG"
