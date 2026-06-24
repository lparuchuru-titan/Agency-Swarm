#!/bin/zsh -l
# Weekly skill refresh — connected indexes + open doc static fetch (0 tokens).
set -euo pipefail

REPO="/Users/lakshmikanthparuchuru/SFDC/SFDC NextGen2/NEXTGEN2"
LOG="$REPO/tools/sfdc-knowledge-swarm/skill-refresh-weekly.log"
cd "$REPO/tools/sfdc-knowledge-swarm"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') weekly skill refresh =====" >> "$LOG"
python3 run.py skill-refresh --tier weekly >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') weekly done =====" >> "$LOG"
