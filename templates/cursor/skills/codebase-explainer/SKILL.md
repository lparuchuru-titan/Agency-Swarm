---
name: codebase-explainer
description: >-
  Search the codebase plus Jira, Confluence, Google Drive, and Google Sheets,
  then produce a styled HTML explanation document. Use when the user asks to
  explain, walk through, document, teach, or understand how something works —
  in Cursor or Claude Code — and wants findings shown in an HTML file (not just
  chat). Triggers: explain, walk me through, how does X work, document this,
  show me in HTML, teach me, architecture overview, end-to-end flow.
---

# Codebase + Docs Explainer (HTML)

When the user wants an **explanation**, search **all available sources**, synthesize, and deliver a **standalone HTML document** they can open in a browser.

**Do not** reply with only chat prose when this skill applies — the deliverable is the HTML file.

## Output

1. Write a complete, self-contained HTML file (use [templates/explanation.html](templates/explanation.html) for structure and CSS).
2. Default path: `docs/explainers/<YYYYMMDD>-<slug>.html`
   ```bash
   python3 ~/.cursor/skills/codebase-explainer/scripts/output_path.py "user question here"
   ```
3. Tell the user the file path and run `open <path>` on macOS when appropriate.
4. Chat reply: 2–3 sentence summary + link/path to the HTML file.

Optional project config: copy `config.example.json` → `.cursor/codebase-explainer/config.json` (override `outputDir`, Jira project, doc paths).

## Research workflow (run all applicable steps)

Copy this checklist and complete every step before writing HTML:

```
Explainer progress:
- [ ] 1. Parse question (topic, entities, Jira ticket keys, LWC/Apex names)
- [ ] 2. Codebase search (semantic + grep + read key files)
- [ ] 3. Local docs (docs/, README, runbooks, knowledge-base)
- [ ] 4. Jira (tickets, epic/story, acceptance criteria)
- [ ] 5. Confluence (design docs, runbooks)
- [ ] 6. Google Drive (docs, decks, PDFs)
- [ ] 7. Google Sheets (matrices, trackers)
- [ ] 8. Write HTML + sources table
```

### 1. Codebase

- `SemanticSearch` for behavior and architecture questions.
- `Grep` for exact symbols, class names, ticket IDs in comments.
- `Read` entry points, controllers, LWC JS, triggers, flows referenced in metadata.
- Cite paths in HTML as `<code>force-app/...</code>` and include short fenced snippets in `<pre><code>` blocks (trim to relevant lines).

### 2. Local documentation

Search project paths (from config or defaults):

- `docs/`
- `README.md`
- `tools/sfdc-knowledge-swarm/knowledge-base/`
- `.cursor/sfdc-promotion/`, `.cursor/jira-subtasks/` when promotion/Jira context matters

### 3. Jira

**Cursor** — enable **`atlassian`** MCP in Settings (OAuth login). Use Jira tools from that server.

**Claude Code** — Atlassian MCP (`getJiraIssue`, `searchJiraIssuesUsingJql`, etc.).

**Fallback** (if MCP unavailable) — env `JIRA_EMAIL` + `JIRA_API_TOKEN` + `JIRA_BASE_URL`:

```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/PROJ-1001?fields=summary,description,status"
```

Extract: summary, description, acceptance criteria, subtasks, status, links.

### 4. Confluence

**Cursor / Claude Code** — **`atlassian`** MCP Confluence tools (search, get page).

**Claude Code** — also `fetch` for Confluence URLs.

Summarize in HTML; link each page in the Sources table.

### 5. Google Drive & Docs

**Cursor** — Google Workspace MCP (`user-Google Workspace`):

| Tool | Use |
|------|-----|
| `drive_search` | Query from user topic + project keywords |
| `drive_get_file` | Metadata for top hits |
| `docs_read` | Google Docs content |
| `drive_download_file` | PDFs / exports when needed |

### 6. Google Sheets

| Tool | Use |
|------|-----|
| `drive_search` | `mimeType = 'application/vnd.google-apps.spreadsheet' and fullText contains 'topic'` |
| `sheets_get` / `sheets_read` | Read relevant ranges (headers + sample rows) |

Quote only cells relevant to the question; link the sheet in Sources.

## HTML content requirements

Each explainer HTML must include:

| Section | Content |
|---------|---------|
| **Your question** | Exact user question |
| **Executive summary** | 3–5 sentences, plain language |
| **Codebase** | Flow, key files, snippets, how components connect |
| **Jira** | Relevant tickets (or "none found") |
| **Confluence** | Page summaries (or skip section if none) |
| **Google Drive & Sheets** | Doc/sheet findings (or skip if none / MCP unavailable) |
| **Local documentation** | Repo docs that answered the question |
| **Sources** | Table: Type · Title · URL or path |

Use `<span class="tag">Jira</span>` style tags for source types. Add `<div class="callout">` for important warnings or gotchas.

Optional: embed a simple flow diagram as ASCII or Mermaid inside a `<pre>` block (no external JS required).

## MCP / auth gaps

If a source is unavailable, **still ship the HTML** with a callout:

> Google Drive: MCP not authenticated — search skipped.

Never invent Jira tickets, Confluence pages, or Drive doc content.

## Examples

**User:** "Explain how quote line calculation works end to end."

1. Search codebase: calculator plugin, quote line services, price rules.
2. Read any local runbooks under `docs/` if present.
3. Jira: related story keys from your project (e.g. `PROJ-1001`).
4. Confluence: search "quoting" / "CPQ calculation".
5. Drive: search product design docs for quoting.
6. Write `docs/explainers/YYYYMMDD-quote-line-calculation.html`.

**User:** "Explain SBQQ__LookupData__c and show me in HTML."

1. Grep `LookupData`, `Auto_Add_Products`, `ProductCatalogService`.
2. Local KB note if exists under knowledge-base.
3. Jira text search for LookupData stories.
4. HTML with data model + code paths + sources.

## Global install paths

| Environment | Skill path |
|-------------|------------|
| Cursor | `~/.cursor/skills/codebase-explainer/` |
| Claude Code | `~/.claude/skills/codebase-explainer/` |

Template: `templates/explanation.html` in the skill folder.

## Related skills

- `advanced-salesforce-developer` — implementation guardrails while reading code
- `jira-subtask-workflow` — Jira credentials and project key patterns
