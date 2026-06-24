"""Generate a safe filename slug from a question string."""
from __future__ import annotations

import re
import sys
from datetime import datetime


def slugify(text: str, max_len: int = 60) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len] or "explanation"


def default_output_path(question: str, output_dir: str = "docs/explainers") -> str:
    date = datetime.now().strftime("%Y%m%d")
    return f"{output_dir}/{date}-{slugify(question)}.html"


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "explanation"
    print(default_output_path(q))
