import { useEffect, useRef, useState } from 'react';
import { apiFetch, apiJson } from '../api';
import './MediaPanel.css';

export type MediaItem = {
  id: string;
  user_id: string;
  kind: 'profile' | 'context';
  path: string;
  mime: string;
  bytes: number;
  created_at: string;
};

export function mediaUrl(item: MediaItem): string {
  return `/api/media/${encodeURIComponent(item.id)}?uid=${encodeURIComponent(item.user_id)}`;
}

type MediaPanelProps = {
  onMediaUpdated?: () => void;
};

export function MediaPanel({ onMediaUpdated }: MediaPanelProps) {
  const [profile, setProfile] = useState<MediaItem | null>(null);
  const [contextList, setContextList] = useState<MediaItem[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const profileInputRef = useRef<HTMLInputElement>(null);
  const contextInputRef = useRef<HTMLInputElement>(null);

  const fetchMedia = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiJson<{ ok: boolean; media: MediaItem[] }>('/api/media');
      if (res.ok && res.media) {
        const prof = res.media.find((m) => m.kind === 'profile') || null;
        const ctx = res.media.filter((m) => m.kind === 'context');
        setProfile(prof);
        setContextList(ctx);
      }
    } catch (err: any) {
      setError(err?.message || 'Không thể tải ảnh');
    } finally {
      setLoading(false);
    }
  };

  const fetchCredits = async () => {
    try {
      const res = await apiJson<{ ok: boolean; balance: number }>('/api/credits');
      if (res.ok && typeof res.balance === 'number') {
        setBalance(res.balance);
      }
    } catch {
      // ignore if credits endpoint not mocked in unit test
    }
  };

  useEffect(() => {
    fetchMedia();
    fetchCredits();
  }, []);

  const handleUpload = async (kind: 'profile' | 'context', file: File) => {
    try {
      setLoading(true);
      setError(null);
      const ext = file.name.toLowerCase();
      const mime =
        file.type ||
        (ext.endsWith('.png') ? 'image/png' : ext.endsWith('.webp') ? 'image/webp' : 'image/jpeg');
      const res = await apiFetch(`/api/media?kind=${kind}`, {
        method: 'POST',
        headers: {
          'Content-Type': mime,
        },
        body: file,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Lỗi khi tải ảnh lên');
      }
      await fetchMedia();
      onMediaUpdated?.();
    } catch (err: any) {
      setError(err?.message || 'Tải ảnh thất bại');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      await apiJson('/api/media/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      await fetchMedia();
      onMediaUpdated?.();
    } catch (err: any) {
      setError(err?.message || 'Xoá ảnh thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="media-panel">
      {error && <div className="notice error">{error}</div>}

      {balance !== null && (
        <div className="profile-card" style={{ justifyContent: 'space-between' }}>
          <div>
            <strong>Số dư Video AI</strong>
          </div>
          <strong style={{ color: 'var(--accent)', fontSize: 15 }}>
            ${(balance / 1000000).toFixed(2)}
          </strong>
        </div>
      )}

      <div className="media-section">
        <div className="media-section-title">
          <span>Ảnh chân dung mẫu (Profile)</span>
          <small className="muted">{profile ? '1/1 ảnh' : 'Chưa có ảnh'}</small>
        </div>

        <div className="profile-card">
          {profile ? (
            <img src={mediaUrl(profile)} alt="Profile" className="profile-preview" />
          ) : (
            <div className="profile-placeholder">👤</div>
          )}

          <div className="profile-info">
            <strong>{profile ? 'Ảnh mẫu chính' : 'Chưa có ảnh chân dung'}</strong>
            <small>{profile ? `${(profile.bytes / 1024).toFixed(0)} KB` : 'Dùng để khớp khuôn mặt trong video'}</small>

            <div className="media-btn-row">
              <input
                ref={profileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleUpload('profile', file);
                  e.target.value = '';
                }}
              />
              <button
                type="button"
                className="media-action-btn"
                onClick={() => profileInputRef.current?.click()}
                disabled={loading}
              >
                {profile ? 'Thay ảnh khác' : 'Tải ảnh mẫu lên'}
              </button>

              {profile && (
                <button
                  type="button"
                  className="media-action-btn danger"
                  onClick={() => handleDelete(profile.id)}
                  disabled={loading}
                >
                  Xoá
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="media-section">
        <div className="media-section-title">
          <span>Ảnh bối cảnh / Sản phẩm (Context)</span>
          <small className="muted">{contextList.length} ảnh</small>
        </div>

        <div className="context-grid">
          {contextList.map((item) => (
            <div key={item.id} className="context-card">
              <img src={mediaUrl(item)} alt="Context" />
              <button
                type="button"
                className="delete-chip"
                title="Xoá ảnh này"
                onClick={() => handleDelete(item.id)}
                disabled={loading}
              >
                ✕
              </button>
            </div>
          ))}

          <input
            ref={contextInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload('context', file);
              e.target.value = '';
            }}
          />
          <div
            className="context-upload-card"
            onClick={() => contextInputRef.current?.click()}
          >
            <span>+</span>
            <div>Thêm ảnh</div>
          </div>
        </div>
      </div>
    </div>
  );
}
