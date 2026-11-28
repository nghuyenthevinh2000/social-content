import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import { formatTopicForAI } from './analysis/format';
import { MediaPanel } from './components/MediaPanel';
import { VideoTab, videoDownloadUrl, videoFileUrl } from './components/VideoTab';
import type { User } from './firebase';
import { clearEditDraft, loadEditDraft, saveEditDraft } from './videoEditDraft';

const mockUser = {
  uid: 'test_uid_123',
  email: 'test@example.com',
  displayName: 'Test User',
  metadata: { lastSignInTime: '2026-11-10T10:00:00Z' },
} as unknown as User;

describe('VideoTab and MediaPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('VideoTab renders login prompt when user is not logged in', () => {
    const onOpenAuth = vi.fn();
    render(<VideoTab user={null} onOpenAuth={onOpenAuth} />);

    expect(screen.getByText('Yêu cầu đăng nhập')).toBeDefined();
    expect(screen.getByText('Đăng nhập / Đăng ký')).toBeDefined();

    fireEvent.click(screen.getByText('Đăng nhập / Đăng ký'));
    expect(onOpenAuth).toHaveBeenCalled();
  });

  test('VideoTab has no file upload inputs and navigates to Profile when no profile image exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/api/videos/estimate') || url.includes('/api/credits')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ ok: true, balance: 500000, cost_micro: 230000, cost_usd: 0.23, can_afford: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, media: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ ok: true, jobs: [] }), { status: 200 }));
    });

    const onGoToProfile = vi.fn();
    const { container } = render(<VideoTab user={mockUser} onOpenAuth={vi.fn()} onGoToProfile={onGoToProfile} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Tạo AI Video' }));

    await waitFor(() => {
      expect(screen.getByText(/Chưa có ảnh chân dung mẫu/)).toBeDefined();
    });

    // VideoTab must NOT contain any direct file upload input
    expect(container.querySelectorAll('input[type="file"]').length).toBe(0);

    // Even with prompt text and balance, Generate button is disabled without profile image
    fireEvent.change(screen.getByPlaceholderText(/Nhập lời thoại/), {
      target: { value: 'Xin chào các bạn' },
    });
    const genBtn = screen.getByRole('button', { name: /Tạo video ngay/ });
    expect(genBtn).toBeDisabled();

    // Clicking "Đi tới Hồ sơ" navigates to Profile tab
    fireEvent.click(screen.getByRole('button', { name: 'Đi tới Hồ sơ' }));
    expect(onGoToProfile).toHaveBeenCalledTimes(1);
  });

  test('VideoTab disables generation when balance is insufficient (< $0.23)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/api/videos/estimate') || url.includes('/api/credits')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ ok: true, balance: 0, cost_micro: 230000, cost_usd: 0.23, can_afford: false }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              media: [
                {
                  id: 'prof1',
                  user_id: 'test_uid_123',
                  kind: 'profile',
                  path: '/path/to/prof1.jpg',
                  mime: 'image/jpeg',
                  bytes: 12345,
                  created_at: '2026-11-10T10:00:00Z',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ ok: true, jobs: [] }), { status: 200 }));
    });

    render(<VideoTab user={mockUser} onOpenAuth={vi.fn()} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Tạo AI Video' }));

    await waitFor(() => {
      expect(screen.getByText(/Số dư không đủ/)).toBeDefined();
    });

    fireEvent.change(screen.getByPlaceholderText(/Nhập lời thoại/), {
      target: { value: 'Thử tạo video khi hết tiền' },
    });
    expect(screen.getByRole('button', { name: /Tạo video ngay/ })).toBeDisabled();
  });

  test('VideoTab selects profile/context images from Profile, confirms cost, and manages job history', async () => {
    const postCalls: { url: string; body: any }[] = [];

    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || 'GET';

      if (url.includes('/api/videos/estimate')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ ok: true, balance: 500000, cost_micro: 230000, cost_usd: 0.23, can_afford: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              media: [
                {
                  id: 'prof1',
                  user_id: 'test_uid_123',
                  kind: 'profile',
                  path: '/path/to/prof1.jpg',
                  mime: 'image/jpeg',
                  bytes: 12345,
                  created_at: '2026-11-10T10:00:00Z',
                },
                {
                  id: 'ctx1',
                  user_id: 'test_uid_123',
                  kind: 'context',
                  path: '/path/to/ctx1.png',
                  mime: 'image/png',
                  bytes: 23456,
                  created_at: '2026-11-10T10:01:00Z',
                },
                {
                  id: 'ctx2',
                  user_id: 'test_uid_123',
                  kind: 'context',
                  path: '/path/to/ctx2.jpg',
                  mime: 'image/jpeg',
                  bytes: 34567,
                  created_at: '2026-11-10T10:02:00Z',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.endsWith('/api/videos') && method === 'POST') {
        const parsed = init?.body ? JSON.parse(String(init.body)) : {};
        postCalls.push({ url, body: parsed });
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              job: {
                id: 'vj_new',
                user_id: 'test_uid_123',
                prompt: parsed.prompt,
                profile_media_id: parsed.profile_media_id,
                context_media_ids: parsed.context_media_ids,
                cost: 230000,
                cost_usd: 0.23,
                status: 'pending',
                video_path: null,
                error: null,
                created_at: '2026-11-10T10:10:00Z',
                started_at: null,
                finished_at: null,
              },
            }),
            { status: 201, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/cancel') || url.includes('/delete')) {
        postCalls.push({ url, body: null });
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, cancelled: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.includes('/api/videos')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              jobs: [
                {
                  id: 'vj_pending',
                  user_id: 'test_uid_123',
                  prompt: 'Video đang chờ',
                  profile_media_id: 'prof1',
                  context_media_ids: [],
                  cost: 230000,
                  cost_usd: 0.23,
                  status: 'pending',
                  video_path: null,
                  error: null,
                  created_at: '2026-11-10T10:04:00Z',
                  started_at: null,
                  finished_at: null,
                },
                {
                  id: 'vj_done',
                  user_id: 'test_uid_123',
                  prompt: 'Prompt test video',
                  profile_media_id: 'prof1',
                  context_media_ids: [],
                  cost: 230000,
                  cost_usd: 0.23,
                  status: 'completed',
                  video_path: '/path/out.mp4',
                  error: null,
                  created_at: '2026-11-10T10:05:00Z',
                  started_at: null,
                  finished_at: null,
                },
                {
                  id: 'vj_fail',
                  user_id: 'test_uid_123',
                  prompt: 'Video lỗi',
                  profile_media_id: 'prof1',
                  context_media_ids: [],
                  cost: 230000,
                  cost_usd: 0.23,
                  status: 'failed',
                  video_path: null,
                  error: 'Omni timeout',
                  created_at: '2026-11-10T10:06:00Z',
                  started_at: null,
                  finished_at: null,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    const { container } = render(<VideoTab user={mockUser} onOpenAuth={vi.fn()} />);

    const historyTab = screen.getByRole('tab', { name: 'Lịch sử' });
    fireEvent.click(historyTab);
    expect(historyTab).toHaveAttribute('aria-selected', 'true');

    await waitFor(() => {
      expect(screen.getAllByText(/Prompt test video/)[0]).toBeDefined();
      expect(screen.getByText('Hoàn tất')).toBeDefined();
      expect(screen.getByText(/Omni timeout/)).toBeDefined();
    });

    // Verify <video> tag includes ?uid=test_uid_123
    const videoEl = container.querySelector('video.video-player') as HTMLVideoElement;
    expect(videoEl?.getAttribute('src')).toBe('/api/videos/vj_done/file?uid=test_uid_123');

    // Verify AI jobs show AI tag instead of duration
    const completedCard = screen.getAllByText('Prompt test video')[0].closest('.video-card');
    expect(completedCard?.querySelector('.duration-tag')?.textContent).toBe('AI');

    // Verify download & delete icon buttons are present in card header and redundant player toolbar link is removed
    const headerDownloadLink = container.querySelector('.video-card-head-right a.download-btn') as HTMLAnchorElement;
    expect(headerDownloadLink).toBeDefined();
    expect(headerDownloadLink?.getAttribute('href')).toBe('/api/videos/vj_done/file?uid=test_uid_123&download=1');
    expect(headerDownloadLink?.getAttribute('download')).toBe('video-vj_done.mp4');
    expect(headerDownloadLink?.getAttribute('aria-label')).toBe('Tải về');
    expect(headerDownloadLink?.querySelector('ion-icon')).not.toBeNull();
    const headerDeleteBtn = container.querySelector(
      '.video-card-head-right button[aria-label="Xoá"]',
    ) as HTMLButtonElement;
    expect(headerDeleteBtn).not.toBeNull();
    expect(headerDeleteBtn?.querySelector('ion-icon')).not.toBeNull();
    expect(container.querySelector('a.download-video-action')).toBeNull();

    // Pending and failed cards do not have download links
    const pendingCard = screen.getAllByText('Video đang chờ')[0].closest('.video-card');
    expect(pendingCard?.querySelector('a.download-btn')).toBeNull();
    const failedCard = screen.getAllByText('Video lỗi')[0].closest('.video-card');
    expect(failedCard?.querySelector('a.download-btn')).toBeNull();

    fireEvent.click(screen.getByRole('tab', { name: 'Tạo AI Video' }));

    await waitFor(() => {
      expect(screen.getByText('Đã chọn ảnh đại diện mẫu')).toBeDefined();
    });

    // Verify <img> tags include ?uid=test_uid_123 so browser requests succeed
    const profileImg = container.querySelector('[data-testid="profile-select-prof1"] img') as HTMLImageElement;
    expect(profileImg?.getAttribute('src')).toBe('/api/media/prof1?uid=test_uid_123');

    // Toggle context image ctx1 selection
    fireEvent.click(screen.getByTestId('context-select-ctx1'));
    expect(screen.getByText(/đã chọn 1\/2/)).toBeDefined();

    // Enter prompt and open Confirm Modal
    fireEvent.change(screen.getByPlaceholderText(/Nhập lời thoại/), {
      target: { value: 'Chia sẻ công thức làm bánh mì' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Tạo video ngay/ }));

    expect(screen.getByText('Xác nhận tạo video AI')).toBeDefined();
    expect(screen.getByText('$0.27')).toBeDefined(); // 0.50 - 0.23 = 0.27 remaining
    expect(screen.getByText('1 ảnh')).toBeDefined();

    // Confirm creation
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận tạo' }));
    await waitFor(() => {
      expect(postCalls.some((c) => c.url.endsWith('/api/videos'))).toBe(true);
    });
    const createCall = postCalls.find((c) => c.url.endsWith('/api/videos'))!;
    expect(createCall.body).toEqual({
      prompt: 'Chia sẻ công thức làm bánh mì',
      profile_media_id: 'prof1',
      context_media_ids: ['ctx1'],
      duration: 15,
    });

    // Test cancel pending job button
    fireEvent.click(screen.getByRole('button', { name: 'Huỷ & Hoàn tiền' }));
    await waitFor(() => {
      expect(postCalls.some((c) => c.url.includes('/api/videos/vj_pending/cancel'))).toBe(true);
    });
  });

  test('VideoTab defaults to Edit Video mode, submits local/history edit jobs, and switches to Generate AI Video', async () => {
    const createObjectUrlSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:local-video-preview');
    const revokeObjectUrlSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const editCalls: { url: string; headers: any; body: any }[] = [];

    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || 'GET';
      if (url.includes('/api/videos/estimate')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ ok: true, balance: 500000, cost_micro: 230000, cost_usd: 0.23, can_afford: true }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, media: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.endsWith('/api/videos/edit') && method === 'POST') {
        const hdrs = Object.fromEntries(new Headers(init?.headers).entries());
        editCalls.push({ url, headers: hdrs, body: init?.body });
        const promptText = hdrs['x-edit-prompt']
          ? decodeURIComponent(hdrs['x-edit-prompt'])
          : JSON.parse(String(init?.body)).prompt;
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              job: {
                id: `ve_${editCalls.length}`,
                user_id: 'test_uid_123',
                prompt: promptText,
                profile_media_id: '',
                context_media_ids: [],
                cost: 0,
                cost_usd: 0,
                status: 'pending',
                video_path: null,
                error: null,
                created_at: '2026-11-10T10:15:00Z',
                started_at: null,
                finished_at: null,
                job_type: 'edit',
              },
            }),
            { status: 201, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/videos')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              jobs: [
                {
                  id: 'vj_done',
                  user_id: 'test_uid_123',
                  prompt: 'Video mẫu hoàn tất',
                  profile_media_id: 'prof1',
                  context_media_ids: [],
                  cost: 230000,
                  cost_usd: 0.23,
                  status: 'completed',
                  video_path: '/path/out.mp4',
                  error: null,
                  created_at: '2026-11-10T10:05:00Z',
                  started_at: null,
                  finished_at: null,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    const { container } = render(
      <VideoTab user={mockUser} onOpenAuth={vi.fn()} editReferenceUrl="https://www.facebook.com/reel/999" />,
    );

    const editTab = screen.getByRole('tab', { name: 'Edit Video' });
    const genTab = screen.getByRole('tab', { name: 'Tạo AI Video' });
    expect(editTab).toHaveAttribute('aria-selected', 'true');
    expect(genTab).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByText('https://www.facebook.com/reel/999')).toBeDefined();
    expect(container.querySelector('.video-edit-history')).toBeNull();

    const applyBtn = screen.getByRole('button', { name: 'Áp dụng chỉnh sửa' });
    expect(applyBtn).toBeDisabled();

    // Pick a local video file and submit edit
    const fileInput = container.querySelector('input[type="file"][accept="video/*"]') as HTMLInputElement;
    expect(fileInput).not.toBeNull();
    const file = new File(['video-bytes'], 'sample-clip.mp4', { type: 'video/mp4' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalledWith(file);
      const preview = container.querySelector('.video-edit-preview video.video-player') as HTMLVideoElement;
      expect(preview?.getAttribute('src')).toBe('blob:local-video-preview');
    });
    expect(screen.getByText('sample-clip.mp4')).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText(/Mô tả chỉnh sửa/), {
      target: { value: 'Thêm phụ đề tiếng Việt' },
    });
    expect(applyBtn).toBeEnabled();
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(editCalls.length).toBe(1);
      const toast = document.querySelector('ion-toast');
      expect(toast).not.toBeNull();
      expect(toast?.getAttribute('message')).toBe('Đã gửi yêu cầu chỉnh sửa video!');
      expect(revokeObjectUrlSpy).toHaveBeenCalledWith('blob:local-video-preview');
    });
    expect(decodeURIComponent(editCalls[0].headers['x-edit-prompt'])).toBe('Thêm phụ đề tiếng Việt');
    expect(decodeURIComponent(editCalls[0].headers['x-reference-url'])).toBe('https://www.facebook.com/reel/999');

    // Switch to Generate AI Video
    fireEvent.click(genTab);
    expect(genTab).toHaveAttribute('aria-selected', 'true');
    expect(container.querySelectorAll('input[type="file"]').length).toBe(0);
  });

  test('VideoTab preserves controlled editSourceFile across unmount/remount (tab switch + Copy Edit)', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:persisted-video');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true, media: [], jobs: [], balance: 0 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const file = new File(['video-bytes'], 'my-uploaded-clip.mp4', { type: 'video/mp4' });
    const { unmount } = render(
      <VideoTab user={mockUser} onOpenAuth={vi.fn()} editSourceFile={file} editPrompt="" editReferenceUrl="" />,
    );
    await waitFor(() => {
      expect(screen.getByText('my-uploaded-clip.mp4')).toBeDefined();
    });

    // Simulate switching away to Analyze tab and returning via Copy Edit
    unmount();
    const { container } = render(
      <VideoTab
        user={mockUser}
        onOpenAuth={vi.fn()}
        editSourceFile={file}
        editPrompt="Copy edit style"
        editReferenceUrl="https://www.facebook.com/reel/555"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('my-uploaded-clip.mp4')).toBeDefined();
      const preview = container.querySelector('.video-edit-preview video.video-player') as HTMLVideoElement;
      expect(preview?.getAttribute('src')).toBe('blob:persisted-video');
    });
    expect(screen.getByText('https://www.facebook.com/reel/555')).toBeDefined();
  });

  test('videoEditDraft persists and clears edit prompt, reference URL, and historyJobId', () => {
    localStorage.clear();
    expect(loadEditDraft()).toEqual({ prompt: '', referenceUrl: '', historyJobId: null, templateId: null });

    saveEditDraft({
      prompt: 'Add captions and zoom',
      referenceUrl: 'https://www.tiktok.com/@a/video/1',
      historyJobId: 'vj_123',
      templateId: 'kinetic-explainer',
    });
    expect(loadEditDraft()).toEqual({
      prompt: 'Add captions and zoom',
      referenceUrl: 'https://www.tiktok.com/@a/video/1',
      historyJobId: 'vj_123',
      templateId: 'kinetic-explainer',
    });

    clearEditDraft();
    expect(loadEditDraft()).toEqual({ prompt: '', referenceUrl: '', historyJobId: null, templateId: null });
  });

  test('VideoTab renders progressbar for active jobs and omits it for completed/failed jobs', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/api/videos/estimate')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, balance: 500000, cost_micro: 230000, cost_usd: 0.23 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, media: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.includes('/api/videos')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              jobs: [
                {
                  id: 've_running',
                  user_id: 'test_uid_123',
                  prompt: 'Editing video',
                  profile_media_id: '',
                  context_media_ids: [],
                  cost: 0,
                  cost_usd: 0,
                  status: 'running',
                  job_type: 'edit',
                  video_path: null,
                  error: null,
                  created_at: new Date(Date.now() - 20_000).toISOString(),
                  started_at: new Date(Date.now() - 20_000).toISOString(),
                  finished_at: null,
                },
                {
                  id: 'vj_done',
                  user_id: 'test_uid_123',
                  prompt: 'Done video',
                  profile_media_id: 'prof1',
                  context_media_ids: [],
                  cost: 230000,
                  cost_usd: 0.23,
                  status: 'completed',
                  video_path: '/path/out.mp4',
                  error: null,
                  created_at: '2026-11-10T10:05:00Z',
                  started_at: null,
                  finished_at: null,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    render(<VideoTab user={mockUser} onOpenAuth={vi.fn()} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Lịch sử' }));

    const bars = await screen.findAllByRole('progressbar');
    expect(bars).toHaveLength(1);
    const pct = Number(bars[0].getAttribute('aria-valuenow'));
    expect(pct).toBeGreaterThanOrEqual(10);
    expect(pct).toBeLessThanOrEqual(95);
    expect(screen.getByText('Đang phân tích video…')).toBeDefined();
  });

  test('MediaPanel renders authenticated image URLs with uid', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              media: [
                {
                  id: 'prof_abc',
                  user_id: 'test_uid_123',
                  kind: 'profile',
                  path: '/path/prof.jpg',
                  mime: 'image/jpeg',
                  bytes: 15360,
                  created_at: '2026-11-10T10:00:00Z',
                },
                {
                  id: 'ctx1',
                  user_id: 'test_uid_123',
                  kind: 'context',
                  path: '/path/ctx.jpg',
                  mime: 'image/jpeg',
                  bytes: 20000,
                  created_at: '2026-11-10T10:00:00Z',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    const { container } = render(<MediaPanel />);

    await waitFor(() => {
      expect(screen.getByText('Ảnh chân dung mẫu (Profile)')).toBeDefined();
      expect(screen.getByText('Ảnh bối cảnh / Sản phẩm (Context)')).toBeDefined();
    });

    const imgs = Array.from(container.querySelectorAll('img')).map((img) => img.getAttribute('src'));
    expect(imgs).toContain('/api/media/prof_abc?uid=test_uid_123');
    expect(imgs).toContain('/api/media/ctx1?uid=test_uid_123');
  });

  test('formatTopicForAI uses backend AI generated prompt directly', () => {
    const aiPrompt = `[CAMERA & COMPOSITION]\nVertical 9:16 mobile POV\n\n[ACTION & TIMECODE]\n00:00 - 00:15\n\n[AUDIO & DIALOGUE]\nSpoken Vietnamese`;
    const topic = {
      title: 'Bao lì xì giấy mỹ thuật',
      hook: 'Có ai lấy giấy mỹ thuật này in bao lì xì Tết chưa?',
      angle: 'Trải nghiệm thực tế xưởng in',
      why_viral: 'Hiếu kỳ về chất liệu giấy cao cấp',
      outline: ['1. Chọn định lượng giấy 180gsm phù hợp', '2. Kỹ thuật ép kim vàng sắc nét'],
      format: 'Reels 15s UGC',
      source_urls: [],
      generated_by: 'agent',
      prompt: aiPrompt,
    };

    expect(formatTopicForAI(topic)).toBe(aiPrompt);

    // Fallback if prompt is not present
    const legacyTopic = { ...topic, prompt: undefined };
    const fallbackText = formatTopicForAI(legacyTopic, 'Nhóm in ấn');
    expect(fallbackText).toContain('### Chủ đề: Bao lì xì giấy mỹ thuật');
    expect(fallbackText).toContain('Nhóm in ấn');
    expect(fallbackText).toContain('Có ai lấy giấy mỹ thuật này in bao lì xì Tết chưa?');
  });

  test('videoFileUrl and videoDownloadUrl generate proper URLs', () => {
    const job = {
      id: 'job_456',
      user_id: 'user_789',
    } as any;

    expect(videoFileUrl(job)).toBe('/api/videos/job_456/file?uid=user_789');
    expect(videoDownloadUrl(job)).toBe('/api/videos/job_456/file?uid=user_789&download=1');
  });

  test('VideoTab uses POST /api/videos/edit-plan and renders locally when WebCodecs is supported', async () => {
    const clientRenderMod = await import('./videoClientRender');
    const draftMod = await import('./videoEditDraft');
    vi.spyOn(clientRenderMod, 'canRenderVideoOnClient').mockResolvedValue(true);
    vi.spyOn(clientRenderMod, 'probeAndExtractKeyframes').mockResolvedValue({
      probe: {
        width: 720,
        height: 1280,
        duration: 10,
        fps: 30,
        has_audio: true,
        speech_segments: [{ start: 0.5, end: 4.5, energy: 0.2 }],
        cuts: [],
      },
      keyframes_b64: ['ZmFrZWpwZw=='],
      audio_b64: 'UklGRg==',
      decomposition: {
        speech_segments: [{ start: 0.5, end: 4.5, energy: 0.2 }],
        cuts: [],
        speech_duration_sec: 4.0,
        speaking_ratio: 0.4,
      },
    });
    const renderSpy = vi
      .spyOn(clientRenderMod, 'renderVideoEditPlan')
      .mockResolvedValue(new Blob(['rendered-mp4'], { type: 'video/mp4' }));
    const blobStore = new Map<string, Blob>();
    vi.spyOn(draftMod, 'saveJobBlob').mockImplementation(async (k, b) => {
      blobStore.set(k, b);
    });
    vi.spyOn(draftMod, 'loadJobBlob').mockImplementation(async (k) => blobStore.get(k) ?? null);
    vi.spyOn(draftMod, 'deleteJobBlob').mockImplementation(async (k) => {
      blobStore.delete(k);
    });
    vi.spyOn(URL, 'createObjectURL').mockImplementation((obj: any) =>
      obj instanceof Blob && obj.size === 12 ? 'blob:rendered-local-mp4' : 'blob:source-preview',
    );
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const planJob: any = {
      id: 'vp_1',
      user_id: 'test_uid_123',
      prompt: 'Client plan captions',
      profile_media_id: '',
      context_media_ids: [],
      cost: 0,
      cost_usd: 0,
      status: 'completed',
      video_path: 'videos/test_uid_123/vp_1/edit_config.json',
      error: null,
      created_at: '2026-11-27T09:00:00Z',
      started_at: null,
      finished_at: null,
      job_type: 'edit_plan',
    };
    const postedUrls: string[] = [];

    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || 'GET';
      if (url.endsWith('/api/videos/edit-plan') && method === 'POST') {
        postedUrls.push(url);
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, job: planJob }), {
            status: 201,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.endsWith('/api/videos/vp_1/plan')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, plan: { width: 720, height: 1280, fps: 24, effects: [] } }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.endsWith('/api/videos/vp_1/file') && method === 'POST') {
        postedUrls.push(url);
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              job: { ...planJob, video_path: 'videos/test_uid_123/vp_1/output.mp4' },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/videos/estimate')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, balance: 500000, cost_micro: 0, cost_usd: 0 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.includes('/api/media')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, media: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      if (url.includes('/api/videos')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, jobs: postedUrls.length ? [planJob] : [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    const srcFile = new File(['raw-mp4'], 'clip.mp4', { type: 'video/mp4' });
    render(
      <VideoTab user={mockUser} onOpenAuth={vi.fn()} editSourceFile={srcFile} editPrompt="Client plan captions" />,
    );

    const applyBtn = await screen.findByRole('button', { name: 'Áp dụng chỉnh sửa' });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(postedUrls.some((u) => u.endsWith('/api/videos/edit-plan'))).toBe(true);
    });
    await waitFor(() => {
      expect(renderSpy).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(postedUrls.some((u) => u.endsWith('/api/videos/vp_1/file'))).toBe(true);
    });
  });

  test('drawEffectsOnCanvas renders table, info.tag, highlight_lines, and top-level subtitles', async () => {
    const { drawEffectsOnCanvas } = await import('./videoClientRender');
    const calls: string[] = [];
    const mockCtx: any = {
      save: () => {},
      restore: () => {},
      clearRect: () => {},
      drawImage: () => {},
      beginPath: () => {},
      moveTo: () => {},
      arcTo: () => {},
      closePath: () => {},
      fill: () => {},
      fillRect: () => {},
      strokeText: (t: string) => calls.push(`stroke:${t}`),
      fillText: (t: string) => calls.push(`fill:${t}`),
      filter: 'none',
      fillStyle: '#000',
      strokeStyle: '#000',
      font: '',
      textAlign: 'center',
      textBaseline: 'top',
      globalAlpha: 1,
      lineJoin: 'round',
      lineWidth: 1,
      shadowColor: '',
      shadowBlur: 0,
      shadowOffsetY: 0,
    };

    drawEffectsOnCanvas(mockCtx, {} as CanvasImageSource, 360, 640, 720, 1280, 2.0, [
      {
        type: 'text_box',
        variant: 'info',
        tag: 'Tóm tắt',
        title: 'Điểm chính',
        body: ['Chi tiết'],
        start: 0,
        end: 5,
      },
      {
        type: 'text_box',
        variant: 'table',
        headers: ['Mục', 'Giá trị'],
        rows: [['1. Thuê', 'Tốt']],
        start: 0,
        end: 5,
      },
      {
        type: 'subtitles',
        color: '#93E227',
        uppercase: true,
        items: [{ start: 1, end: 3, text: 'xin chào' }],
      },
    ]);

    expect(calls).toContain('fill:Tóm tắt');
    expect(calls).toContain('fill:Điểm chính');
    expect(calls).toContain('fill:Mục');
    expect(calls).toContain('fill:1. Thuê');
    expect(calls).toContain('stroke:XIN CHÀO');
    expect(calls).toContain('fill:XIN CHÀO');
  });

  test('VideoTab displays templates, enforces owner-only delete, allows template-only edit, and saves produced template', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input: any, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/videos/templates/tpl_mine/delete') && init?.method === 'POST') {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
        );
      }
      if (url.includes('/api/videos/templates') && init?.method === 'POST') {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              template: {
                id: 'tpl_new',
                slug: 'my-saved-tpl',
                name: 'My Saved Tpl',
                source: 'user',
                author_id: 'test_uid_123',
                is_owner: true,
                visibility: 'public',
                config: { width: 1080, height: 1920 },
              },
            }),
            { status: 201, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/videos/templates')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              templates: [
                {
                  id: 'kinetic-explainer',
                  slug: 'kinetic-explainer',
                  name: 'kinetic-explainer',
                  source: 'builtin',
                  author_id: null,
                  is_owner: false,
                  visibility: 'public',
                  config: { width: 1080, height: 1920, fps: 30, theme: { bgTop: '#f8f4ec', bgBot: '#ede4d3' } },
                },
                {
                  id: 'tpl_mine',
                  slug: 'tpl-mine',
                  name: 'My Own Style',
                  source: 'user',
                  author_id: 'test_uid_123',
                  is_owner: true,
                  visibility: 'public',
                  config: { width: 1080, height: 1920, fps: 30 },
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/videos/edit') && init?.method === 'POST') {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              job: {
                id: 'job_edit_tpl',
                user_id: 'test_uid_123',
                prompt: 'Apply template: kinetic-explainer',
                profile_media_id: '',
                context_media_ids: [],
                cost: 0,
                cost_usd: 0,
                status: 'pending',
                video_path: null,
                error: null,
                created_at: '2026-11-27T12:00:00Z',
                started_at: null,
                finished_at: null,
                job_type: 'edit',
                template_id: 'kinetic-explainer',
              },
            }),
            { status: 201, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.endsWith('/api/videos')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              jobs: [
                {
                  id: 'job_done_1',
                  user_id: 'test_uid_123',
                  prompt: 'Edited clip',
                  profile_media_id: '',
                  context_media_ids: [],
                  cost: 0,
                  cost_usd: 0,
                  status: 'completed',
                  video_path: 'videos/test_uid_123/job_done_1/output.mp4',
                  error: null,
                  created_at: '2026-11-27T12:00:00Z',
                  started_at: null,
                  finished_at: null,
                  job_type: 'edit',
                  produced_template: { width: 1080, height: 1920, color_grade: { contrast: 1.05 } },
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/videos/estimate') || url.includes('/api/credits')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, balance: 500000, cost_micro: 230000, cost_usd: 0.23 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ ok: true, media: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    });

    const mockFile = new File([new Uint8Array([1, 2, 3])], 'clip.mp4', { type: 'video/mp4' });
    render(<VideoTab user={mockUser} onOpenAuth={vi.fn()} editSourceFile={mockFile} />);

    // Both templates render; only owner template shows delete button
    await waitFor(() => {
      expect(screen.getByTestId('template-card-kinetic-explainer')).toBeDefined();
      expect(screen.getByTestId('template-card-tpl_mine')).toBeDefined();
    });
    expect(screen.getAllByRole('button', { name: 'Xoá mẫu' })).toHaveLength(1);

    // Delete owner template
    fireEvent.click(screen.getByRole('button', { name: 'Xoá mẫu' }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/videos/templates/tpl_mine/delete'),
        expect.objectContaining({ method: 'POST' }),
      );
      expect(screen.queryByTestId('template-card-tpl_mine')).toBeNull();
    });

    // Selecting built-in template enables Apply Edits even with empty prompt
    const applyBtn = screen.getByRole('button', { name: 'Áp dụng chỉnh sửa' });
    expect(applyBtn).toBeDisabled();
    fireEvent.click(screen.getByTestId('template-card-kinetic-explainer'));
    expect(applyBtn).not.toBeDisabled();

    // Switch to History, expand completed job, and save produced template
    fireEvent.click(screen.getByRole('tab', { name: 'Lịch sử' }));
    await waitFor(() => {
      expect(screen.getAllByText('Edited clip').length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getAllByText('Edited clip')[0]);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Lưu thành mẫu' })).toBeDefined();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thành mẫu' }));
    fireEvent.change(screen.getByLabelText('Tên mẫu'), { target: { value: 'My Saved Tpl' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mẫu' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/videos/templates'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ job_id: 'job_done_1', name: 'My Saved Tpl', visibility: 'public' }),
        }),
      );
    });
  });
});
