import { render } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import App from './App';
import { apiJson } from './api';
import { CREATOR_PACKS } from './data/creatorPacks';

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('renders without crashing', () => {
    const { baseElement } = render(<App />);
    expect(baseElement).toBeDefined();
  });

  test('apiJson parses valid JSON response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, topics: [{ name: 'Test' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const data = await apiJson('/api/sources/topics');
    expect(data).toEqual({ ok: true, topics: [{ name: 'Test' }] });
  });

  test('apiJson safely handles empty 200 response without Unexpected end of JSON error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 200 }));
    const data = await apiJson('/api/sources/topics');
    expect(data).toEqual({});
  });

  test('apiJson handles 502 Bad Gateway proxy failure with readable error message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 502, statusText: 'Bad Gateway' }));
    await expect(apiJson('/api/sources/topics')).rejects.toThrow(
      'Không thể kết nối đến máy chủ backend (127.0.0.1:8765)',
    );
  });

  test('apiJson handles error payload from server', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'Thiếu tên chủ đề' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await expect(apiJson('/api/sources/topics')).rejects.toThrow('Thiếu tên chủ đề');
  });

  test('apiJson fetches run history from /api/jobs', async () => {
    const fakeJobs = [
      {
        id: 'job1',
        status: 'completed',
        filename: 'all_topics.json',
        created_at: '2026-11-09T00:00:00Z',
        total_sheets: 2,
        completed_sheets: 2,
        total_topics: 6,
      },
    ];
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, jobs: fakeJobs }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const data = await apiJson<{ ok: boolean; jobs: typeof fakeJobs }>('/api/jobs');
    expect(data.ok).toBe(true);
    expect(data.jobs).toHaveLength(1);
    expect(data.jobs[0].id).toBe('job1');
  });

  test('run persistence persists and restores active job id via localStorage', () => {
    localStorage.setItem('aibrand-active-job-id', 'job_persist_test');
    expect(localStorage.getItem('aibrand-active-job-id')).toBe('job_persist_test');
    localStorage.removeItem('aibrand-active-job-id');
    expect(localStorage.getItem('aibrand-active-job-id')).toBeNull();
  });

  test('CREATOR_PACKS contains 5 packs with ongoing months, maintenance pack and correct pricing', () => {
    expect(CREATOR_PACKS).toHaveLength(5);

    const pack50 = CREATOR_PACKS.find((p) => p.name === '50 creator list October');
    expect(pack50).toBeDefined();
    expect(pack50?.price).toBe('Free');
    expect(pack50?.disabled).toBe(false);
    expect(pack50?.count).toBe(50);
    expect(pack50?.targets).toHaveLength(50);

    const packBds = CREATOR_PACKS.find((p) => p.name === '1000 creator bđs November');
    expect(packBds).toBeDefined();
    expect(packBds?.price).toBe('5$');
    expect(packBds?.disabled).toBe(true);
    expect(packBds?.count).toBe(1000);

    const packDaoTao = CREATOR_PACKS.find((p) => p.name === '1000 creator đào tạo December');
    expect(packDaoTao).toBeDefined();
    expect(packDaoTao?.price).toBe('5$');
    expect(packDaoTao?.disabled).toBe(true);
    expect(packDaoTao?.count).toBe(1000);

    const packTongHop = CREATOR_PACKS.find((p) => p.name === '10000 creators tổng hợp December');
    expect(packTongHop).toBeDefined();
    expect(packTongHop?.price).toBe('20$');
    expect(packTongHop?.disabled).toBe(true);
    expect(packTongHop?.count).toBe(10000);

    const packMaintenance = CREATOR_PACKS.find((p) => p.name === 'bảo trì dài hạn');
    expect(packMaintenance).toBeDefined();
    expect(packMaintenance?.price).toBe('50$/year');
    expect(packMaintenance?.disabled).toBe(true);
  });

  test('apiJson fetches saved reels and handles delete action', async () => {
    const fakeReels = [
      {
        id: 'reel_1',
        reel_url: 'https://www.facebook.com/reel/123456789',
        platform: 'facebook',
        share_type: 'link_share',
        sender_name: 'Test Sender',
        message_text: 'Check this reel',
        created_at: '2026-11-12T10:00:00Z',
      },
    ];
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true, reels: fakeReels }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true, message: 'Đã xoá Reel đã lưu.' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );

    const getRes = await apiJson<{ ok: boolean; reels: typeof fakeReels }>('/api/saved-reels');
    expect(getRes.ok).toBe(true);
    expect(getRes.reels).toHaveLength(1);
    expect(getRes.reels[0].sender_name).toBe('Test Sender');

    const delRes = await apiJson<{ ok: boolean; message: string }>('/api/saved-reels/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: 'reel_1' }),
    });
    expect(delRes.ok).toBe(true);
  });

  test('apiJson fetches facebook status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, linked: true, fb_name: 'Nguyen Van A' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const statusRes = await apiJson<{ ok: boolean; linked: boolean; fb_name: string }>('/api/facebook/status');
    expect(statusRes.ok).toBe(true);
    expect(statusRes.linked).toBe(true);
    expect(statusRes.fb_name).toBe('Nguyen Van A');
  });
});
