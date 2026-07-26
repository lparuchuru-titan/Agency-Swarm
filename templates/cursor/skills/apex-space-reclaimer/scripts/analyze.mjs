#!/usr/bin/env node
/**
 * Apex Space Reclaimer — read-only inventory + reclaim scoring.
 *
 * Prefers UAT (closer to prod code volume). Never deletes or deploys.
 *
 * Usage:
 *   node scripts/analyze.mjs -o UAT
 *   node scripts/analyze.mjs -o UAT --target-pct 75 --limit-chars 24500000
 *   node scripts/analyze.mjs -o UAT --stale-years 7 --old-api 45
 *
 * Outputs:
 *   docs/apex-reclaim/<timestamp>-apex-reclaim-<org>.json
 *   docs/apex-reclaim/<timestamp>-apex-reclaim-<org>.html
 */
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG = path.resolve(__dirname, '..');
const ROOT = path.resolve(PKG, '../..');

function parseArgs(argv) {
  const out = {
    org: 'UAT',
    targetPct: 75,
    currentPct: 92,
    limitChars: null,
    staleYears: 7,
    oldApi: 45,
    outDir: path.join(ROOT, 'docs', 'apex-reclaim'),
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-o' || a === '--org') out.org = argv[++i];
    else if (a === '--target-pct') out.targetPct = Number(argv[++i]);
    else if (a === '--current-pct') out.currentPct = Number(argv[++i]);
    else if (a === '--limit-chars') out.limitChars = Number(argv[++i]);
    else if (a === '--stale-years') out.staleYears = Number(argv[++i]);
    else if (a === '--old-api') out.oldApi = Number(argv[++i]);
    else if (a === '--out') out.outDir = path.resolve(argv[++i]);
  }
  return out;
}

