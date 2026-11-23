import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { AnalyzerTab } from './components/AnalyzerTab';
import { BrandPanel } from './components/BrandPanel';
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
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
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

  test('renders saved-reel job without profile hints, preserving order', async () => {
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
    expect(screen.getByText('Reel transcript 1')).toBeInTheDocument();
    expect(screen.queryByText(/P1 ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Glasser API:/)).not.toBeInTheDocument();
  });

  test('renders keyword search job with 3 expanded queries, creators, and save actions', async () => {
    const keywordJobFixture = {
      id: 'job_kw_1',
      job_kind: 'keyword',
      status: 'completed',
      filename: 'gyno conditions',
      created_at: '2026-11-16T10:00:00Z',
      current_sheet: null,
      sheets: [
        {
          name: 'gyno conditions',
          slug: 'gyno-conditions',
          status: 'completed',
          targets: 1,
          reels: 1,
          pool_distribution: {},
          queries: [
            { kind: 'original', text: 'gyno conditions' },
            { kind: 'abbreviation', text: 'gynecomastia' },
            { kind: 'vi', text: 'nữ hóa tuyến vú' },
          ],
          creators: [
            {
              name: 'Dr YT',
              handle: 'dryt',
              url: 'https://www.youtube.com/@dryt',
              platform: 'youtube',
              followers: 120000,
              video_count: 1,
              top_views: 50000,
              relevance: 'direct',
              why_relevant: 'Covers gynecomastia directly.',
            },
            {
              name: 'Off Topic Creator',
              handle: 'offtopic',
              url: 'https://www.youtube.com/@offtopic',
              platform: 'youtube',
              followers: 50000,
              video_count: 1,
              top_views: 10000,
              relevance: 'off_topic',
              why_relevant: 'Unrelated music channel.',
            },
          ],
          error: null,
          notice: null,
          topics: [
            {
              title: 'Gynecomastia Explained',
              hook: '',
              angle: '',
              why_viral: '',
              outline: [],
              format: 'youtube',
              source_urls: ['https://www.youtube.com/watch?v=yt1'],
              reel_url: 'https://www.youtube.com/watch?v=yt1',
              platform: 'youtube',
              matched_query: 'gynecomastia',
              author_name: 'Dr YT',
              author_handle: 'dryt',
              author_url: 'https://www.youtube.com/@dryt',
              generated_by: 'glasser',
              views: 50000,
            },
          ],
        },
      ],
      logs: [],
    };

    const fetchSpy = setupMockFetch({ job_kw_1: keywordJobFixture });

    render(
      <MemoryRouter initialEntries={['/?tab=analyzer&job_id=job_kw_1']}>
        <Home />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Original: gyno conditions')).toBeInTheDocument();
    });

    expect(screen.getByText('Abbr: gynecomastia')).toBeInTheDocument();
    expect(screen.getByText('VI: nữ hóa tuyến vú')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Dr YT/i })).toHaveAttribute('href', 'https://www.youtube.com/@dryt');
    expect(screen.getByText('120K followers')).toBeInTheDocument();
    expect(screen.queryByText('direct')).not.toBeInTheDocument();
    expect(screen.queryByText(/Off Topic Creator/)).not.toBeInTheDocument();
    expect(screen.getByText('Covers gynecomastia directly.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Copy cho AI/i })).not.toBeInTheDocument();

    const subpanels = document.querySelectorAll('details.keyword-subpanel');
    expect(subpanels).toHaveLength(1);
    subpanels.forEach((el) => expect((el as HTMLDetailsElement).open).toBe(false));
    expect(document.querySelector('.topics-carousel')).not.toBeInTheDocument();

    expect(screen.getByRole('button', { name: 'Thêm tất cả kênh' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Phân tích các kênh' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Lưu tất cả video' })).not.toBeInTheDocument();

    const addCreatorBtns = screen.getAllByRole('button', { name: 'Thêm kênh' });
    addCreatorBtns[0].click();

    await waitFor(() => {
      const postUrls = fetchSpy.mock.calls
        .filter(([, init]) => init?.method === 'POST')
        .map(([input]) => (typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)));
      expect(postUrls.some((u) => u.includes('/api/sources/topics'))).toBe(true);
      expect(screen.getByRole('button', { name: 'Đã thêm kênh' })).toHaveTextContent('✓');
      expect(screen.getByRole('button', { name: 'Đã thêm tất cả kênh' })).toHaveTextContent('✓');
    });

    // Clicking Analyze starts a profile analysis job directly on the discovered creators
    fireEvent.click(screen.getByRole('button', { name: 'Phân tích các kênh' }));
    await waitFor(() => {
      const postCalls = fetchSpy.mock.calls.filter(([, init]) => init?.method === 'POST');
      expect(
        postCalls.some(([input]) =>
          (typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)).includes(
            'job_kind=profile',
          ),
        ),
      ).toBe(true);
    });
  });

  test('toggles platform filter buttons in keyword search results', async () => {
    const multiPlatformKeywordJob = {
      id: 'job_kw_filter',
      job_kind: 'keyword',
      status: 'completed',
      filename: 'gyno conditions',
      created_at: '2026-11-16T10:00:00Z',
      current_sheet: null,
      sheets: [
        {
          name: 'gyno conditions',
          slug: 'gyno-conditions',
          status: 'completed',
          targets: 2,
          reels: 2,
          pool_distribution: {},
          queries: [{ kind: 'original', text: 'gyno conditions' }],
          creators: [
            {
              name: 'Dr YT',
              handle: 'dryt',
              url: 'https://www.youtube.com/@dryt',
              platform: 'youtube',
              followers: 120000,
              video_count: 1,
              top_views: 50000,
              relevance: 'direct',
              why_relevant: 'Covers gynecomastia directly.',
            },
            {
              name: 'Off Topic Creator',
              handle: 'offtopic',
              url: 'https://www.youtube.com/@offtopic',
              platform: 'youtube',
              followers: 50000,
              video_count: 1,
              top_views: 10000,
              relevance: 'off_topic',
              why_relevant: 'Unrelated music channel.',
            },
            {
              name: 'TT Doc',
              handle: 'ttdoc',
              url: 'https://www.tiktok.com/@ttdoc',
              platform: 'tiktok',
              followers: 80000,
              video_count: 1,
              top_views: 90000,
            },
          ],
          error: null,
          notice: null,
          topics: [
            {
              title: 'YT Gyno Video',
              hook: '',
              angle: '',
              why_viral: '',
              outline: [],
              format: 'youtube',
              source_urls: ['https://www.youtube.com/watch?v=yt1'],
              reel_url: 'https://www.youtube.com/watch?v=yt1',
              platform: 'youtube',
              author_name: 'Dr YT',
              author_handle: 'dryt',
              generated_by: 'glasser',
              views: 50000,
            },
            {
              title: 'TT Gyno Video',
              hook: '',
              angle: '',
              why_viral: '',
              outline: [],
              format: 'tiktok',
              source_urls: ['https://www.tiktok.com/@ttdoc/video/123'],
              reel_url: 'https://www.tiktok.com/@ttdoc/video/123',
              platform: 'tiktok',
              author_name: 'TT Doc',
              author_handle: 'ttdoc',
              generated_by: 'glasser',
              views: 90000,
            },
          ],
        },
      ],
      logs: [],
    };

    setupMockFetch({ job_kw_filter: multiPlatformKeywordJob });

    render(
      <MemoryRouter initialEntries={['/?tab=analyzer&job_id=job_kw_filter']}>
        <Home />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Dr YT/i })).toBeInTheDocument();
    });

    const ytBtn = screen.getByRole('button', { name: 'youtube: 1' });
    const ttBtn = screen.getByRole('button', { name: 'tiktok: 1' });
    expect(ytBtn).toHaveAttribute('aria-pressed', 'false');
    expect(ttBtn).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('link', { name: /Dr YT/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /TT Doc/i })).toBeInTheDocument();

    // Filter to YouTube only
    ytBtn.click();
    await waitFor(() => {
      expect(ytBtn).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByRole('link', { name: /Dr YT/i })).toBeInTheDocument();
      expect(screen.queryByRole('link', { name: /TT Doc/i })).not.toBeInTheDocument();
    });

    // Toggle YouTube off -> restores all platforms
    ytBtn.click();
    await waitFor(() => {
      expect(ytBtn).toHaveAttribute('aria-pressed', 'false');
      expect(screen.getByRole('link', { name: /Dr YT/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /TT Doc/i })).toBeInTheDocument();
    });
  });

  test('merges history into flat #results-analysis with job kind filter', async () => {
    const onSelectJob = vi.fn();
    const baseProps = {
      keyword: '',
      onKeywordChange: vi.fn(),
      onSearchKeyword: vi.fn(),
      blocked: false,
      error: null,
      starting: false,
      jobId: null,
      job: null,
      visibleHistory: [
        {
          id: 'job_kw_1',
          job_kind: 'keyword' as const,
          status: 'completed' as const,
          filename: 'skincare',
          created_at: '2026-11-12T10:00:00Z',
          finished_at: null,
          current_sheet: null,
          total_sheets: 1,
          completed_sheets: 1,
          total_topics: 3,
        },
        {
          id: 'job_profile_1',
          job_kind: 'profile' as const,
          status: 'completed' as const,
          filename: 'all_topics.json',
          created_at: '2026-11-12T10:00:00Z',
          finished_at: null,
          current_sheet: null,
          total_sheets: 1,
          completed_sheets: 1,
          total_topics: 2,
        },
      ],
      onSelectJob,
      onDeleteJob: vi.fn(),
      tourDemoId: '',
      copiedKey: null,
      onCopyTopic: vi.fn(),
      onAddCreator: vi.fn(),
      onGoToLibrary: vi.fn(),
    };

    const { rerender } = render(<AnalyzerTab {...baseProps} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Lịch sử phân tích' }));
    expect(screen.queryByRole('heading', { name: 'Khám phá brand' })).not.toBeInTheDocument();
    expect(document.querySelector('#results-analysis > .panel-head')).not.toBeInTheDocument();
    expect(screen.getAllByText('Xem kết quả')).toHaveLength(2);

    // Filter by job kind
    fireEvent.click(screen.getByRole('button', { name: 'brand (1)' }));
    await waitFor(() => {
      expect(screen.getByText('skincare')).toBeInTheDocument();
      expect(screen.queryByText('all_topics.json')).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Tất cả (2)' }));
    await waitFor(() => {
      expect(screen.getAllByText('Xem kết quả')).toHaveLength(2);
    });

    // JobResult view renders flat inside #results-analysis without outer collapse button
    rerender(<AnalyzerTab {...baseProps} jobId="job_profile_1" job={profileJobFixture as never} />);
    expect(document.querySelector('#results-analysis .panel-collapse-btn')).not.toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Lịch sử chạy/i }));
    expect(onSelectJob).toHaveBeenCalledWith(null);
  });

  test('renders BrandPanel with Nhân hiệu question and saves to /api/user/profile', async () => {
    render(<BrandPanel />);
    const input = screen.getByLabelText(/Nhân hiệu:/i) as HTMLInputElement;
    expect(screen.getByText(/Khi nhắc tới bạn, mọi người sẽ nhớ tới gì\?/i)).toBeInTheDocument();

    input.value = 'Chuyên gia nấu ăn 15 phút';
    screen.getByRole('button', { name: 'Cập nhật Brand' }).click();
    await waitFor(() => {
      expect(localStorage.getItem('aibrand_brand_profile')).toBeTruthy();
      expect(screen.getByRole('button', { name: 'Cập nhật Brand' })).toBeInTheDocument();
      expect(document.querySelector('ion-toast')).toHaveAttribute('message', 'Đã cập nhật Brand');
    });
  });
});
