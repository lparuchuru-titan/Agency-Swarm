const { test: setup } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const authFile = path.join(__dirname, '.auth', 'user.json');

setup('authenticate to Salesforce', async ({ page }) => {
  const username = process.env.SF_USERNAME;
  const password = process.env.SF_PASSWORD;
  const loginUrl = process.env.SF_LOGIN_URL || 'https://test.salesforce.com';

  if (!username || !password) {
    throw new Error('Set SF_USERNAME and SF_PASSWORD before running E2E tests.');
  }

  fs.mkdirSync(path.dirname(authFile), { recursive: true });
  await page.goto(loginUrl);
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /log in to sandbox|log in/i }).click();
  await page.waitForURL(/lightning\.force\.com|\.salesforce\.com/, { timeout: 120_000 });

  const instanceUrl = new URL(page.url()).origin;
  fs.writeFileSync(path.join(path.dirname(authFile), 'instance-url.txt'), instanceUrl);
  await page.context().storageState({ path: authFile });
});
