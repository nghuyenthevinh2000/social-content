import { expect, test } from '@playwright/test';

test('opens on the library with a single import box and run-all CTA', async ({ page }) => {
  const uid = `e2e_app_${Date.now()}`;
  await page.addInitScript((testUid) => {
    localStorage.setItem(`aibrand-tour-done-${testUid}`, '1');
    (window as any).__E2E_TEST_USER__ = {
      uid: testUid,
      email: 'e2e@example.com',
      displayName: 'E2E User',
      metadata: { lastSignInTime: '2026-11-10T10:00:00Z' },
      getIdToken: async () => 'e2e-fake-token',
    };
  }, uid);

  await page.route('**/api/sources/topics', (route) => route.fulfill({ json: { ok: true, topics: [] } }));
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Thư viện' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('input[type=file]')).toHaveCount(1);
  await expect(page.getByRole('button', { name: /Chạy tất cả/ })).toBeDisabled();
  await page.getByRole('tab', { name: 'Phân tích' }).click();
  await expect(page.getByText('Chưa có lần chạy nào', { exact: true })).toBeVisible();
});
