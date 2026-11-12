import React, { useState } from 'react';

import {
  auth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  FacebookAuthProvider,
} from '../firebase';
import './AuthModal.css';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleFacebookLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const provider = new FacebookAuthProvider();
      provider.addScope('public_profile');
      provider.addScope('email');
      await signInWithPopup(auth, provider);
      onClose();
    } catch (err: any) {
      let msg = err.message || 'Đã xảy ra lỗi khi đăng nhập bằng Facebook.';
      if (err.code === 'auth/popup-closed-by-user') msg = 'Bạn đã đóng cửa sổ đăng nhập.';
      if (err.code === 'auth/cancelled-popup-request') msg = 'Yêu cầu đăng nhập đã bị hủy.';
      if (err.code === 'auth/account-exists-with-different-credential')
        msg = 'Email của tài khoản Facebook này đã tồn tại với một phương thức đăng nhập khác.';
      setError(msg);
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
      let msg = err.message || 'Đã xảy ra lỗi khi xác thực.';
      if (err.code === 'auth/invalid-email') msg = 'Địa chỉ email không hợp lệ.';
      if (
        err.code === 'auth/user-not-found' ||
        err.code === 'auth/wrong-password' ||
        err.code === 'auth/invalid-credential'
      )
        msg = 'Email hoặc mật khẩu không chính xác.';
      if (err.code === 'auth/email-already-in-use') msg = 'Email này đã được đăng ký tài khoản.';
      if (err.code === 'auth/weak-password') msg = 'Mật khẩu phải có ít nhất 6 ký tự.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-backdrop" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-header">
          <h3>{isSignUp ? 'Đăng ký tài khoản' : 'Đăng nhập tài khoản'}</h3>
          <button type="button" className="auth-close-btn" onClick={onClose} aria-label="Đóng">
            ✕
          </button>
        </div>

        {error && <div className="alert error auth-alert">{error}</div>}

        <button
          type="button"
          className="auth-facebook-btn"
          onClick={handleFacebookLogin}
          disabled={loading}
        >
          <svg className="fb-svg" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
          </svg>
          Tiếp tục với Facebook
        </button>

        <div className="auth-divider">
          <span>hoặc dùng email</span>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <label className="auth-label">
            Email
            <input
              type="email"
              className="text-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ten@example.com"
              required
              autoFocus
            />
          </label>

          <label className="auth-label">
            Mật khẩu
            <input
              type="password"
              className="text-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Tối thiểu 6 ký tự"
              required
            />
          </label>

          <button type="submit" className="primary auth-submit-btn" disabled={loading}>
            {loading ? 'Đang xử lý…' : isSignUp ? 'Đăng ký' : 'Đăng nhập'}
          </button>
        </form>

        <div className="auth-footer">
          {isSignUp ? (
            <p>
              Đã có tài khoản?{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsSignUp(false);
                  setError(null);
                }}
              >
                Đăng nhập ngay
              </button>
            </p>
          ) : (
            <p>
              Chưa có tài khoản?{' '}
              <button
                type="button"
                className="link-btn"
                onClick={() => {
                  setIsSignUp(true);
                  setError(null);
                }}
              >
                Đăng ký tài khoản mới
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
