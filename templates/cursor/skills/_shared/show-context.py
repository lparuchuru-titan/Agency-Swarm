#!/usr/bin/env python3
"""Print resolved Salesforce project context for the current folder."""

import json
import sys
from pathlib import Path

SHARED = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARED))

from sfdc_context import resolve_context  # noqa: E402

override = None
if len(sys.argv) > 1 and sys.argv[1] not in ("-h", "--help"):
    override = sys.argv[1]

ctx = resolve_context(target_org_override=override)
print(json.dumps(ctx, indent=2))
