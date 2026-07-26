#!/bin/zsh -l
# Headless, unattended run of the SFDC Knowledge Swarm under your Claude Code login.
# No API key — uses your existing `claude` authentication.
set -euo pipefail

REPO="${AGENCY_SWARM_PROJECT_REPO:-/path/to/your-sfdx-project}"
LOG="$REPO/tools/sfdc-knowledge-swarm/swarm.log"
CLAUDE="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

cd "$REPO"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') swarm run starting =====" >> "$LOG"

# acceptEdits lets the research agents write KB notes without prompting.
# Web tools are read-only. If a run stalls on a permission prompt, switch to
# --dangerously-skip-permissions (understand the risk first).
"$CLAUDE" -p "Run the sfdc-knowledge-swarm workflow (full refresh of all topics). Use the Workflow tool with the saved script at .claude/workflows/sfdc-knowledge-swarm.js." \
  --permission-mode acceptEdits \
  >> "$LOG" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') swarm run finished =====" >> "$LOG"
