import { render } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import App from './App';
import { apiJson } from './api';

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
});
