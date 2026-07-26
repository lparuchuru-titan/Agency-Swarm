/**
 * Record a guided FleetView walkthrough (button clicks + scrolls).
 * Always point FLEET_URL at the clean .demo-sfdx fixture — never a
 * customer project that has private skills (pantheon / trailhead / etc.).
 */
import { chromium } from 'playwright';
import fs from 'fs';

const BASE = process.env.FLEET_URL || 'http://127.0.0.1:8771';
const OUT = process.env.OUT_DIR || '/tmp/agency-swarm-recording';
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);

async function clickIfVisible(selector, waitAfter = 1200) {
  const loc = page.locator(selector).first();
  if (await loc.isVisible({ timeout: 2500 }).catch(() => false)) {
    await loc.click({ timeout: 3000 }).catch(() => {});
    await pause(waitAfter);
    return true;
  }
  return false;
}

console.log('0) Sanity — refuse customer-private skills in frame');
const fleetResp = await context.request.get(`${BASE}/api/cursor-fleet`);
const fleet = await fleetResp.json();
const ids = (fleet.skills || []).map((s) => s.id);
const banned = ids.filter((id) => /pantheon|trailhead|the-fixer/i.test(id));
if (banned.length) {
  console.error('REFUSING to record — private skills visible:', banned.join(', '));
  console.error('Serve .demo-sfdx on FLEET_URL, not a customer project.');
  process.exit(3);
}
console.log('project=', fleet.project, 'skills=', ids.length);

console.log('1) Skills Fleet — overview');
await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle', timeout: 45000 });
await pause(3500);
// Hover first few skill cards so feeds are readable
const cards = page.locator('.skill-card');
const cardCount = await cards.count();
for (let i = 0; i < Math.min(cardCount, 3); i++) {
  await cards.nth(i).hover().catch(() => {});
  await pause(900);
}
await page.evaluate(() => window.scrollTo({ top: 420, behavior: 'smooth' }));
await pause(1800);
await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
await pause(1000);

console.log('2) Click Sync Skill Feeds');
await clickIfVisible('#btn-refresh-manifest', 4500);
await pause(2000);

console.log('3) Scroll feed lists on cards');
await page.evaluate(() => window.scrollTo({ top: 520, behavior: 'smooth' }));
await pause(2200);
if (cardCount > 0) {
  await cards.nth(0).scrollIntoViewIfNeeded().catch(() => {});
  await pause(1600);
  await cards.nth(Math.min(1, cardCount - 1)).scrollIntoViewIfNeeded().catch(() => {});
  await pause(1600);
}
await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
await pause(800);

console.log('4) Orchestrator home');
await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 45000 });
await pause(3200);
await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'smooth' }));
await pause(2000);
await page.evaluate(() => window.scrollTo({ top: 900, behavior: 'smooth' }));
await pause(1600);

console.log('5) Dev Swarm — show Run Orchestrator');
await page.goto(`${BASE}/dev-swarm.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
await pause(2500);
// Focus / fill sample request if a textarea exists
const input = page.locator('textarea, input[type="text"]').first();
if (await input.isVisible({ timeout: 2000 }).catch(() => false)) {
  await input.click().catch(() => {});
  await input.fill('Review Apex changes and outline a test plan').catch(() => {});
  await pause(1800);
}
await clickIfVisible('#btn-run', 900); // may start a short offline run — ok for demo
await pause(2800);
await clickIfVisible('#btn-kb', 2000);

console.log('6) Swarm Fleet status board');
await page.goto(`${BASE}/swarm-fleet.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
await pause(2800);
await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
await pause(1600);

console.log('7) Skills Fleet finale');
await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle' });
await pause(3200);

await context.close();
await browser.close();
const files = fs.readdirSync(OUT).filter((f) => f.endsWith('.webm'));
console.log('VIDEO_FILES', JSON.stringify(files));
if (!files.length) process.exit(2);
