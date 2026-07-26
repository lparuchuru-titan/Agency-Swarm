#!/usr/bin/env node
/**
 * PR / commit gate for Apex character growth.
 *
 * Modes:
 *   1) Changed files (CI default) — warn/fail on large new/changed .cls/.trigger
 *   2) Org snapshot — compare current org inventory to a baseline JSON
 *
 * Examples:
 *   node scripts/check-pr-apex-size.mjs --base origin/main
 *   node scripts/check-pr-apex-size.mjs --files a.cls b.cls
 *   node scripts/check-pr-apex-size.mjs --org Production --baseline docs/apex-reclaim/baseline-production.json
 *
 * Env / flags:
 *   --warn-file  50000     warn if a changed file ≥ this many chars (default 50k)
 *   --fail-file  100000    fail if a changed file ≥ this many chars (default 100k)
 *   --warn-delta 75000     warn if net +chars in PR ≥ this (default 75k)
 *   --fail-delta 150000    fail if net +chars in PR ≥ this (default 150k)
 *   --soft                 never exit non-zero (comment-only mode)
 */
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

function args(argv) {
  const o = {
    base: process.env.GITHUB_BASE_REF ? `origin/${process.env.GITHUB_BASE_REF}` : 'HEAD~1',
    files: [],
    warnFile: 50000,
    failFile: 100000,
    warnDelta: 75000,
    failDelta: 150000,
    soft: false,
    org: null,
    baseline: null,
    out: null,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--base') o.base = argv[++i];
    else if (a === '--files') {
      while (argv[i + 1] && !argv[i + 1].startsWith('--')) o.files.push(argv[++i]);
    } else if (a === '--warn-file') o.warnFile = Number(argv[++i]);
    else if (a === '--fail-file') o.failFile = Number(argv[++i]);
    else if (a === '--warn-delta') o.warnDelta = Number(argv[++i]);
    else if (a === '--fail-delta') o.failDelta = Number(argv[++i]);
    else if (a === '--soft') o.soft = true;
    else if (a === '--org') o.org = argv[++i];
    else if (a === '--baseline') o.baseline = argv[++i];
    else if (a === '--out') o.out = argv[++i];
  }
  return o;
}

function sh(cmd) {
  return execSync(cmd, { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }).trim();
}

function isApexPath(p) {
  return /\.(cls|trigger)$/i.test(p) && !p.includes('__'); // skip namespaced packaged copies if path contains __
}

