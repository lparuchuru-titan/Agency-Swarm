#!/bin/zsh -l
# Monthly deep check — LLM synthesis for stale open docs only (max 2 topics by default).
set -euo pipefail

REPO="${AGENCY_SWARM_PROJECT_REPO:-/path/to/your-sfdx-project}"
LOG="$REPO/tools/sfdc-knowledge-swarm/skill-refresh-monthly.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') monthly deep check =====" >> "$LOG"
python3 run.py skill-refresh --tier monthly >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') monthly done =====" >> "$LOG"
