import type * as FirebaseAuth from 'firebase/auth';
import { beforeEach, describe, expect, test, vi } from 'vitest';

import { formatFacebookAuthError, isMobileBrowser, linkWithFacebook, signInWithFacebook } from './firebase';

const authMocks = vi.hoisted(() => ({
  signInWithPopup: vi.fn(),
  signInWithRedirect: vi.fn(),
  linkWithPopup: vi.fn(),
  linkWithRedirect: vi.fn(),
  getRedirectResult: vi.fn(),
}));

vi.mock('firebase/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof FirebaseAuth>();
  return {
    ...actual,
    getAuth: vi.fn(() => ({ currentUser: null })),
    signInWithPopup: authMocks.signInWithPopup,
    signInWithRedirect: authMocks.signInWithRedirect,
    linkWithPopup: authMocks.linkWithPopup,
    linkWithRedirect: authMocks.linkWithRedirect,
    getRedirectResult: authMocks.getRedirectResult,
  };
});

function setMobileEnv(mobile: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({ matches: mobile })),
  });
  Object.defineProperty(navigator, 'userAgent', {
    configurable: true,
    value: mobile
      ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'
      : 'Mozilla/5.0 (Macintosh; Intel Mac OS X)',
  });
}

describe('firebase Facebook auth routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('uses popup on desktop and redirect on mobile', async () => {
    setMobileEnv(false);
    expect(isMobileBrowser()).toBe(false);
    authMocks.signInWithPopup.mockResolvedValueOnce({ user: { uid: 'u1' } });
    authMocks.linkWithPopup.mockResolvedValueOnce({ user: { uid: 'u1' } });

    await signInWithFacebook();
    await linkWithFacebook({ uid: 'u1' } as any);
    expect(authMocks.signInWithPopup).toHaveBeenCalledTimes(1);
    expect(authMocks.linkWithPopup).toHaveBeenCalledTimes(1);
    expect(authMocks.signInWithRedirect).not.toHaveBeenCalled();
    expect(authMocks.linkWithRedirect).not.toHaveBeenCalled();

    setMobileEnv(true);
    expect(isMobileBrowser()).toBe(true);
    expect(await signInWithFacebook()).toBeNull();
    expect(await linkWithFacebook({ uid: 'u1' } as any)).toBeNull();
    expect(authMocks.signInWithRedirect).toHaveBeenCalledTimes(1);
    expect(authMocks.linkWithRedirect).toHaveBeenCalledTimes(1);
  });

  test('maps known Facebook error codes and falls back cleanly', () => {
    expect(formatFacebookAuthError({ code: 'auth/credential-already-in-use' }, 'fallback')).toContain(
      'đã được liên kết',
    );
    expect(formatFacebookAuthError({ message: 'raw' }, 'fallback')).toBe('raw');
    expect(formatFacebookAuthError({}, 'fallback')).toBe('fallback');
  });
});
