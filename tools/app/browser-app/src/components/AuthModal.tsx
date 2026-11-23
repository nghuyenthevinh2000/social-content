import React, { useState } from 'react';

import { auth, createUserWithEmailAndPassword, signInWithEmailAndPassword } from '../firebase';
import { useLocale } from '../locales';
import './AuthModal.css';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { t } = useLocale();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

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

        {error && <div className="alert error auth-alert">{error}</div>}

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
