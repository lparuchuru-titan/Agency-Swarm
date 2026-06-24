# Metadata Sync Scripts

## sync-metadata.sh

Main entry point. Auto-detects full vs delta mode and runs the appropriate retrieve workflow.

```bash
chmod +x .cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh
./.cursor/skills/sfdc-metadata-sync/scripts/sync-metadata.sh --target-org <alias>
```

## build-delta-package.py

Parses `sf project retrieve preview --json` output and generates:
- `manifest/delta-package.xml` — manifest for delta retrieve
- `manifest/delta-report.json` — structured report (counts, conflicts, local-only changes)

Used automatically by `sync-metadata.sh` during delta mode.
