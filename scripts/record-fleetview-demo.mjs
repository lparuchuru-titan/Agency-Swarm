import { chromium } from 'playwright';
import fs from 'fs';

const BASE = process.env.FLEET_URL || 'http://127.0.0.1:8770';
const OUT = process.env.OUT_DIR || '/tmp/agency-swarm-recording';
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);

console.log('1) Skills Fleet');
await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle', timeout: 45000 });
await pause(2800);
await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
await pause(1600);
await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
await pause(1000);

const buttons = page.locator('button:visible');
const bc = await buttons.count();
for (let i = 0; i < Math.min(bc, 6); i++) {
  const b = buttons.nth(i);
  const txt = ((await b.innerText().catch(() => '')) || '').trim();
  if (/kill|delete|stop|clear|remove/i.test(txt)) continue;
  await b.click({ timeout: 1500 }).catch(() => {});
  await pause(900);
}

console.log('2) Orchestrator home');
await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 45000 });
await pause(2800);
await page.evaluate(() => window.scrollTo({ top: 700, behavior: 'smooth' }));
await pause(1600);

console.log('3) Swarm fleet');
await page.goto(`${BASE}/swarm-fleet.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(()=>{});
await pause(2500);

console.log('4) Dev swarm');
await page.goto(`${BASE}/dev-swarm.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(()=>{});
await pause(2500);

console.log('5) Skills Fleet finale');
await page.goto(`${BASE}/skills-fleet.html`, { waitUntil: 'networkidle' });
await pause(2200);

await context.close();
await browser.close();
const files = fs.readdirSync(OUT).filter(f => f.endsWith('.webm'));
console.log('VIDEO_FILES', JSON.stringify(files));
if (!files.length) process.exit(2);
