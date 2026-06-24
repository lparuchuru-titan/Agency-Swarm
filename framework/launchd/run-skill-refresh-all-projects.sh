#!/bin/zsh -l
# Daily skill refresh for every registered Salesforce DX project.
set -euo pipefail

SWARM_HOME="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"
LOG="$SWARM_HOME/skill-refresh-all.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') all-projects daily =====" >> "$LOG"
cd "$SWARM_HOME"
python3 run.py skill-refresh-all --tier daily >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') done =====" >> "$LOG"
