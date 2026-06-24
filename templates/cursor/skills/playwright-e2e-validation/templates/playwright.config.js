// @ts-check
const { defineConfig, devices } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

function getBaseURL() {
  const fromEnv = process.env.SF_BASE_URL || process.env.SF_INSTANCE_URL;
  if (fromEnv) return fromEnv;
  const instanceFile = path.join(__dirname, 'e2e', '.auth', 'instance-url.txt');
  if (fs.existsSync(instanceFile)) return fs.readFileSync(instanceFile, 'utf8').trim();
  return undefined;
}

module.exports = defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: getBaseURL(),
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 30_000,
    navigationTimeout: 90_000,
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.js/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], storageState: 'e2e/.auth/user.json' },
      dependencies: ['setup'],
    },
  ],
});
