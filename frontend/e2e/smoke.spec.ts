import { test, expect } from '@playwright/test';

test('app boots and renders @smoke', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Astrolabe Paper DB');
  await expect(page.locator('#root')).toBeVisible();
});
