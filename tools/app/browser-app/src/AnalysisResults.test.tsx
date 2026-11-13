import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import Home from './pages/Home';

const profileJobFixture = {
  id: 'job_profile_1',
  status: 'completed',
  filename: 'all_topics.json',
  created_at: '2026-11-12T10:00:00Z',
  current_sheet: null,
  sheets: [
    {
      name: 'Ẩm thực',
      slug: 'am-thuc',
      status: 'completed',
      targets: 2,
      reels: 5,
      pool_distribution: { pool_1: 3, pool_2: 2 },
      source_breakdown: { glasser_api: ['chan1'], cache: ['chan2'], empty: [] },
      error: null,
      notice: null,
      topics: [
        {
          title: 'Low views topic',
          hook: 'Hook low',
          angle: 'Angle low',
          why_viral: 'Why low',
          outline: ['Step 1'],
          format: 'talking_head',
          source_urls: ['https://www.facebook.com/reel/111'],
          generated_by: 'agent',
          views: 1000,
          velocity_per_hour: 100,
          author_handle: 'chef_a',
          transcript: 'Transcript low',
        },
        {
          title: 'High views topic',
          hook: 'Hook high',
          angle: 'Angle high',
          why_viral: 'Why high',
          outline: ['Step 1', 'Step 2'],
          format: 'talking_head',
          source_urls: ['https://www.facebook.com/reel/222'],
          generated_by: 'agent',
          views: 50000,
          velocity_per_hour: 2500,
          author_handle: 'chef_b',
          transcript: 'Transcript high',
        },
      ],
    },
  ],
  logs: [{ at: '2026-11-12T10:00:05Z', sheet: 'am-thuc', message: 'Done' }],
};

const savedReelJobFixture = {
  id: 'job_reel_1',
  job_kind: 'reel',
  status: 'completed',
  filename: 'Reel đã lưu',
  created_at: '2026-11-12T11:00:00Z',
  current_sheet: null,
  sheets: [
    {
      name: 'Reel đã lưu',
      slug: 'saved-reel-1',
      status: 'completed',
      targets: 2,
      reels: 2,
      pool_distribution: { pool_1: 1 },
      source_breakdown: { glasser_api: ['reel_1'] },
      error: null,
      notice: null,
      topics: [
        {
          title: 'First saved reel',
          hook: 'Reel hook 1',
          angle: 'Reel angle 1',
          why_viral: 'Reel why viral 1',
          outline: ['Open', 'Close'],
          format: 'single_reel',
          source_urls: ['https://www.facebook.com/reel/333'],
          generated_by: 'agent',
          views: 500,
          author_handle: 'creator_1',
          transcript: 'Reel transcript 1',
          visual: 'Close-up cooking shots',
        },
        {
          title: 'Second saved reel',
          hook: 'Reel hook 2',
          angle: 'Reel angle 2',
          why_viral: 'Reel why viral 2',
          outline: ['Intro'],
          format: 'single_reel',
          source_urls: ['https://www.facebook.com/reel/444'],
          generated_by: 'agent',
          views: 9000,
          author_handle: 'creator_2',
          transcript: 'Reel transcript 2',
        },
      ],
    },
  ],
  logs: [{ at: '2026-11-12T11:00:05Z', sheet: 'saved-reel-1', message: 'Reel done' }],
};

function setupMockFetch(jobsById: Record<string, unknown>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input);
    const path = new URL(url, 'http://localhost').pathname;
    if (path.startsWith('/api/jobs/')) {
      const id = path.replace('/api/jobs/', '');
      const job = jobsById[id];
      if (job) {
        return new Response(JSON.stringify(job), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
    }
    if (path === '/api/jobs') {
      return new Response(JSON.stringify({ ok: true, jobs: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (path === '/api/sources/topics') {
      return new Response(JSON.stringify({ ok: true, topics: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (path === '/api/saved-reels') {
      return new Response(JSON.stringify({ ok: true, reels: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
}

describe('Analysis results rendering', () => {
  beforeEach(() => {
    const uid = 'vitest_analysis_user';
    localStorage.setItem(`aibrand-tour-done-${uid}`, '1');
    (globalThis as Record<string, unknown>).__E2E_TEST_USER__ = {
      uid,
      email: 'test@example.com',
      displayName: 'Test User',
      metadata: { lastSignInTime: '2026-11-12T09:00:00Z' },
      providerData: [],
      getIdToken: async () => 'fake-token',
    };
  });

  afterEach(() => {
    delete (globalThis as Record<string, unknown>).__E2E_TEST_USER__;
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test('renders profile job with pools, source breakdown, and topics sorted by views', async () => {
    setupMockFetch({ job_profile_1: profileJobFixture });

    render(
      <MemoryRouter initialEntries={['/?tab=analyzer&job_id=job_profile_1']}>
        <Home />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Ẩm thực')).toBeInTheDocument();
    });

    expect(screen.getByText(/2 kênh · 5 reel/)).toBeInTheDocument();
    expect(screen.getByText('P1 · 3')).toBeInTheDocument();
    expect(screen.getByText('⚡ Glasser API: 1 kênh')).toBeInTheDocument();
    expect(screen.getByText('💾 Cache: 1 kênh')).toBeInTheDocument();

    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(['High views topic', 'Low views topic']);
    expect(screen.getByText('Transcript high')).toBeInTheDocument();
  });

  test('renders saved-reel job without profile hints, preserving order, and showing visual', async () => {
    setupMockFetch({ job_reel_1: savedReelJobFixture });

    render(
      <MemoryRouter initialEntries={['/?tab=analyzer&job_id=job_reel_1']}>
        <Home />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('First saved reel')).toBeInTheDocument();
    });

    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(['First saved reel', 'Second saved reel']);
    expect(screen.getByText('333')).toBeInTheDocument();
    expect(screen.getByText('2 reel')).toBeInTheDocument();
    expect(screen.getByText('Close-up cooking shots')).toBeInTheDocument();
    expect(screen.getByText('Reel transcript 1')).toBeInTheDocument();
    expect(screen.queryByText(/P1 ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Glasser API:/)).not.toBeInTheDocument();
  });
});
