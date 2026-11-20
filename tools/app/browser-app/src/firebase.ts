import { initializeApp } from 'firebase/app';
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  linkWithPopup,
  linkWithRedirect,
  getRedirectResult,
  updateProfile,
  signOut,
  FacebookAuthProvider,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  type User,
  type UserCredential,
} from 'firebase/auth';

import { getMessages } from './locales';

const configuredAuthDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '';
const useSameOriginAuthDomain =
  typeof window !== 'undefined' &&
  window.location.protocol === 'https:' &&
  Boolean(configuredAuthDomain) &&
  !window.location.hostname.endsWith('.firebaseapp.com') &&
  !window.location.hostname.endsWith('.web.app');

export const firebaseConfig = {
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: useSameOriginAuthDomain ? window.location.host : configuredAuthDomain,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || '',
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

export function onAuthStateChanged(authInstance: any, cb: (user: User | null) => void): () => void {
  const e2eUser = (globalThis as any).__E2E_TEST_USER__ as User | undefined;
  if (e2eUser) {
    Object.defineProperty(auth, 'currentUser', { get: () => e2eUser, configurable: true });
    queueMicrotask(() => cb(e2eUser));
    return () => {};
  }
  return firebaseOnAuthStateChanged(authInstance, cb);
}

export function isMobileBrowser(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia?.('(pointer: coarse)')?.matches === true || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  );
}

function createFacebookProvider(): FacebookAuthProvider {
  const provider = new FacebookAuthProvider();
  provider.addScope('public_profile');
  provider.addScope('email');
  return provider;
}

export async function signInWithFacebook(): Promise<UserCredential | null> {
  const provider = createFacebookProvider();
  if (isMobileBrowser()) {
    await signInWithRedirect(auth, provider);
    return null;
  }
  return signInWithPopup(auth, provider);
}

export async function linkWithFacebook(user: User): Promise<UserCredential | null> {
  const provider = createFacebookProvider();
  if (isMobileBrowser()) {
    await linkWithRedirect(user, provider);
    return null;
  }
  return linkWithPopup(user, provider);
}

export async function resolveAuthRedirect(): Promise<UserCredential | null> {
  if ((globalThis as any).__E2E_TEST_USER__) return null;
  return getRedirectResult(auth);
}

export function formatFacebookAuthError(err: any, fallback: string): string {
  const fbErrors = getMessages().fbErrors;
  return (err?.code && fbErrors[err.code]) || err?.message || fallback;
}

export {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  linkWithPopup,
  linkWithRedirect,
  getRedirectResult,
  updateProfile,
  signOut,
  FacebookAuthProvider,
};
export type { User, UserCredential };
