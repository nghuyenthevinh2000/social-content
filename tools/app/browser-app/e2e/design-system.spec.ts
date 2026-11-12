import { expect, test } from '@playwright/test';

const FONT_SIZES = [11, 13, 15, 18, 24, 32];
const CONTROL_HEIGHTS = [32, 44, 52];

test('controls follow design tokens', async ({ page }) => {
  const uid = 'e2e_ds_user';
  await page.addInitScript((u) => {
    localStorage.setItem(`aibrand-tour-done-${u}`, '1');
    (window as any).__E2E_TEST_USER__ = {
      uid: u,
      email: 'e2e@example.com',
      displayName: 'E2E',
      metadata: { lastSignInTime: '2026-11-10T10:00:00Z' },
      getIdToken: async () => 'x',
    };
  }, uid);
  await page.route('**/api/sources/topics*', (r) => r.fulfill({ json: { ok: true, topics: [] } }));
  await page.route('**/api/jobs*', (r) => r.fulfill({ json: { ok: true, jobs: [] } }));
  await page.route('**/api/media*', (r) => r.fulfill({ json: { ok: true, media: [] } }));
  await page.route('**/api/videos*', (r) => r.fulfill({ json: { ok: true, jobs: [], balance: 0 } }));

  const bad: string[] = [];
  for (const tab of ['library', 'analyzer', 'video', 'profile']) {
    await page.goto(`/?tab=${tab}`);
    await page.waitForSelector('.panel, .video-tab');
    bad.push(
      ...(await page.evaluate(
        ([sizes, heights, tabName]) =>
          [
            ...document.querySelectorAll<HTMLElement>(
              'button, input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=range]), textarea, select, label, dt',
            ),
          ]
            .filter(
              (e) =>
                e.offsetParent &&
                e.getBoundingClientRect().width > 0 &&
                !e.closest('ion-tab-bar, ion-tab-button, .tabbar-btn, .picker'),
            )
            .flatMap((e) => {
              const c = getComputedStyle(e);
              const h = Math.round(e.getBoundingClientRect().height);
              const out: string[] = [];
              const name = `${tabName} ${e.tagName.toLowerCase()}.${e.className} "${(e.textContent || '').trim().slice(0, 20)}"`;
              if (!(sizes as number[]).includes(parseFloat(c.fontSize))) out.push(`${name} font-size ${c.fontSize}`);
              if (e.matches('button, input, select') && !(heights as number[]).includes(h))
                out.push(`${name} height ${h}`);
              return out;
            }),
        [FONT_SIZES, CONTROL_HEIGHTS, tab] as const,
      )),
    );
  }
  expect(bad, bad.join('\n')).toEqual([]);
});
