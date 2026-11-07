import { expect, test } from '@playwright/test';

test('sources tab allows adding channels and browsing topics', async ({ page }) => {
  await page.goto('/?tab=sources');

  // Verify header and initial count
  await expect(page.locator('h1')).toContainText('Kho nguồn dữ liệu cá nhân');
  await expect(page.locator('.stats-pill')).toContainText('4 chủ đề');

  // Verify default topic accordions exist
  await expect(page.locator('.topic-accordion')).toHaveCount(4);
  await expect(page.locator('.topic-accordion').first()).toContainText('Mẹ chồng - nàng dâu');
  await expect(page.locator('.topic-accordion').first().locator('.channel-card')).toHaveCount(3);
  await expect(page.locator('.channel-card')).toHaveCount(6); // Total across all topics

  // Test adding direct channel to a new topic
  await page.locator('input[placeholder*="facebook.com/page-name"]').fill('https://facebook.com/bepnhatoi');
  await page.locator('input[placeholder*="Ví dụ: Mẹ Chồng"]').fill('Bếp Nhà Tôi');
  await page.locator('.select-input').selectOption('__new__');
  await page.locator('input[placeholder*="Ví dụ: Đồ gia dụng"]').fill('Ẩm thực gia đình');
  await page.getByRole('button', { name: '+ Lưu kênh vào chủ đề' }).click();

  // Verify success alert and count increase
  await expect(page.locator('.alert-success')).toBeVisible();
  await expect(page.locator('.stats-pill')).toContainText('5 chủ đề');
  await expect(page.locator('.topic-accordion')).toHaveCount(5);

  // Take screenshot of topics section
  await page.locator('.panel').nth(1).scrollIntoViewIfNeeded();
  await page.screenshot({ path: '/tmp/playwright_sources_library.png', fullPage: true });
});
