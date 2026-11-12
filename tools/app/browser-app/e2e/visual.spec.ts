import { test } from '@playwright/test';

test.describe('Visual screenshots', () => {
  test('capture baseline screenshots', async ({ page }) => {
    const uid = 'e2e_visual_test_user';
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

    await page.route('**/api/sources/topics*', (route) =>
      route.fulfill({
        json: {
          ok: true,
          topics: [
            {
              name: 'sở thích cá nhân',
              slug: 'so-thich-ca-nhan',
              targets: [],
            },
          ],
        },
      }),
    );
    await page.route('**/api/jobs*', (route) => route.fulfill({ json: { ok: true, jobs: [] } }));
    await page.route('**/api/media*', (route) => route.fulfill({ json: { ok: true, media: [] } }));

    // 1. Library tab
    await page.goto('/');
    await page.waitForSelector('.panel');
    await page.screenshot({ path: 'e2e/screenshots/baseline/library.png' });

    // 2. Analyzer tab
    await page.goto('/?tab=analyzer');
    await page.waitForSelector('.panel');
    await page.screenshot({ path: 'e2e/screenshots/baseline/analyzer.png' });

    // 3. Video tab
    await page.goto('/?tab=video');
    await page.waitForSelector('.video-tab, .panel');
    await page.screenshot({ path: 'e2e/screenshots/baseline/video.png' });

    // 4. Profile tab
    await page.goto('/?tab=profile');
    await page.waitForSelector('.panel');
    await page.screenshot({ path: 'e2e/screenshots/baseline/profile.png' });
  });

  test('capture auth modal screenshot', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('.panel, .auth-gate-btn');
    const authBtn = page.locator('.auth-gate-btn').first();
    if (await authBtn.isVisible()) {
      await authBtn.click();
      await page.waitForSelector('.auth-modal');
      await page.screenshot({ path: 'e2e/screenshots/baseline/auth-modal.png' });
    }
  });
});
