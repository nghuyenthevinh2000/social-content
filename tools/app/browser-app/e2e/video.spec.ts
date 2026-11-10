import { expect, test } from '@playwright/test';

// Valid 1x1 red PNG
const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

test('unauthenticated video tab shows login gate', async ({ page }) => {
  await page.route('**/api/sources/topics', (route) => route.fulfill({ json: { ok: true, topics: [] } }));
  await page.goto('/?tab=video');

  const videoTab = page.getByRole('tab', { name: 'Tạo Video' });
  await expect(videoTab).toBeVisible();
  await expect(videoTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('Tạo Video AI (10s)')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Đăng nhập ngay' })).toBeVisible();
});

test('authenticated user uploads images in Profile, selects them in Video tab, and creates/cancels job', async ({
  page,
}) => {
  const uid = `e2e_vid_${Date.now()}`;

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

  await page.route('**/api/sources/topics*', (route) => route.fulfill({ json: { ok: true, topics: [] } }));
  await page.route('**/api/jobs', (route) => route.fulfill({ json: { ok: true, jobs: [] } }));

  // 1. Start on Video tab with no profile image uploaded yet -> must have 0 file inputs and navigate to Profile
  await page.goto('/?tab=video');
  await expect(page.getByText(/Chưa có ảnh chân dung mẫu/)).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);

  await page.getByRole('button', { name: 'Đi tới Hồ sơ' }).click();
  await expect(page.getByRole('tab', { name: 'Hồ sơ' })).toHaveAttribute('aria-selected', 'true');

  // 2. Upload Profile image and Context image in Profile tab against live backend
  const fileInputs = page.locator('.media-panel input[type="file"]');
  await expect(fileInputs).toHaveCount(2);

  await fileInputs.nth(0).setInputFiles({
    name: 'profile.png',
    mimeType: 'image/png',
    buffer: TINY_PNG,
  });

  const profileImg = page.locator('.media-panel img.profile-preview');
  await expect(profileImg).toBeVisible();
  await expect
    .poll(async () => profileImg.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBe(true);

  await fileInputs.nth(1).setInputFiles({
    name: 'context.png',
    mimeType: 'image/png',
    buffer: TINY_PNG,
  });

  const contextImg = page.locator('.media-panel .context-card img');
  await expect(contextImg).toBeVisible();
  await expect
    .poll(async () => contextImg.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBe(true);

  // 3. Switch to Video tab -> verify NO upload inputs exist, and uploaded images render & can be selected
  await page.getByRole('tab', { name: 'Tạo Video' }).click();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);
  await expect(page.getByText('Đã chọn ảnh đại diện mẫu')).toBeVisible();

  const videoTabProfileImg = page.locator('[data-testid^="profile-select-"] img');
  await expect(videoTabProfileImg).toBeVisible();
  await expect
    .poll(async () => videoTabProfileImg.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBe(true);

  // Select context image
  const videoTabContextCard = page.locator('[data-testid^="context-select-"]').first();
  await videoTabContextCard.click();
  await expect(page.getByText(/đã chọn 1\/1/)).toBeVisible();

  // 4. With 0 balance, Generate button is disabled and shows warning
  await page.getByPlaceholder(/Nhập lời thoại/).fill('Chia sẻ 3 bí quyết làm bánh mì giòn tan');
  await expect(page.getByText(/Số dư không đủ/)).toBeVisible();
  await expect(page.getByRole('button', { name: /Tạo video ngay/ })).toBeDisabled();

  // 5. Simulate funded balance & job creation / confirm modal / cancel flow
  let currentBalance = 500000;
  const mockJobs: any[] = [];

  await page.route('**/api/videos/estimate', async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        cost_micro: 230000,
        cost_usd: 0.23,
        duration_sec: 10,
        balance: currentBalance,
        balance_usd: currentBalance / 1000000,
        can_afford: currentBalance >= 230000,
      },
    });
  });

  await page.route('**/api/videos', async (route) => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      currentBalance -= 230000;
      const newJob = {
        id: 'job_e2e_1',
        user_id: uid,
        prompt: body.prompt,
        profile_media_id: body.profile_media_id,
        context_media_ids: body.context_media_ids,
        cost: 230000,
        cost_usd: 0.23,
        status: 'pending',
        video_path: null,
        error: null,
        created_at: new Date().toISOString(),
        started_at: null,
        finished_at: null,
      };
      mockJobs.push(newJob);
      await route.fulfill({ status: 201, json: { ok: true, job: newJob } });
    } else {
      await route.fulfill({ json: { ok: true, jobs: mockJobs } });
    }
  });

  await page.route('**/api/videos/job_e2e_1/cancel', async (route) => {
    currentBalance += 230000;
    mockJobs[0].status = 'cancelled';
    await route.fulfill({ json: { ok: true, cancelled: true } });
  });

  // Switch to Profile and back to Video tab to refresh estimate
  await page.getByRole('tab', { name: 'Hồ sơ' }).click();
  await page.getByRole('tab', { name: 'Tạo Video' }).click();

  await expect(page.getByText(/500,000 credits/)).toBeVisible();
  await page.locator('[data-testid^="context-select-"]').first().click();
  await page.getByPlaceholder(/Nhập lời thoại/).fill('Chia sẻ 3 bí quyết làm bánh mì giòn tan');

  const genBtn = page.getByRole('button', { name: /Tạo video ngay/ });
  await expect(genBtn).toBeEnabled();
  await genBtn.click();

  // Confirm modal displays cost and remaining balance
  await expect(page.getByText('Xác nhận tạo video AI')).toBeVisible();
  await expect(page.getByText('$0.27')).toBeVisible();
  await page.getByRole('button', { name: 'Xác nhận tạo' }).click();

  // Job appears in history as pending, balance updated to 270,000
  await expect(page.getByText('Đang chờ hàng đợi')).toBeVisible();
  await expect(page.getByText(/270,000 credits/)).toBeVisible();

  // Cancel pending job -> refunds to 500,000
  await page.getByRole('button', { name: 'Huỷ & Hoàn tiền' }).click();
  await expect(page.getByText('Đã huỷ')).toBeVisible();
  await expect(page.getByText(/500,000 credits/)).toBeVisible();

  // Verify collapsible history card: newly created job starts expanded, clicking header collapses it
  const videoCardHead = page.locator('.video-card-head').first();
  const videoCardBody = page.locator('.video-card-body').first();
  await expect(videoCardBody).toBeVisible();
  await videoCardHead.click();
  await expect(videoCardBody).not.toBeVisible();
  await videoCardHead.click();
  await expect(videoCardBody).toBeVisible();

  // 6. Return to Profile tab and delete the uploaded context & profile images
  await page.getByRole('tab', { name: 'Hồ sơ' }).click();
  await page.locator('.media-panel .context-card .delete-chip').click();
  await expect(page.locator('.media-panel .context-card')).toHaveCount(0);

  await page.locator('.media-panel .profile-card .media-action-btn.danger').click();
  await expect(page.getByText('Chưa có ảnh chân dung')).toBeVisible();
});

