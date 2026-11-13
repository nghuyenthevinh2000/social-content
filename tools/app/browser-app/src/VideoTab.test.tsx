import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import { formatTopicForAI } from './analysis/format';
import { MediaPanel } from './components/MediaPanel';
import { VideoTab, videoDownloadUrl, videoFileUrl } from './components/VideoTab';
import type { User } from './firebase';

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

    expect(screen.getByText(/Tạo Video AI \(\d+s\)/)).toBeDefined();
    expect(screen.getByText('Đăng nhập ngay')).toBeDefined();

    fireEvent.click(screen.getByText('Đăng nhập ngay'));
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

    await waitFor(() => {
      expect(screen.getByText(/\$0\.50/)).toBeDefined();
      expect(screen.getByText('Đã chọn ảnh đại diện mẫu')).toBeDefined();
      expect(screen.getAllByText(/Prompt test video/)[0]).toBeDefined();
      expect(screen.getByText('Hoàn tất')).toBeDefined();
      expect(screen.getByText(/Omni timeout/)).toBeDefined();
    });

    // Verify <img> tags include ?uid=test_uid_123 so browser requests succeed
    const profileImg = container.querySelector('[data-testid="profile-select-prof1"] img') as HTMLImageElement;
    expect(profileImg?.getAttribute('src')).toBe('/api/media/prof1?uid=test_uid_123');

    // Verify <video> tag includes ?uid=test_uid_123
    const videoEl = container.querySelector('video.video-player') as HTMLVideoElement;
    expect(videoEl?.getAttribute('src')).toBe('/api/videos/vj_done/file?uid=test_uid_123');

    // Verify download link is present in card header and redundant player toolbar link is removed
    const headerDownloadLink = container.querySelector('.video-card-head-right a.download-btn') as HTMLAnchorElement;
    expect(headerDownloadLink).toBeDefined();
    expect(headerDownloadLink?.getAttribute('href')).toBe('/api/videos/vj_done/file?uid=test_uid_123&download=1');
    expect(headerDownloadLink?.getAttribute('download')).toBe('video-vj_done.mp4');
    expect(headerDownloadLink?.textContent).toBe('Tải về');
    expect(container.querySelector('a.download-video-action')).toBeNull();

    // Pending and failed cards do not have download links
    const pendingCard = screen.getAllByText('Video đang chờ')[0].closest('.video-card');
    expect(pendingCard?.querySelector('a.download-btn')).toBeNull();
    const failedCard = screen.getAllByText('Video lỗi')[0].closest('.video-card');
    expect(failedCard?.querySelector('a.download-btn')).toBeNull();

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

  test('MediaPanel renders authenticated image URLs with uid and displays credit balance', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/api/credits')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, balance: 230000 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
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
      expect(screen.getByText(/\$0\.23/)).toBeDefined();
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
});
