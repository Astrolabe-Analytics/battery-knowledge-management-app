import { test, expect } from '@playwright/test';

// First run: npm run test:e2e:update to generate baselines.
// Subsequent runs: npm run test:e2e to compare against baselines.
// The API backend (port 8003) may not be available in test environments;
// the snapshot captures whatever the app renders in that state.
test('homepage visual snapshot', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  // Give React time to render the initial shell
  await page.waitForTimeout(300);
  // Suppress animations for deterministic screenshots
  await page.addStyleTag({
    content: [
      '*, *::before, *::after {',
      '  animation-duration: 0ms !important;',
      '  animation-delay: 0ms !important;',
      '  transition-duration: 0ms !important;',
      '  caret-color: transparent !important;',
      '}',
    ].join('\n'),
  });
  await expect(page).toHaveScreenshot('homepage.png', {
    fullPage: false,
    maxDiffPixelRatio: 0.02,
  });
});
