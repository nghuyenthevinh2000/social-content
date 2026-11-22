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

  test('switches tour language to English from inside the tour dialog', async () => {
    localStorage.removeItem('aibrand-tour-done-uid_locale_test');

    const { container } = render(
      <LocaleProvider>
        <MemoryRouter initialEntries={['/']}>
          <Home />
        </MemoryRouter>
      </LocaleProvider>,
    );

    const tourToggle = await waitFor(() => {
      const btn = container.querySelector('.tour .lang-toggle-btn') as HTMLButtonElement | null;
      expect(btn).not.toBeNull();
      return btn!;
    });

    expect(tourToggle.textContent).toContain('VI');
    expect(screen.getByRole('button', { name: 'Bỏ qua' })).toBeInTheDocument();

    fireEvent.click(tourToggle);

    expect(tourToggle.textContent).toContain('EN');
    expect(localStorage.getItem('aibrand-locale')).toBe('en');
    expect(screen.getByRole('button', { name: 'Skip' })).toBeInTheDocument();
    expect(screen.getByText('Import Excel/Google Sheets, manage topics, Facebook channels, and saved Reels.')).toBeInTheDocument();
  });
});
