import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { resetBrandAssistantStore, setBrandAssistantUser } from './brandAssistantStore';
import { cacheBrandProfile } from './brandProfile';
import { AnalyzerTab } from './components/AnalyzerTab';
import { BrandAssistant } from './components/BrandAssistant';
import { LocaleProvider, useLocale } from './locales';

describe('BrandAssistant', () => {
  beforeEach(() => {
    localStorage.clear();
    resetBrandAssistantStore();
    localStorage.setItem('aibrand-locale', 'en');
  });

  afterEach(() => {
    resetBrandAssistantStore();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test('renders strictly 2 modes, saves brand v1 draft + keywords, and launches keyword search', async () => {
    const onSearchKeyword = vi.fn();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/brand-assistant/chat')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              mode: 'brand_setup',
              reply: 'Here is your first brand version.',
              brand_draft: {
                identity: 'Minimalist skincare educator',
                audience: 'Busy office workers',
              },
              keywords: ['minimalist skincare', '5-min routine'],
              ready: true,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      if (url.includes('/api/user/profile')) {
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true, profile: { brand: {} } }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={onSearchKeyword} blocked={false} />
      </LocaleProvider>,
    );

    expect(document.querySelector('form.brand-direct-search')).toBeNull();

    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(2);
    expect(tabs[0]).toHaveTextContent('Build Brand');
    expect(tabs[1]).toHaveTextContent('Explore Brand');

    const input = screen.getByPlaceholderText('Describe your niche, offer, or answer the question…');
    fireEvent.change(input, { target: { value: 'I teach 5-minute skincare for office workers' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Here is your first brand version.')).toBeInTheDocument();
      expect(screen.getByText('Minimalist skincare educator')).toBeInTheDocument();
    });

    const chatCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/brand-assistant/chat'));
    expect(chatCall).toBeDefined();
    expect(JSON.parse(String(chatCall![1]?.body)).mode).toBe('brand_setup');

    fireEvent.click(screen.getByRole('button', { name: 'Save to brand profile' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '✓ Saved to brand profile' })).toBeInTheDocument();
    });

    const profileCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/user/profile'));
    expect(profileCall).toBeDefined();
    const savedBody = JSON.parse(String(profileCall![1]?.body));
    expect(savedBody.brand.identity).toBe('Minimalist skincare educator');
    expect(savedBody.brand.keywords).toEqual(['minimalist skincare', '5-min routine']);

    fireEvent.click(screen.getByRole('button', { name: 'minimalist skincare ↗' }));
    expect(onSearchKeyword).toHaveBeenCalledWith('minimalist skincare');
  });

  test('switches to free keyword_explore mode without brand save controls', async () => {
    const onSearchKeyword = vi.fn();
    const onSearchKeywords = vi.fn();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          mode: 'keyword_explore',
          reply: 'Explore these off-brand queries freely:',
          keywords: ['street food saigon', 'night market vlog'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={onSearchKeyword} onSearchKeywords={onSearchKeywords} blocked={false} />
      </LocaleProvider>,
    );

    expect(document.querySelector('form.brand-direct-search')).toBeNull();

    fireEvent.click(screen.getByRole('tab', { name: 'Explore Brand' }));
    expect(document.querySelector('form.brand-direct-search')).toBeNull();

    const input = screen.getByPlaceholderText('Ask about any topic, niche, or trend…');
    fireEvent.change(input, { target: { value: 'night food trends' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Explore these off-brand queries freely:')).toBeInTheDocument();
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).mode).toBe('keyword_explore');
    expect(screen.queryByRole('button', { name: 'Save to brand profile' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'street food saigon ↗' }));
    expect(onSearchKeyword).toHaveBeenCalledWith('street food saigon');

    fireEvent.click(screen.getByRole('button', { name: 'Search with 2 keywords' }));
    expect(onSearchKeywords).toHaveBeenCalledWith(['street food saigon', 'night market vlog']);
  });

  test('updates welcome message dynamically when locale switches between VI and EN', () => {
    localStorage.setItem('aibrand-locale', 'vi');
    const ToggleWrapper: React.FC = () => {
      const { toggleLocale } = useLocale();
      return (
        <>
          <button type="button" onClick={toggleLocale}>
            Switch
          </button>
          <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
        </>
      );
    };

    render(
      <LocaleProvider>
        <ToggleWrapper />
      </LocaleProvider>,
    );

    const welcomeEl = () => document.querySelector('#brand-assistant > div.brand-chat-messages > div > p')?.textContent;
    expect(welcomeEl()).toContain('Chào bạn!');

    fireEvent.click(screen.getByRole('button', { name: 'Switch' }));
    expect(welcomeEl()).toContain('Hi! I will ask a few quick questions');
  });

  test('persists chat history and mode across unmount/remount (tab switches)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          mode: 'keyword_explore',
          reply: 'Saved reply across tabs',
          keywords: ['persisted kw'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    const { unmount } = render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Explore Brand' }));
    const input = screen.getByPlaceholderText('Ask about any topic, niche, or trend…');
    fireEvent.change(input, { target: { value: 'hello across tabs' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Saved reply across tabs')).toBeInTheDocument();
    });

    unmount();

    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    expect(screen.getByRole('tab', { name: 'Explore Brand' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('hello across tabs')).toBeInTheDocument();
    expect(screen.getByText('Saved reply across tabs')).toBeInTheDocument();
  });

  test('keeps processing bubble and delivers in-flight reply after unmount/remount', async () => {
    let resolveFetch!: (res: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const { unmount } = render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    const input = screen.getByPlaceholderText('Describe your niche, offer, or answer the question…');
    fireEvent.change(input, { target: { value: 'in-flight question' } });
    fireEvent.submit(input.closest('form')!);

    expect(screen.getByText('Asking assistant...')).toBeInTheDocument();

    // User switches to Profile tab (unmounts BrandAssistant) while request is in flight
    unmount();

    // User switches back before response arrives: processing bubble must still be visible
    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );
    expect(screen.getByText('in-flight question')).toBeInTheDocument();
    expect(screen.getByText('Asking assistant...')).toBeInTheDocument();

    // Backend responds while remounted
    resolveFetch(
      new Response(
        JSON.stringify({
          ok: true,
          mode: 'brand_setup',
          reply: 'Delayed reply arrived!',
          brand_draft: { identity: 'Test Brand' },
          keywords: ['test kw'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    await waitFor(() => {
      expect(screen.getByText('Delayed reply arrived!')).toBeInTheDocument();
      expect(screen.queryByText('Asking assistant...')).not.toBeInTheDocument();
    });
  });

  test('expands and highlights #results-brand when clicking search CTA in AnalyzerTab', async () => {
    localStorage.setItem('aibrand-results-brand-collapsed', '1');
    const onSearchKeywords = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          mode: 'keyword_explore',
          reply: 'Ready to search:',
          keywords: ['mc song ngu', 'mc su kien'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    const { container } = render(
      <LocaleProvider>
        <AnalyzerTab
          keyword=""
          onKeywordChange={vi.fn()}
          onSearchKeyword={vi.fn()}
          onSearchKeywords={onSearchKeywords}
          blocked={false}
          error={null}
          starting={false}
          jobId={null}
          job={null}
          visibleHistory={[]}
          loadingHistory={false}
          onFetchHistory={vi.fn()}
          onSelectJob={vi.fn()}
          onDeleteJob={vi.fn()}
          tourDemoId=""
          copiedKey={null}
          onCopyTopic={vi.fn()}
          onAddCreator={vi.fn()}
          onSaveVideo={vi.fn()}
          onGoToLibrary={vi.fn()}
        />
      </LocaleProvider>,
    );

    const assistantSection = container.querySelector('#brand-assistant')!;
    expect(assistantSection).toHaveClass('brand-assistant-full');
    expect(container.querySelector('#results')).toBeNull();
    expect(screen.getByRole('tab', { name: 'Analysis History' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Explore Brand' }));
    const input = screen.getByPlaceholderText('Ask about any topic, niche, or trend…');
    fireEvent.change(input, { target: { value: 'mc' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Search with 2 keywords' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Search with 2 keywords' }));

    expect(onSearchKeywords).toHaveBeenCalledWith(['mc song ngu', 'mc su kien']);
    const resultsBrand = container.querySelector('#results-brand')!;
    expect(resultsBrand.querySelector('[aria-expanded]')).toHaveAttribute('aria-expanded', 'true');
    expect(resultsBrand).toHaveClass('results-highlight');
    expect(assistantSection).not.toHaveClass('brand-assistant-full');
  });

  test('restores per-user chat history after logout and login without leaking to other accounts', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/api/brand-assistant/chat')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ok: true,
              mode: 'brand_setup',
              reply: 'Reply for account A',
              brand_draft: { identity: 'Brand A' },
              keywords: ['kw a'],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ ok: true, profile: {} }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    });

    setBrandAssistantUser('uid-a');
    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    const input = screen.getByPlaceholderText('Describe your niche, offer, or answer the question…');
    fireEvent.change(input, { target: { value: 'Account A message' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Reply for account A')).toBeInTheDocument();
    });

    // Sign out: clears UI
    setBrandAssistantUser(null);
    await waitFor(() => {
      expect(screen.queryByText('Account A message')).not.toBeInTheDocument();
    });

    // Sign in as another account: isolated
    setBrandAssistantUser('uid-b');
    expect(screen.queryByText('Account A message')).not.toBeInTheDocument();

    // Sign back in as account A: history is restored
    setBrandAssistantUser('uid-a');
    await waitFor(() => {
      expect(screen.getByText('Account A message')).toBeInTheDocument();
      expect(screen.getByText('Reply for account A')).toBeInTheDocument();
    });
  });

  test('recognizes existing #brand-profile and prompts for revision in welcome message', async () => {
    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    const welcomeEl = () => document.querySelector('#brand-assistant > div.brand-chat-messages > div > p')?.textContent;
    expect(welcomeEl()).toContain('Hi! I will ask a few quick questions');

    cacheBrandProfile({
      identity: 'MC song ngữ',
      audience: 'Event organizers',
      differentiator: 'Bilingual stage energy',
      tone: 'Warm, sharp',
      keywords: ['mc song ngu', 'mc su kien'],
    });

    await waitFor(() => {
      const text = welcomeEl() || '';
      expect(text).toContain('I see your current brand profile:');
      expect(text).toContain('Brand Identity: MC song ngữ');
      expect(text).toContain('Target Audience: Event organizers');
      expect(text).toContain('Differentiator: Bilingual stage energy');
      expect(text).toContain('Style & Tone: Warm, sharp');
      expect(text).toContain('On-brand Keywords: mc song ngu, mc su kien');
    });
  });

  test('renders inline markdown bold/italic/code in assistant replies', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          mode: 'brand_setup',
          reply: 'Mình đã rút gọn phần **Nhân hiệu** xuống còn **“Trợ lý AI”** và *gọn* hơn.',
          keywords: ['ai brand'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    render(
      <LocaleProvider>
        <BrandAssistant onSearchKeyword={vi.fn()} blocked={false} />
      </LocaleProvider>,
    );

    const input = screen.getByPlaceholderText('Describe your niche, offer, or answer the question…');
    fireEvent.change(input, { target: { value: 'shorten it' } });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => {
      const strong = screen.getByText('Nhân hiệu');
      expect(strong.tagName).toBe('STRONG');
      expect(screen.getByText('“Trợ lý AI”').tagName).toBe('STRONG');
      expect(screen.getByText('gọn').tagName).toBe('EM');
      expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
    });
  });
});
