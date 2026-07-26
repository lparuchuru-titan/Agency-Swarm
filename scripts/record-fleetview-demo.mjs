/**
 * Timed FleetView walkthrough — pauses match Personal Voice section timings
 * so video actions stay in sync with narration.
 *
 * Prereq: python3 scripts/build-fleetview-demo-audio.py
 * Always use clean .demo-sfdx FleetView (FLEET_URL), never a customer project.
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Prefer explicit AGENCY_ROOT — script is sometimes copied into a Playwright project to resolve deps.
const ROOT = process.env.AGENCY_ROOT
  ? path.resolve(process.env.AGENCY_ROOT)
  : path.resolve(__dirname, '..');
const BASE = process.env.FLEET_URL || 'http://127.0.0.1:8771';
const OUT = process.env.OUT_DIR || '/tmp/agency-swarm-recording';
const TIMINGS_PATH =
  process.env.TIMINGS_FILE ||
  path.join(ROOT, 'docs/blog/assets/voice/timings.json');

fs.mkdirSync(OUT, { recursive: true });

if (!fs.existsSync(TIMINGS_PATH)) {
  console.error('Missing timings.json — run: python3 scripts/build-fleetview-demo-audio.py');
  process.exit(2);
}
const timings = JSON.parse(fs.readFileSync(TIMINGS_PATH, 'utf8'));
const byId = Object.fromEntries(timings.sections.map((s) => [s.id, s]));

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);

async function section(id, fn) {
  const t = byId[id];
  if (!t) throw new Error(`Unknown section ${id}`);
  const start = Date.now();
  console.log(`▶ ${id} (${t.total_ms}ms)`);
  await fn();
  const used = Date.now() - start;
  const remain = t.total_ms - used;
  if (remain > 50) await pause(remain);
  else if (remain < -200) console.warn(`  section ${id} overran by ${-remain}ms`);
}

async function clickIfVisible(selector, waitAfter = 800) {
  const loc = page.locator(selector).first();
  if (await loc.isVisible({ timeout: 2000 }).catch(() => false)) {
    await loc.click({ timeout: 3000 }).catch(() => {});
    await pause(waitAfter);
    return true;
  }
  return false;
}

// Sanity: no private skills
const fleetResp = await context.request.get(`${BASE}/api/cursor-fleet`);
const fleet = await fleetResp.json();
const ids = (fleet.skills || []).map((s) => s.id);
const banned = ids.filter((id) => /pantheon|trailhead|the-fixer/i.test(id));
if (banned.length) {
  console.error('REFUSING to record — private skills visible:', banned.join(', '));
  process.exit(3);
}
console.log('project=', fleet.project, 'skills=', ids.length, 'audio_total_s=', (timings.total_ms / 1000).toFixed(1));

await section('intro', async () => {
  await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle', timeout: 45000 });
  await pause(600);
});

await section('skills_overview', async () => {
  const cards = page.locator('.skill-card');
  const n = await cards.count();
  for (let i = 0; i < Math.min(n, 4); i++) {
    await cards.nth(i).hover().catch(() => {});
    await pause(700);
  }
  await page.evaluate(() => window.scrollTo({ top: 380, behavior: 'smooth' }));
  await pause(900);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
});

await section('sync_feeds', async () => {
  await clickIfVisible('#btn-refresh-manifest', 1200);
  // Let sync UI animate while audio explains
});

await section('feed_detail', async () => {
  await page.evaluate(() => window.scrollTo({ top: 480, behavior: 'smooth' }));
  await pause(800);
  const cards = page.locator('.skill-card');
  const n = await cards.count();
  if (n > 0) {
    await cards.nth(0).scrollIntoViewIfNeeded().catch(() => {});
    await pause(1000);
    if (n > 1) {
      await cards.nth(1).scrollIntoViewIfNeeded().catch(() => {});
      await pause(900);
    }
  }
});

await section('orchestrator', async () => {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 45000 });
  await pause(700);
  await page.evaluate(() => window.scrollTo({ top: 420, behavior: 'smooth' }));
  await pause(900);
  await page.evaluate(() => window.scrollTo({ top: 780, behavior: 'smooth' }));
});

await section('dev_swarm', async () => {
  await page.goto(`${BASE}/dev-swarm.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  await pause(700);
  const input = page.locator('textarea, input[type="text"]').first();
  if (await input.isVisible({ timeout: 2000 }).catch(() => false)) {
    await input.click().catch(() => {});
    await input.fill('Review Apex changes and outline a test plan').catch(() => {});
    await pause(900);
  }
  // Highlight the button; avoid long-running orchestrate in the recording
  const btn = page.locator('#btn-run').first();
  if (await btn.isVisible({ timeout: 1500 }).catch(() => false)) {
    await btn.hover().catch(() => {});
    await pause(800);
    // brief click then stay — offline run is fine if short
    await btn.click({ timeout: 2000 }).catch(() => {});
  }
});

await section('swarm_fleet', async () => {
  await page.goto(`${BASE}/swarm-fleet.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  await pause(600);
  await page.evaluate(() => window.scrollTo({ top: 360, behavior: 'smooth' }));
});

await section('outro', async () => {
  await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle' });
  await pause(500);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
});

await context.close();
await browser.close();
const files = fs.readdirSync(OUT).filter((f) => f.endsWith('.webm'));
console.log('VIDEO_FILES', JSON.stringify(files));
if (!files.length) process.exit(2);
