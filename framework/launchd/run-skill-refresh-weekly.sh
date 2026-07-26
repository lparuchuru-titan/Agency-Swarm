#!/bin/zsh -l
# Weekly skill refresh — connected indexes + open doc static fetch (0 tokens).
set -euo pipefail

REPO="${AGENCY_SWARM_PROJECT_REPO:-/path/to/your-sfdx-project}"
LOG="$REPO/tools/sfdc-knowledge-swarm/skill-refresh-weekly.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') weekly skill refresh =====" >> "$LOG"
python3 run.py skill-refresh --tier weekly >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') weekly done =====" >> "$LOG"
