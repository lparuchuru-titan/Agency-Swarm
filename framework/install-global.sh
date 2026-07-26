#!/bin/zsh -l
# Install Agency-Swarm framework globally for all Cursor Salesforce projects.
# Source of truth: https://github.com/lparuchuru-titan/Agency-Swarm
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"

echo "Installing Agency-Swarm framework to $DEST"

mkdir -p "$DEST"
rsync -a \
  --exclude 'knowledge-base' \
  --exclude '.fleet' \
  --exclude '*.log' \
  --exclude '.git' \
  "$SRC/" "$DEST/"

chmod +x "$DEST/run.sh" 2>/dev/null || true
chmod +x "$DEST/launchd/"*.sh 2>/dev/null || true
chmod +x "$DEST/install-global.sh" 2>/dev/null || true

# Global CLI shim
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/sfdc-swarm" <<'EOF'
#!/bin/zsh -l
export SFDC_SWARM_HOME="${SFDC_SWARM_HOME:-$HOME/.cursor/sfdc-knowledge-swarm}"
if [[ ! -d "$SFDC_SWARM_HOME" ]]; then
  echo "Run Agency-Swarm/install.sh or framework/install-global.sh first."
  exit 1
fi
export SFDC_SWARM_PROJECT_ROOT="${SFDC_SWARM_PROJECT_ROOT:-$(pwd)}"
exec python3 "$SFDC_SWARM_HOME/run.py" "$@"
EOF
chmod +x "$BIN_DIR/sfdc-swarm"

echo ""
echo "Installed. From any Salesforce DX project:"
echo "  sfdc-swarm context"
echo "  sfdc-swarm orchestrate \"your request\""
echo "  sfdc-swarm skill-refresh --tier weekly"
echo ""
echo "Or per-repo wrapper:"
echo "  ./tools/sfdc-knowledge-swarm/run.sh context"
echo ""
echo "Optional launchd (all projects):"
echo "  cp $DEST/launchd/com.agency-swarm.skill-refresh-all.plist ~/Library/LaunchAgents/"
echo "  launchctl load ~/Library/LaunchAgents/com.agency-swarm.skill-refresh-all.plist"
