import { expect, test } from '@playwright/test';

test('visits the app root url', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('3 chủ đề viral mỗi sheet');
  await expect(page.getByRole('button', { name: 'Chạy phân tích' })).toBeVisible();
});
