import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import Home from '../pages/Home';

import { LocaleProvider } from './index';

describe('Locale switcher in Profile panel', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('aibrand-tour-done-uid_locale_test', '1');
    (globalThis as any).__E2E_TEST_USER__ = {
      uid: 'uid_locale_test',
      email: 'locale@example.com',
      displayName: 'Locale Tester',
      providerData: [],
      getIdToken: async () => 'tok',
    };
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true, topics: [], jobs: [], reels: [], media: [], balance: 0 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
  });

  afterEach(() => {
    delete (globalThis as any).__E2E_TEST_USER__;
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test('renders VI/EN toggle inside section.panel.profile > div and switches UI text', async () => {
    const { container } = render(
      <LocaleProvider>
        <MemoryRouter initialEntries={['/?tab=profile']}>
          <Home />
        </MemoryRouter>
      </LocaleProvider>,
    );

    const toggle = await waitFor(() => {
      const btn = container.querySelector('section.panel.profile > div .lang-toggle-btn') as HTMLButtonElement | null;
      expect(btn).not.toBeNull();
      return btn!;
    });

    expect(toggle.textContent).toContain('VI');
    expect(screen.getByText('Đăng xuất')).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle.textContent).toContain('EN');
    expect(localStorage.getItem('aibrand-locale')).toBe('en');
    expect(screen.getByText('Sign out')).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(toggle.textContent).toContain('VI');
    expect(localStorage.getItem('aibrand-locale')).toBe('vi');
    expect(screen.getByText('Đăng xuất')).toBeInTheDocument();
  });
});
