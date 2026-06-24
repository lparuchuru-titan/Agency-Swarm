#!/bin/zsh -l
# Install Agency-Swarm globally (~/.cursor/sfdc-knowledge-swarm + sfdc-swarm CLI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/framework/install-global.sh"
