#!/usr/bin/env bash
# Sync Salesforce metadata: full retrieve (empty local) or delta retrieve (local vs org).
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAIT_MINUTES=120

TARGET_ORG=""
PROJECT_ROOT_OVERRIDE=""
MODE="auto"
PREVIEW_ONLY=false
IGNORE_CONFLICTS=false

usage() {
  cat <<EOF
Usage: sync-metadata.sh [OPTIONS]

Automatically retrieve Salesforce metadata from an org into a Salesforce DX project.

Options:
  -o, --target-org <alias>     Target org alias or username (default: sf config target-org)
  -r, --project-root <path>    Project root (default: walk up from cwd for sfdx-project.json)
  -f, --full                   Force full retrieve even if local has files
  -p, --preview-only           Preview delta only; do not retrieve
  -c, --ignore-conflicts       Pass --ignore-conflicts to retrieve commands
  -h, --help                   Show this help

Examples:
  sync-metadata.sh
  sync-metadata.sh --target-org my-sandbox
  sync-metadata.sh --full --target-org prod
  sync-metadata.sh --preview-only
EOF
}

log() { printf '[metadata-sync] %s\n' "$*"; }
die() { printf '[metadata-sync] ERROR: %s\n' "$*" >&2; exit 1; }

find_project_root() {
  if [[ -n "$PROJECT_ROOT_OVERRIDE" ]]; then
    echo "$PROJECT_ROOT_OVERRIDE"
    return 0
  fi
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/sfdx-project.json" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--target-org) TARGET_ORG="$2"; shift 2 ;;
    -r|--project-root) PROJECT_ROOT_OVERRIDE="$2"; shift 2 ;;
    -f|--full) MODE="full"; shift ;;
    -p|--preview-only) PREVIEW_ONLY=true; shift ;;
    -c|--ignore-conflicts) IGNORE_CONFLICTS=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

PROJECT_ROOT="$(find_project_root)" || die "Could not find sfdx-project.json. Run from a Salesforce DX project or pass --project-root."

# Resolve source path + org from shared context (folder + sf CLI)
CONTEXT_JSON="$(python3 "$HOME/.cursor/skills/_shared/show-context.py" ${TARGET_ORG:+"$TARGET_ORG"} 2>/dev/null || true)"
if [[ -n "$CONTEXT_JSON" ]]; then
  SOURCE_REL="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sourcePath','force-app/main/default'))" <<<"$CONTEXT_JSON")"
  if [[ -z "$TARGET_ORG" ]]; then
    DETECTED_ORG="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('targetOrgAlias',''))" <<<"$CONTEXT_JSON")"
    if [[ -n "$DETECTED_ORG" ]]; then TARGET_ORG="$DETECTED_ORG"; fi
  fi
else
  SOURCE_REL="force-app/main/default"
fi

FORCE_APP="$PROJECT_ROOT/$SOURCE_REL"
BATCHES_DIR="$PROJECT_ROOT/manifest/batches"
FULL_MANIFEST="$PROJECT_ROOT/manifest/package.xml"
DELTA_MANIFEST="$PROJECT_ROOT/manifest/delta-package.xml"
PREVIEW_JSON="$PROJECT_ROOT/manifest/.retrieve-preview.json"

cd "$PROJECT_ROOT"
log "Project root: $PROJECT_ROOT"

if ! command -v sf >/dev/null 2>&1; then
  die "Salesforce CLI (sf) not found. Install: https://developer.salesforce.com/tools/salesforcecli"
fi

if [[ -n "$TARGET_ORG" ]]; then
  log "Target org: $TARGET_ORG"
else
  DEFAULT_ORG="$(sf config get target-org --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result',[{}])[0].get('value',''))" 2>/dev/null || true)"
  if [[ -n "$DEFAULT_ORG" ]]; then
    log "Using default target org: $DEFAULT_ORG"
  else
    die "No target org specified. Use --target-org or set default: sf config set target-org <alias>"
  fi
fi

sf_retrieve_start() {
  local manifest="$1"
  local cmd=(sf project retrieve start --manifest "$manifest" --wait "$WAIT_MINUTES")
  if [[ -n "$TARGET_ORG" ]]; then
    cmd+=(--target-org "$TARGET_ORG")
  fi
  if [[ "$IGNORE_CONFLICTS" == true ]]; then
    cmd+=(--ignore-conflicts)
  fi
  "${cmd[@]}"
}

sf_retrieve_preview() {
  local cmd=(sf project retrieve preview --json --concise)
  if [[ -n "$TARGET_ORG" ]]; then
    cmd+=(--target-org "$TARGET_ORG")
  fi
  "${cmd[@]}"
}

is_local_empty() {
  if [[ ! -d "$FORCE_APP" ]]; then
    return 0
  fi
  local count
  count="$(find "$FORCE_APP" -name '*-meta.xml' 2>/dev/null | head -1 | wc -l | tr -d ' ')"
  [[ "$count" -eq 0 ]]
}

run_full_retrieve() {
  log "Starting FULL metadata retrieve (batched)..."

  local batches=()
  if [[ -d "$BATCHES_DIR" ]]; then
    while IFS= read -r batch; do
      batches+=("$batch")
    done < <(find "$BATCHES_DIR" -maxdepth 1 -name 'package-*.xml' | sort)
  fi

  if [[ ${#batches[@]} -eq 0 ]]; then
    log "No batch manifests found. Using manifest/package.xml"
    sf_retrieve_start "$FULL_MANIFEST"
    return
  fi

  local total=${#batches[@]}
  local i=0
  for batch in "${batches[@]}"; do
    i=$((i + 1))
    local batch_name
    batch_name="$(basename "$batch")"
    local log_file="$BATCHES_DIR/log-${batch_name%.xml}.txt"
    log "Batch $i/$total: $batch_name"
    sf_retrieve_start "$batch" 2>&1 | tee "$log_file"
  done

  log "Full retrieve complete ($total batches)."
}

run_delta_preview() {
  log "Running retrieve preview (local vs org)..."
  sf_retrieve_preview > "$PREVIEW_JSON"

  python3 "$SCRIPT_DIR/build-delta-package.py" \
    "$PREVIEW_JSON" \
    "$DELTA_MANIFEST" \
    "$PROJECT_ROOT"
}

run_delta_retrieve() {
  run_delta_preview

  if [[ ! -s "$DELTA_MANIFEST" ]]; then
    log "No delta — local metadata matches org."
    return
  fi

  local count
  count="$(python3 -c "import json; d=json.load(open('$PROJECT_ROOT/manifest/delta-report.json')); print(d['toRetrieveCount'])")"
  log "Retrieving $count delta component(s)..."
  sf_retrieve_start "$DELTA_MANIFEST"
  log "Delta retrieve complete."
}

# --- Main ---

if [[ "$MODE" == "auto" ]] && is_local_empty; then
  MODE="full"
  log "Local force-app is empty — using full retrieve mode."
elif [[ "$MODE" == "auto" ]]; then
  MODE="delta"
  log "Local metadata found — using delta retrieve mode."
fi

if [[ "$PREVIEW_ONLY" == true ]]; then
  run_delta_preview
  log "Preview only — no retrieve performed."
  exit 0
fi

case "$MODE" in
  full) run_full_retrieve ;;
  delta) run_delta_retrieve ;;
  *) die "Unknown mode: $MODE" ;;
esac
