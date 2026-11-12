import { expect, test } from '@playwright/test';

type Topic = { name: string; slug: string; targets: { name: string; url: string }[] };

test('library adds channels via the backend and runs from the library only', async ({ page }) => {
  const uid = `e2e_sources_${Date.now()}`;
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

  const topics: Topic[] = [
    {
      name: 'Mẹ chồng - nàng dâu',
      slug: 'me-chong-nang-dau',
      targets: [{ name: 'Mẹ chồng vào bếp', url: 'https://www.facebook.com/100084795256037' }],
    },
    {
      name: 'sở thích cá nhân',
      slug: 'so-thich-ca-nhan',
      targets: [],
    },
  ];
  let jobPayload: { sheets: { name: string }[] } | null = null;

  await page.route('**/api/sources/topics', async (route) => {
    if (route.request().method() === 'POST') {
      const { topic, url } = route.request().postDataJSON();
      let found = topics.find((t) => t.name === topic);
      if (!found) topics.push((found = { name: topic, slug: `t${topics.length}`, targets: [] }));
      if (url) found.targets.push({ name: url, url });
    }
    await route.fulfill({ json: { ok: true, topics } });
  });
  await page.route(
    (url) => url.pathname === '/api/jobs',
    async (route) => {
      if (route.request().method() === 'POST') {
        jobPayload = route.request().postDataJSON();
      }
      await route.fulfill({
        json: { id: 'abc', status: 'queued', filename: 'all_topics.json', current_sheet: null, sheets: [], logs: [] },
      });
    },
  );
  await page.route('**/api/jobs/abc', (route) =>
    route.fulfill({
      json: { id: 'abc', status: 'queued', filename: 'all_topics.json', current_sheet: null, sheets: [], logs: [] },
    }),
  );

  await page.goto('/');
  await expect(page.locator('.topic-accordion')).toHaveCount(2);
  await expect(page.locator('.count').first()).toContainText('2 chủ đề · 1 kênh');

  // One add-channel path: inline per topic
  await page.locator('.topic-accordion summary').first().click();
  await page.getByLabel('Thêm kênh vào Mẹ chồng - nàng dâu').fill('https://facebook.com/a');
  await page.getByRole('button', { name: '+ Thêm' }).click();
  await expect(page.locator('.alert.success')).toBeVisible();
  await expect(page.locator('.channel-card')).toHaveCount(2);

  // New topic row
  await page.getByLabel('Tên chủ đề mới').fill('Ẩm thực');
  await page.getByLabel('Link kênh đầu tiên').fill('https://facebook.com/b');
  await page.getByRole('button', { name: '+ Tạo chủ đề' }).click();
  await expect(page.locator('.topic-accordion')).toHaveCount(3);

  // Run all → switches to analyzer
  await page.getByRole('button', { name: /Chạy tất cả \(2 chủ đề\)/ }).click();
  await expect(page.getByRole('tab', { name: /Phân tích/ })).toHaveAttribute('aria-selected', 'true');
  await expect.poll(() => jobPayload).not.toBeNull();
  expect(jobPayload!.sheets.map((s) => s.name)).toEqual(['Mẹ chồng - nàng dâu', 'Ẩm thực']);
});

test('topics section is collapsible and saved reels container renders', async ({ page }) => {
  const uid = `e2e_reels_${Date.now()}`;
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

  const fakeReels = [
    {
      id: 'reel_abc',
      reel_url: 'https://www.facebook.com/reel/999888777',
      platform: 'facebook',
      share_type: 'link_share',
      sender_name: 'Minh Chau',
      message_text: 'Reel viral hay',
      created_at: '2026-11-12T12:00:00Z',
    },
  ];

  await page.route('**/api/sources/topics', (route) =>
    route.fulfill({
      json: {
        ok: true,
        topics: [
          {
            name: 'Thời trang',
            slug: 'thoi-trang',
            targets: [{ name: 'Kênh thời trang', url: 'https://facebook.com/fashion' }],
          },
        ],
      },
    }),
  );
  await page.route('**/api/saved-reels', (route) => route.fulfill({ json: { ok: true, reels: fakeReels } }));

  await page.goto('/');

  // Run all button is visible on top of topics section
  const runAllBtn = page.getByRole('button', { name: /Chạy tất cả \(1 chủ đề\)/ });
  await expect(runAllBtn).toBeVisible();

  // Topics section collapsible toggle
  const topicsHead = page.locator('.topics-panel .collapsible-head');
  await expect(topicsHead).toBeVisible();
  await expect(page.locator('.topic-accordion')).toBeVisible();

  // Click to collapse
  await topicsHead.click();
  await expect(page.locator('.topic-accordion')).toHaveCount(0);

  // Click to expand again
  await topicsHead.click();
  await expect(page.locator('.topic-accordion')).toBeVisible();

  // Saved reels container
  const savedReelsPanel = page.locator('.saved-reels-panel');
  await expect(savedReelsPanel).toBeVisible();
  await expect(savedReelsPanel).toContainText('Reel đã lưu');
  await expect(savedReelsPanel).toContainText('1 reel');
  await expect(page.locator('.saved-reel-card')).toHaveCount(1);
  await expect(page.locator('.saved-reel-card')).toContainText('facebook');
  await expect(page.locator('.saved-reel-card .channel-link')).toBeVisible();
});
