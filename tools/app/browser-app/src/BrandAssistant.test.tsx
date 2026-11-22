import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { BrandAssistant } from './components/BrandAssistant';
import { LocaleProvider } from './locales';

describe('BrandAssistant', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('aibrand-locale', 'en');
  });

  afterEach(() => {
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
    expect(tabs[1]).toHaveTextContent('Explore Brand Keyword');

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

    fireEvent.click(screen.getByRole('tab', { name: 'Explore Brand Keyword' }));
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
});
