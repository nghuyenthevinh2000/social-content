import { initializeApp } from 'firebase/app';
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  updateProfile,
  signOut,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  type User,
} from 'firebase/auth';

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

export {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  updateProfile,
  signOut,
};
export type { User };
