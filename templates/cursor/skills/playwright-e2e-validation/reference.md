# Playwright E2E Reference

## npm scripts (add to package.json)

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:debug": "playwright test --debug",
    "test:e2e:report": "playwright show-report",
    "test:e2e:codegen": "playwright codegen"
  },
  "devDependencies": {
    "@playwright/test": "^1.60.0"
  }
}
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SF_USERNAME` | Sandbox login |
| `SF_PASSWORD` | Sandbox password |
| `SF_LOGIN_URL` | Default `https://test.salesforce.com` |
| `SF_BASE_URL` | Override instance URL |
| `E2E_RECORD_ID` | Quote/record ID for record-page LWCs |

## Lightning selectors

```javascript
// LWC custom element
page.locator('c-my-quote-line-view')

// Lightning button
page.getByRole('button', { name: 'Save' })

// Spinner gone
await page.locator('lightning-spinner').waitFor({ state: 'hidden', timeout: 60000 });

// Tab navigation
await page.goto('/lightning/n/My_Quote_View');
```

## Install Playwright browsers (first time)

```bash
npx playwright install chromium
```

## CI notes

Set `CI=true` for retries. Store `SF_USERNAME`/`SF_PASSWORD` in CI secrets. Do not commit `e2e/.auth/`.