function fileChars(p) {
  if (!fs.existsSync(p)) return 0;
  // Approximate LengthWithoutComments: strip // and /* */ loosely
  let s = fs.readFileSync(p, 'utf8');
  s = s.replace(/\/\*[\s\S]*?\*\//g, '');
  s = s.replace(/\/\/.*$/gm, '');
  return s.replace(/\s+/g, ' ').trim().length;
}

function changedApexFiles(base) {
  try {
    const out = sh(`git diff --name-only --diff-filter=ACMR ${base}...HEAD`);
    return out.split('\n').map((l) => l.trim()).filter((p) => p && isApexPath(p));
  } catch {
    return [];
  }
}

function netDeltaChars(base, file) {
  try {
    const diff = sh(`git diff --numstat ${base}...HEAD -- ${JSON.stringify(file)}`);
    // numstat: added deleted path
    const m = diff.match(/^(\d+)\s+(\d+)\s+/);
    if (!m) return fileChars(file); // new binary-ish / unreadable — use full size
    const added = Number(m[1]);
    const deleted = Number(m[2]);
    // rough char proxy from line counts * avg 40 chars (better than nothing for gate)
    return Math.max(0, (added - deleted) * 40);
  } catch {
    return fileChars(file);
  }
}

function checkPr(opts) {
  const files = opts.files.length ? opts.files.filter(isApexPath) : changedApexFiles(opts.base);
  const findings = [];
  let net = 0;

  for (const f of files) {
    const abs = fileChars(f);
    const delta = netDeltaChars(opts.base, f);
    net += delta;
    const row = { file: f, charsApprox: abs, deltaApprox: delta, level: 'ok' };
    if (abs >= opts.failFile || delta >= opts.failFile) row.level = 'fail';
    else if (abs >= opts.warnFile || delta >= opts.warnFile) row.level = 'warn';
    if (row.level !== 'ok') findings.push(row);
    else if (abs >= opts.warnFile * 0.6) findings.push({ ...row, level: 'info' });
  }

  let prLevel = 'ok';
  if (net >= opts.failDelta) prLevel = 'fail';
  else if (net >= opts.warnDelta) prLevel = 'warn';

  return { mode: 'pr', files: files.length, netDeltaApprox: net, prLevel, findings, thresholds: opts };
}

function checkOrgBaseline(opts) {
  // Expect baseline from analyze.mjs output (candidates + totals)
  const baseline = JSON.parse(fs.readFileSync(opts.baseline, 'utf8'));
  const raw = sh(
    `sf data query -o ${opts.org} --use-tooling-api -q "SELECT Name, LengthWithoutComments, LastModifiedDate FROM ApexClass WHERE NamespacePrefix = null" --json`
  );
  // Note: may be capped — for CI prefer weekly analyze.mjs full inventory
  const j = JSON.parse(raw);
  const records = j.result?.records || [];
  const byName = new Map(records.map((r) => [r.Name, r]));
  const baseMap = new Map((baseline.candidates || []).map((c) => [c.name, c]));

  const grown = [];
  for (const [name, r] of byName) {
    const prev = baseMap.get(name);
    const cur = r.LengthWithoutComments || 0;
    if (!prev) {
      if (cur >= opts.warnFile) grown.push({ name, delta: cur, chars: cur, kind: 'new' });
      continue;
    }
    const delta = cur - (prev.bytes || 0);
    if (delta >= opts.warnFile) grown.push({ name, delta, chars: cur, kind: 'grown' });
  }

  grown.sort((a, b) => b.delta - a.delta);
  const level = grown.some((g) => g.delta >= opts.failFile) ? 'fail' : grown.length ? 'warn' : 'ok';
  return { mode: 'org-baseline', org: opts.org, level, grown: grown.slice(0, 50) };
}

function markdownReport(result) {
  if (result.mode === 'pr') {
    const lines = [
      `## Apex size gate`,
      ``,
      `| Metric | Value |`,
      `|---|---|`,
      `| Changed Apex files | ${result.files} |`,
      `| Approx net +chars | ${result.netDeltaApprox.toLocaleString()} |`,
      `| PR level | **${result.prLevel}** |`,
      ``,
    ];
    if (result.findings.length) {
      lines.push(`### Findings`, ``, `| Level | File | ~chars | ~delta |`, `|---|---|---:|---:|`);
      for (const f of result.findings) {
        lines.push(`| ${f.level} | \`${f.file}\` | ${f.charsApprox.toLocaleString()} | ${f.deltaApprox.toLocaleString()} |`);
      }
      lines.push(``);
    }
    lines.push(
      `<details><summary>Thresholds</summary>`,
      ``,
      `- warn file ≥ ${result.thresholds.warnFile}`,
      `- fail file ≥ ${result.thresholds.failFile}`,
      `- warn PR delta ≥ ${result.thresholds.warnDelta}`,
      `- fail PR delta ≥ ${result.thresholds.failDelta}`,
      ``,
      `</details>`
    );
    return lines.join('\n');
  }
  const lines = [`## Org Apex growth vs baseline`, ``, `Level: **${result.level}**`, ``];
  if (result.grown?.length) {
    lines.push(`| Kind | Class | Delta | Chars |`, `|---|---|---:|---:|`);
    for (const g of result.grown) {
      lines.push(`| ${g.kind} | \`${g.name}\` | ${g.delta.toLocaleString()} | ${g.chars.toLocaleString()} |`);
    }
  } else lines.push(`No class grew beyond warn threshold vs baseline.`);
  return lines.join('\n');
}

function main() {
  const opts = args(process.argv);
  const result = opts.org && opts.baseline ? checkOrgBaseline(opts) : checkPr(opts);
  const md = markdownReport(result);
  console.log(md);
  if (opts.out) fs.writeFileSync(opts.out, md);
  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md + '\n');
  }

  const level = result.prLevel || result.level;
  if (!opts.soft && level === 'fail') process.exit(2);
  if (!opts.soft && level === 'warn' && process.env.APEX_SIZE_WARN_IS_FAIL === '1') process.exit(1);
}

main();
