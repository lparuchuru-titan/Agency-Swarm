"""Fetch Salesforce docs and web snippets for swarm agents."""
from __future__ import annotations

import re
from html import unescape
from typing import Dict, List, Tuple

import httpx

from config import TOPICS

USER_AGENT = "SFDC-Knowledge-Swarm/1.0 (+local research bot)"
TIMEOUT = 25.0
MAX_CHARS = 12000


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url: str) -> Tuple[str, str]:
    """Return (status, body_text). status: ok | empty | error."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            return "error", f"HTTP {resp.status_code} for {url}"
        text = _strip_html(resp.text)
        if len(text) < 200:
            return "empty", f"JS-rendered or empty body ({len(text)} chars) for {url}"
        return "ok", text[:MAX_CHARS]
    except Exception as exc:  # noqa: BLE001
        return "error", f"{type(exc).__name__}: {exc}"


def gather_topic_sources(topic_key: str) -> Dict[str, object]:
    topic = next((t for t in TOPICS if t["key"] == topic_key), None)
    if not topic:
        return {"key": topic_key, "error": "unknown topic", "sources": []}

    blocks: List[str] = []
    ok_count = 0
    for url in topic.get("docs", []):
        status, body = fetch_url(url)
        if status == "ok":
            ok_count += 1
            blocks.append(f"### Source: {url}\n{body}")
        else:
            blocks.append(f"### Source: {url} [{status}]\n{body}")

    return {
        "key": topic["key"],
        "title": topic["title"],
        "focus": topic["focus"],
        "docs_read": ok_count,
        "context": "\n\n".join(blocks),
    }
