import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import * as firebaseMod from '../firebase';
import Home from '../pages/Home';

import { LocaleProvider } from './index';

describe('Locale switcher in topbar', () => {
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

  test('renders VI/EN toggle in .topbar and switches UI text when signed in', async () => {
    const { container } = render(
      <LocaleProvider>
        <MemoryRouter initialEntries={['/?tab=profile']}>
          <Home />
        </MemoryRouter>
      </LocaleProvider>,
    );

    const toggle = await waitFor(() => {
      const btn = container.querySelector('.topbar .lang-toggle-btn') as HTMLButtonElement | null;
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

    const contributorsHeading = screen.getByRole('heading', { name: 'Đóng góp' });
    const details = contributorsHeading.closest('details') as HTMLDetailsElement;
    expect(details).not.toBeNull();
    expect(details.open).toBe(false);
    expect(screen.getByText('Christine Erispe')).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByRole('heading', { name: 'Contributors' })).toBeInTheDocument();

    // Collapse #brand-profile and media section, then verify persistence across tab switch & remount
    const brandHead = container.querySelector('#brand-profile .collapsible-head') as HTMLElement;
    const mediaHead = container.querySelectorAll('.collapsible-head')[1] as HTMLElement;
    expect(brandHead.getAttribute('aria-expanded')).toBe('true');
    expect(mediaHead.getAttribute('aria-expanded')).toBe('true');

    fireEvent.click(brandHead);
    fireEvent.click(mediaHead);
    expect(localStorage.getItem('aibrand-profile-brand-collapsed')).toBe('1');
    expect(localStorage.getItem('aibrand-profile-media-collapsed')).toBe('1');

    // Switch to another tab and back
    fireEvent.click(screen.getByRole('tab', { name: /Library|Thư viện/i }));
    fireEvent.click(screen.getByRole('tab', { name: /Profile|Hồ sơ/i }));
    expect(container.querySelector('#brand-profile .collapsible-head')?.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelectorAll('.collapsible-head')[1]?.getAttribute('aria-expanded')).toBe('false');
  });

  test('renders VI/EN toggle in .topbar on the login page when signed out', async () => {
    delete (globalThis as any).__E2E_TEST_USER__;
    vi.spyOn(firebaseMod, 'onAuthStateChanged').mockImplementation((_auth, cb) => {
      queueMicrotask(() => cb(null));
      return () => {};
    });

    const { container } = render(
      <LocaleProvider>
        <MemoryRouter initialEntries={['/']}>
          <Home />
        </MemoryRouter>
      </LocaleProvider>,
    );

    const toggle = await waitFor(() => {
      const btn = container.querySelector('.topbar .lang-toggle-btn') as HTMLButtonElement | null;
      expect(btn).not.toBeNull();
      return btn!;
    });

    expect(toggle.textContent).toContain('VI');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Đăng nhập / Đăng ký' })).toBeInTheDocument();
    });

    fireEvent.click(toggle);

    expect(toggle.textContent).toContain('EN');
    expect(localStorage.getItem('aibrand-locale')).toBe('en');
    expect(screen.getByRole('button', { name: 'Sign in / Sign up' })).toBeInTheDocument();
  });
});
