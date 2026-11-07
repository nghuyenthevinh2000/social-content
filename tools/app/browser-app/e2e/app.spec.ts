import { expect, test } from '@playwright/test';

test('opens on the library with a single import box and run-all CTA', async ({ page }) => {
  await page.route('**/api/sources/topics', (route) => route.fulfill({ json: { ok: true, topics: [] } }));
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Thư viện' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('input[type=file]')).toHaveCount(1);
  await expect(page.getByRole('button', { name: /Chạy tất cả/ })).toBeDisabled();
  await page.getByRole('tab', { name: 'Phân tích' }).click();
  await expect(page.getByText('Chưa có lần chạy nào.')).toBeVisible();
});