test('clicking Copy cho AI in Analysis immediately switches to Video tab and pastes prompt', async ({ page }) => {
  const uid = `e2e_copy_${Date.now()}`;
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

  const completedAnalysisJob = {
    id: 'job_analysis_1',
    status: 'completed',
    filename: 'all_topics.json',
    created_at: '2026-11-10T10:00:00Z',
    finished_at: '2026-11-10T10:02:00Z',
    current_sheet: null,
    total_sheets: 1,
    completed_sheets: 1,
    total_topics: 1,
    sheets: [
      {
        name: 'Ẩm thực gia đình',
        slug: 'am-thuc-gia-dinh',
        status: 'completed',
        targets: 1,
        reels: 3,
        pool_distribution: {},
        topics: [
          {
            title: '3 bí quyết làm bánh mì giòn rụm',
            hook: 'Đừng bao giờ nướng bánh mì ở nhiệt độ thấp!',
            angle: 'So sánh cách làm truyền thống và mẹo tiệm bánh',
            why_viral: 'Hook đánh trúng lỗi sai phổ biến của người nội trợ',
            outline: ['Mở đầu 3s với chiếc bánh bị ỉu', 'Bật mí nhiệt độ vàng 220 độ'],
            format: 'Talking head + B-roll',
            source_urls: ['https://www.facebook.com/reel/123456'],
            generated_by: 'agy',
          },
        ],
        error: null,
      },
    ],
    logs: [],
  };

  await page.route('**/api/sources/topics*', (route) => route.fulfill({ json: { ok: true, topics: [] } }));
  await page.route('**/api/jobs', (route) =>
    route.fulfill({ json: { ok: true, jobs: [completedAnalysisJob] } }),
  );
  await page.route('**/api/jobs/job_analysis_1', (route) => route.fulfill({ json: completedAnalysisJob }));
  await page.route('**/api/media*', (route) => route.fulfill({ json: { ok: true, media: [] } }));
  await page.route('**/api/videos*', (route) => route.fulfill({ json: { ok: true, jobs: [], balance: 0 } }));

  await page.goto('/?tab=analyzer&job_id=job_analysis_1');
  await expect(page.getByText('3 bí quyết làm bánh mì giòn rụm')).toBeVisible();

  await page.getByRole('button', { name: /Copy cho AI/ }).click();

  // Immediately switches to Video tab and pastes the formatted prompt into the textarea
  await expect(page.getByRole('tab', { name: 'Tạo Video' })).toHaveAttribute('aria-selected', 'true');
  const promptBox = page.getByPlaceholder(/Nhập lời thoại/);
  await expect(promptBox).toHaveValue(/### Chủ đề: 3 bí quyết làm bánh mì giòn rụm/);
  await expect(promptBox).toHaveValue(/Đừng bao giờ nướng bánh mì ở nhiệt độ thấp!/);
});
