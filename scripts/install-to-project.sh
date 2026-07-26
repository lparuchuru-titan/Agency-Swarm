#!/bin/zsh -l
# Wire Agency-Swarm into a Salesforce DX project (symlink framework + copy Cursor templates).
#
# Usage:
#   ./scripts/install-to-project.sh                    # current directory
#   ./scripts/install-to-project.sh /path/to/your-sfdx-project
#   ./scripts/install-to-project.sh --global-skills    # also refresh ~/.cursor/skills
set -euo pipefail

AGENCY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GLOBAL_SKILLS=0
TARGET="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global-skills) GLOBAL_SKILLS=1; shift ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

TARGET="$(cd "$TARGET" && pwd)"

if [[ ! -f "$TARGET/sfdx-project.json" ]]; then
  echo "Not a Salesforce DX project (missing sfdx-project.json): $TARGET"
  exit 1
fi

echo "Agency-Swarm → $TARGET"

# Framework: symlink into tools/sfdc-knowledge-swarm (standard path for wired projects)
mkdir -p "$TARGET/tools"
if [[ -e "$TARGET/tools/sfdc-knowledge-swarm" && ! -L "$TARGET/tools/sfdc-knowledge-swarm" ]]; then
  echo "WARN: $TARGET/tools/sfdc-knowledge-swarm exists as a directory (not a symlink)."
  echo "      Back it up manually, then re-run. Skipping framework link."
else
  ln -sfn "$AGENCY_ROOT/framework" "$TARGET/tools/sfdc-knowledge-swarm"
  echo "Linked tools/sfdc-knowledge-swarm → Agency-Swarm/framework"
fi

# Cursor agency layout
mkdir -p "$TARGET/.cursor/agency" "$TARGET/.cursor/agents" "$TARGET/.cursor/rules" "$TARGET/.cursor/swarm/.fleet"
rsync -a "$AGENCY_ROOT/templates/cursor/agency/" "$TARGET/.cursor/agency/"
rsync -a "$AGENCY_ROOT/templates/cursor/agents/" "$TARGET/.cursor/agents/"
rsync -a "$AGENCY_ROOT/templates/cursor/rules/" "$TARGET/.cursor/rules/"

# AGENTS.md entry point
if [[ ! -f "$TARGET/AGENTS.md" ]]; then
  cp "$AGENCY_ROOT/templates/project/AGENTS.md" "$TARGET/AGENTS.md"
  echo "Created AGENTS.md"
else
  echo "Kept existing AGENTS.md (compare with templates/project/AGENTS.md)"
fi

# Optional project topics stub
if [[ ! -f "$TARGET/.cursor/swarm/project-topics.json" ]]; then
  if [[ -f "$AGENCY_ROOT/templates/project/project-topics.example.json" ]]; then
    cp "$AGENCY_ROOT/templates/project/project-topics.example.json" "$TARGET/.cursor/swarm/project-topics.json"
  fi
fi

# Per-project KB + delivery folders (runtime output)
mkdir -p "$TARGET/knowledge-base" "$TARGET/docs/swarm-deliveries"

# Global CLI + ~/.cursor/sfdc-knowledge-swarm
"$AGENCY_ROOT/framework/install-global.sh"

# Skills → ~/.cursor/skills (shared across all SFDC projects)
if [[ "$GLOBAL_SKILLS" -eq 1 ]]; then
  "$AGENCY_ROOT/scripts/install-skills.sh"
fi

echo ""
echo "Done. From $TARGET:"
echo "  sfdc-swarm context"
echo "  sfdc-swarm serve"
echo "  sfdc-swarm orchestrate \"your request\""
echo ""
echo "Tip: run with --global-skills to refresh ~/.cursor/skills from templates."
