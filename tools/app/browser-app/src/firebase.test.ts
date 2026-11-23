import type * as FirebaseAuth from 'firebase/auth';
import { beforeEach, describe, expect, test, vi } from 'vitest';

import { onAuthStateChanged } from './firebase';

const authMocks = vi.hoisted(() => ({
  onAuthStateChanged: vi.fn(() => () => {}),
}));

vi.mock('firebase/auth', async (importOriginal) => {
  const actual = await importOriginal<typeof FirebaseAuth>();
  return {
    ...actual,
    getAuth: vi.fn(() => ({ currentUser: null })),
    onAuthStateChanged: authMocks.onAuthStateChanged,
  };
});

describe('firebase auth helper', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (globalThis as any).__E2E_TEST_USER__;
  });

  test('delegates to firebase onAuthStateChanged when no e2e user is set', () => {
    const cb = vi.fn();
    onAuthStateChanged({} as any, cb);
    expect(authMocks.onAuthStateChanged).toHaveBeenCalledTimes(1);
  });
});
