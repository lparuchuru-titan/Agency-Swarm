#!/bin/zsh -l
# Copy Cursor skill templates to ~/.cursor/skills (global install).
set -euo pipefail

AGENCY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${CURSOR_SKILLS_HOME:-$HOME/.cursor/skills}"

SKILLS=(
  advanced-salesforce-developer
  sfdc-metadata-sync
  sfdc-promotion-workflow
  jira-subtask-workflow
  playwright-e2e-validation
  codebase-explainer
  sfdc-cta-mentor
  pr-reviewer
  org-analyst
  reverse-engineer
  apex-space-reclaimer
  cpq-qle-validation
  sfdc-qcp-editor
)

mkdir -p "$DEST"
rsync -a "$AGENCY_ROOT/templates/cursor/skills/_shared/" "$DEST/_shared/"

for skill in "${SKILLS[@]}"; do
  rsync -a "$AGENCY_ROOT/templates/cursor/skills/$skill/" "$DEST/$skill/"
  echo "Installed skill: $skill"
done

echo "Skills installed to $DEST"
