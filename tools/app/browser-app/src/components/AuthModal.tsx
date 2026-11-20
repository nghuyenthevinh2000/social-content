import React, { useState } from 'react';

import {
  auth,
  createUserWithEmailAndPassword,
  formatFacebookAuthError,
  signInWithEmailAndPassword,
  signInWithFacebook,
} from '../firebase';
import { useLocale } from '../locales';
import './AuthModal.css';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialError?: string | null;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, initialError }) => {
  const { t } = useLocale();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const displayError = error ?? initialError ?? null;

  const handleFacebookLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await signInWithFacebook();
      if (res) onClose();
    } catch (err: any) {
      setError(formatFacebookAuthError(err, t.authModal.errors.fbFallback));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isSignUp) {
        await createUserWithEmailAndPassword(auth, email.trim(), password);
      } else {
        await signInWithEmailAndPassword(auth, email.trim(), password);
      }
      onClose();
    } catch (err: any) {
      let msg = err.message || t.authModal.errors.generic;
      if (err.code === 'auth/invalid-email') msg = t.authModal.errors.invalidEmail;
      if (
        err.code === 'auth/user-not-found' ||
        err.code === 'auth/wrong-password' ||
        err.code === 'auth/invalid-credential'
      )
        msg = t.authModal.errors.invalidCredential;
      if (err.code === 'auth/email-already-in-use') msg = t.authModal.errors.emailInUse;
      if (err.code === 'auth/weak-password') msg = t.authModal.errors.weakPassword;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-backdrop" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-header">
          <h3>{isSignUp ? t.authModal.signUpTitle : t.authModal.signInTitle}</h3>
          <button type="button" className="auth-close-btn" onClick={onClose} aria-label={t.common.close}>
            ✕
          </button>
        </div>

        {displayError && <div className="alert error auth-alert">{displayError}</div>}

        <button type="button" className="auth-facebook-btn" onClick={handleFacebookLogin} disabled={loading}>
          <svg className="fb-svg" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
          </svg>
          {t.authModal.continueFacebook}
        </button>

        <div className="auth-divider">
          <span>{t.authModal.orUseEmail}</span>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <label className="auth-label">
            {t.authModal.emailLabel}
            <input
              type="email"
              className="text-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t.authModal.emailPlaceholder}
              required
              autoFocus
            />
          </label>

          <label className="auth-label">
            {t.authModal.passwordLabel}
            <input
              type="password"
              className="text-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t.authModal.passwordPlaceholder}
              required
            />
          </label>

          <button type="submit" className="primary auth-submit-btn" disabled={loading}>
            {loading ? t.common.processing : isSignUp ? t.authModal.signUpBtn : t.authModal.signInBtn}
          </button>
        </form>

        <div className="auth-footer">
          {isSignUp ? (
            <p>
              {t.authModal.hasAccount}{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsSignUp(false);
                  setError(null);
                }}
              >
                {t.authModal.signInNow}
              </button>
            </p>
          ) : (
            <p>
              {t.authModal.noAccount}{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsSignUp(true);
                  setError(null);
                }}
              >
                {t.authModal.signUpNew}
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
