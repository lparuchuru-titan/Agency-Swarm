#!/bin/zsh -l
# Daily skill refresh — codebase static scan + skill manifest (0 tokens).
set -euo pipefail

REPO="/Users/lakshmikanthparuchuru/SFDC/SFDC NextGen2/NEXTGEN2"
LOG="$REPO/tools/sfdc-knowledge-swarm/skill-refresh-daily.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily skill refresh =====" >> "$LOG"
python3 run.py skill-refresh --tier daily >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily done =====" >> "$LOG"
