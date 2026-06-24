const { test, expect } = require('@playwright/test');

test.describe('Salesforce Lightning shell', () => {
  test('loads Lightning Experience home', async ({ page }) => {
    await page.goto('/lightning/page/home');
    await expect(page).toHaveURL(/lightning/);
    await expect(page.locator('body')).toBeVisible();
  });
});