function sh(cmd) {
  return execSync(cmd, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
}

function toolingQuery(org, soql) {
  const q = soql.replace(/\s+/g, ' ').trim();
  const raw = sh(`sf data query -o ${org} --use-tooling-api -q ${JSON.stringify(q)} --json`);
  const j = JSON.parse(raw);
  if (j.status !== 0) throw new Error(j.message || raw.slice(0, 500));
  return j.result.records || [];
}

/** Paginate Tooling REST queries (MetadataComponentDependency needs this). */
function toolingQueryAll(org, soql, { maxRows = 50000 } = {}) {
  const q = encodeURIComponent(soql.replace(/\s+/g, ' ').trim());
  let path = `/services/data/v62.0/tooling/query?q=${q}`;
  const records = [];
  while (path && records.length < maxRows) {
    const raw = sh(`sf api request rest ${JSON.stringify(path)} -o ${org}`);
    const j = JSON.parse(raw);
    records.push(...(j.records || []));
    if (!j.done && j.nextRecordsUrl) {
      path = j.nextRecordsUrl;
    } else {
      break;
    }
    process.stdout.write(`  deps=${records.length}`);
  }
  console.log(`\n  toolingQueryAll total:`, records.length);
  return records;
}

/** Fetch all unmanaged Apex types — Tooling queries often cap at 2000 rows. */
function queryApexByName(org, objectName, fields) {
  const prefixes = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_'.split('');
  const byId = new Map();
  for (const p of prefixes) {
    const soql = `SELECT ${fields} FROM ${objectName}
      WHERE NamespacePrefix = null AND Name LIKE '${p}%'
      ORDER BY Name LIMIT 2000`;
    try {
      const rows = toolingQuery(org, soql);
      for (const r of rows) byId.set(r.Id, r);
      if (rows.length) process.stdout.write(`  ${objectName}[${p}]=${rows.length}`);
    } catch (e) {
      console.warn(`\n  skip ${objectName} ${p}:`, e.message.slice(0, 120));
    }
  }
  // Catch names that don't match LIKE prefixes (unicode/etc.)
  try {
    const rest = toolingQuery(
      org,
      `SELECT ${fields} FROM ${objectName} WHERE NamespacePrefix = null ORDER BY LengthWithoutComments DESC LIMIT 2000`
    );
    for (const r of rest) byId.set(r.Id, r);
  } catch {
    /* ignore */
  }
  console.log(`\n  ${objectName} unique:`, byId.size);
  return [...byId.values()];
}

function daysAgo(dateStr) {
  return (Date.now() - new Date(dateStr).getTime()) / (86400 * 1000);
}

function isTestName(name) {
  return /(?:^|[_\.])(test|tests|mock|mocks|stub)(?:[_\.]|$)/i.test(name) || /Test\d*$/i.test(name);
}

function scoreClass(c, ctx) {
  const reasons = [];
  let score = 0;
  const ageYears = daysAgo(c.LastModifiedDate) / 365.25;
  const createdYears = daysAgo(c.CreatedDate) / 365.25;
  const bytes = c.LengthWithoutComments || 0;
  const name = c.Name || '';

  // Stale: last modified ≥ N years (user intent: old unused code)
  if (ageYears >= ctx.staleYears) {
    score += 35;
    reasons.push(`stale_last_modified_${ctx.staleYears}y+`);
  } else if (ageYears >= ctx.staleYears * 0.7) {
    score += 15;
    reasons.push('aging_last_modified');
  }

  if (c.ApiVersion < ctx.oldApi) {
    score += 20;
    reasons.push(`api_version_<${ctx.oldApi}`);
  } else if (c.ApiVersion < ctx.oldApi + 10) {
    score += 8;
    reasons.push('api_version_aging');
  }

  if (c.Status && c.Status !== 'Active') {
    score += 40;
    reasons.push(`status_${c.Status}`);
  }
  if (c.IsValid === false) {
    score += 25;
    reasons.push('invalid_compile');
  }

  // Backup / scratch naming — avoid matching Template/Delete/AccountCopy business names
  if (
    /(Backup\d*$|_Backup|_Bak\b|_Old\b|_Copy\d*$|^CopyOf|_Deprecated|Deprecated_|zzz_|_tmp$|^Tmp[A-Z]|Scratch|_Scratch)/i.test(
      name
    )
  ) {
    score += 40;
    reasons.push('backup_or_temp_name');
  }

  // Orphan test / one-off experimental names
  if (/^(testluv|luvbackup|tmp|xxx)/i.test(name) && bytes > 5000) {
    score += 15;
    reasons.push('experimental_name');
  }

  const inbound = ctx.inbound.get(name);
  const depsAvailable = ctx.depsAvailable;
  if (depsAvailable && inbound === 0 && !isTestName(name)) {
    score += 30;
    reasons.push('no_inbound_metadata_deps');
  } else if (depsAvailable && (inbound || 0) <= 1 && isTestName(name)) {
    score += 5;
    reasons.push('test_class_low_deps');
  } else if (depsAvailable && (inbound || 0) >= 1) {
    // referenced — small penalty already by not adding orphan points
  }

  // Zero coverage (prod classes)
  if (ctx.zeroCoverage.has(name) && !isTestName(name)) {
    score += 25;
    reasons.push('zero_test_coverage');
  }

  // Never touched after create long ago + small inbound
  if (depsAvailable && createdYears >= ctx.staleYears && (inbound || 0) <= 1) {
    score += 10;
    reasons.push('old_create_low_refs');
  }

  // Size amplifies priority (more chars reclaimed)
  const sizeBoost = Math.min(20, Math.floor(bytes / 25000));
  score += sizeBoost;
  if (sizeBoost) reasons.push(`size_boost_${bytes}`);

  return {
    score: Math.min(100, score),
    reasons,
    inbound: inbound ?? null,
    ageYears: +ageYears.toFixed(1),
  };
}

function buildHtml(report) {
  const rows = report.candidates
    .slice(0, 150)
    .map(
      (c) => `<tr>
      <td>${c.score}</td>
      <td><code>${escapeHtml(c.name)}</code></td>
      <td>${c.bytes.toLocaleString()}</td>
      <td>${c.apiVersion}</td>
      <td>${c.lastModified?.slice(0, 10) || ''}</td>
      <td>${c.inbound}</td>
      <td>${c.reasons.map(escapeHtml).join(', ')}</td>
    </tr>`
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Apex Space Reclaim — ${escapeHtml(report.org)}</title>
<style>
:root{--bg:#0f1419;--card:#1a2332;--text:#e7ecf3;--muted:#9aa8bc;--accent:#3d9cf0;--ok:#3ecf8e;--warn:#f5a524}
*{box-sizing:border-box}body{margin:0;font-family:ui-sans-serif,system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
.hero{padding:2.5rem 2rem;background:linear-gradient(135deg,#1a2332,#243044);border-bottom:1px solid #2a3548}
h1{margin:0 0 .5rem;font-size:1.75rem}.sub{color:var(--muted);max-width:60rem}
.wrap{padding:1.5rem 2rem;max-width:1100px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin:1.5rem 0}
.card{background:var(--card);border:1px solid #2a3548;border-radius:10px;padding:1rem}
.card b{display:block;font-size:1.4rem;color:var(--accent)}
.callout{background:#243044;border-left:4px solid var(--warn);padding:1rem 1.25rem;margin:1rem 0;border-radius:0 8px 8px 0}
table{width:100%;border-collapse:collapse;font-size:.85rem}th,td{padding:.45rem .5rem;border-bottom:1px solid #2a3548;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}code{color:#9cdcfe}
.ok{color:var(--ok)}.footer{color:var(--muted);font-size:.8rem;margin-top:2rem}
</style></head><body>
<div class="hero">
  <h1>Apex Space Reclaimer</h1>
  <p class="sub">Read-only analysis for <strong>${escapeHtml(report.org)}</strong> — scored candidates to move Apex usage from ~${report.currentPct}% toward ≤${report.targetPct}%. Generated ${escapeHtml(report.ts)}</p>
</div>
<div class="wrap">
  <div class="cards">
    <div class="card"><span>Unmanaged Apex chars</span><b>${report.totals.chars.toLocaleString()}</b></div>
    <div class="card"><span>Classes / Triggers</span><b>${report.totals.classes} / ${report.totals.triggers}</b></div>
    <div class="card"><span>Est. limit (chars)</span><b>${report.limitChars ? report.limitChars.toLocaleString() : 'n/a'}</b></div>
    <div class="card"><span>Chars to free (→${report.targetPct}%)</span><b>${report.charsToFree.toLocaleString()}</b></div>
    <div class="card"><span>Top-150 candidate chars</span><b>${report.candidateChars.toLocaleString()}</b></div>
    <div class="card"><span>Coverage if removed*</span><b class="ok">${report.projectedPct != null ? report.projectedPct + '%' : 'n/a'}</b></div>
  </div>
  <div class="callout">
    <strong>Do not delete from this report alone.</strong> Validate each candidate for Flows, LWC, VF, package install, scheduled jobs, and production traffic.
    Prefer UAT analysis, then dry-run delete in a sandbox. Managed package code (<code>NamespacePrefix != null</code>) is excluded.
    *Projected % assumes estimated limit and that every listed candidate is safe to remove — treat as upper bound.
  </div>
  <h2>Scoring heuristics</h2>
  <ul>
    <li>Last modified ≥ ${report.staleYears} years (stale)</li>
    <li>API version &lt; ${report.oldApi}</li>
    <li>No inbound <code>MetadataComponentDependency</code> references</li>
    <li>Zero Apex test coverage (non-test classes)</li>
    <li>Backup/temp/deprecated naming; invalid/inactive status</li>
    <li>Size boost (larger classes reclaim more limit)</li>
  </ul>
  <h2>Top reclaim candidates</h2>
  <table>
    <thead><tr><th>Score</th><th>Name</th><th>Chars</th><th>API</th><th>Last mod</th><th>Inbound deps</th><th>Reasons</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <h2>Recommended playbook</h2>
  <ol>
    <li>Review P1 (score ≥ 70) with owners — confirm no declarative / integration callers.</li>
    <li>Start with backup/temp names and invalid classes.</li>
    <li>Delete or archive in a sandbox; run full regression; promote via normal pipeline.</li>
    <li>Re-run this analyzer after each batch until usage ≤ ${report.targetPct}%.</li>
  </ol>
  <p class="footer">tools/apex-space-reclaimer · org ${escapeHtml(report.org)} · ${escapeHtml(report.ts)}</p>
</div>
</body></html>`;
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function main() {
  const opts = parseArgs(process.argv);
  console.log('Org:', opts.org, '| target%:', opts.targetPct, '| staleYears:', opts.staleYears, '| oldApi:', opts.oldApi);

  console.log('Querying ApexClass…');
  const classes = queryApexByName(
    opts.org,
    'ApexClass',
    'Id, Name, ApiVersion, LengthWithoutComments, LastModifiedDate, CreatedDate, Status, IsValid'
  );

  console.log('Querying ApexTrigger…');
  const triggers = queryApexByName(
    opts.org,
    'ApexTrigger',
    'Id, Name, ApiVersion, LengthWithoutComments, LastModifiedDate, CreatedDate, Status'
  );

  console.log('Querying coverage aggregates (zero coverage)…');
  let zeroCoverage = new Set();
  try {
    const cov = toolingQuery(
      opts.org,
      `SELECT ApexClassOrTriggerId, ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered
       FROM ApexCodeCoverageAggregate
       WHERE NumLinesCovered = 0
       LIMIT 2000`
    );
    zeroCoverage = new Set(cov.map((r) => r.ApexClassOrTrigger?.Name).filter(Boolean));
    console.log('  zero-coverage rows:', zeroCoverage.size);
  } catch (e) {
    console.warn('  coverage query skipped:', e.message.slice(0, 200));
  }

  console.log('Querying MetadataComponentDependency (inbound Apex refs)…');
  const inbound = new Map();
  let depsAvailable = false;
  // Object is capped ~2000 rows per query — slice by MetadataComponentType
  const depTypes = [
    'ApexClass',
    'ApexTrigger',
    'LightningComponentBundle',
    'AuraDefinitionBundle',
    'ApexPage',
    'ApexComponent',
    'Flow',
    'FlowDefinition',
    'CustomObject',
    'ValidationRule',
    'QuickAction',
    'FlexiPage',
  ];
  try {
    let totalDeps = 0;
    for (const t of depTypes) {
      const deps = toolingQuery(
        opts.org,
        `SELECT RefMetadataComponentName, MetadataComponentName, MetadataComponentType
         FROM MetadataComponentDependency
         WHERE RefMetadataComponentType = 'ApexClass'
         AND MetadataComponentType = '${t}'
         LIMIT 2000`
      );
      totalDeps += deps.length;
      for (const d of deps) {
        const ref = d.RefMetadataComponentName;
        if (!ref) continue;
        inbound.set(ref, (inbound.get(ref) || 0) + 1);
      }
      if (deps.length) process.stdout.write(`  ${t}=${deps.length}`);
    }
    console.log(`\n  dep rows≈${totalDeps}, unique referenced classes:`, inbound.size);
    depsAvailable = inbound.size > 0;
    if (totalDeps >= 2000) {
      console.warn('  Note: MetadataComponentDependency is capped per query (~2000); treat orphan signal as heuristic.');
    }
  } catch (e) {
    console.warn('  dependency query limited/failed:', e.message.slice(0, 400));
  }

  const classChars = classes.reduce((s, c) => s + (c.LengthWithoutComments || 0), 0);
  const triggerChars = triggers.reduce((s, c) => s + (c.LengthWithoutComments || 0), 0);
  const totalChars = classChars + triggerChars;

  // Infer limit from current% if not provided: limit = total / (currentPct/100)
  const limitChars =
    opts.limitChars ||
    (opts.currentPct > 0 ? Math.round(totalChars / (opts.currentPct / 100)) : null);
  const charsToFree = limitChars
    ? Math.max(0, Math.round(totalChars - (opts.targetPct / 100) * limitChars))
    : Math.round(totalChars * ((opts.currentPct - opts.targetPct) / opts.currentPct));

  const ctx = {
    staleYears: opts.staleYears,
    oldApi: opts.oldApi,
    inbound,
    zeroCoverage,
    depsAvailable,
  };

  const scored = classes.map((c) => {
    const { score, reasons, inbound: ib, ageYears } = scoreClass(c, ctx);
    return {
      id: c.Id,
      name: c.Name,
      bytes: c.LengthWithoutComments || 0,
      apiVersion: c.ApiVersion,
      lastModified: c.LastModifiedDate,
      created: c.CreatedDate,
      status: c.Status,
      isValid: c.IsValid,
      isTest: isTestName(c.Name),
      score,
      reasons,
      inbound: ib,
      ageYears,
      type: 'ApexClass',
    };
  });

  scored.sort((a, b) => b.score - a.score || b.bytes - a.bytes);

  // Greedy pack until charsToFree met among score≥30 (review required)
  let packed = 0;
  const plan = [];
  for (const c of scored) {
    if (c.score < 30) continue;
    plan.push(c);
    packed += c.bytes;
    if (packed >= charsToFree) break;
  }

  const candidateChars = scored.slice(0, 150).reduce((s, c) => s + c.bytes, 0);
  const projectedUsed = limitChars ? totalChars - packed : null;
  const projectedPct = limitChars && projectedUsed != null ? +((projectedUsed / limitChars) * 100).toFixed(1) : null;

  const report = {
    org: opts.org,
    ts: new Date().toISOString(),
    currentPct: opts.currentPct,
    targetPct: opts.targetPct,
    staleYears: opts.staleYears,
    oldApi: opts.oldApi,
    limitChars,
    charsToFree,
    candidateChars,
    projectedPct,
    totals: {
      chars: totalChars,
      classChars,
      triggerChars,
      classes: classes.length,
      triggers: triggers.length,
    },
    planChars: packed,
    planCount: plan.length,
    candidates: scored,
    plan: plan.map((c) => ({ name: c.name, bytes: c.bytes, score: c.score, reasons: c.reasons })),
    notes: [
      'Read-only. No deletes performed.',
      'UAT preferred for inventory (higher volume than your-org sandbox).',
      'Inbound deps from MetadataComponentDependency — may miss dynamic Type.forName / REST callers.',
      'Validate before delete: Schedulable/Batch jobs, VF, Aura, LWC wire, Flow invocable, email services, packages.',
    ],
  };

  fs.mkdirSync(opts.outDir, { recursive: true });
  const stamp = report.ts.slice(0, 10).replace(/-/g, '');
  const base = `${stamp}-apex-reclaim-${opts.org.toLowerCase()}`;
  const jsonPath = path.join(opts.outDir, `${base}.json`);
  const htmlPath = path.join(opts.outDir, `${base}.html`);
  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(htmlPath, buildHtml(report));

  console.log('\n=== SUMMARY ===');
  console.log('Total unmanaged Apex chars:', totalChars.toLocaleString());
  console.log('Estimated limit:', limitChars?.toLocaleString() || 'n/a');
  console.log('Chars to free for', opts.targetPct + '%:', charsToFree.toLocaleString());
  console.log('Greedy plan (score≥40):', plan.length, 'classes,', packed.toLocaleString(), 'chars');
  console.log('Projected usage if plan safe:', projectedPct != null ? projectedPct + '%' : 'n/a');
  console.log('Top 10:');
  for (const c of scored.slice(0, 10)) {
    console.log(`  [${c.score}] ${c.bytes.toLocaleString()} ${c.name} — ${c.reasons.join(', ')}`);
  }
  console.log('\nWrote', jsonPath);
  console.log('Wrote', htmlPath);

  // open on macOS
  try {
    sh(`open ${JSON.stringify(htmlPath)}`);
  } catch {
    /* ignore */
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
