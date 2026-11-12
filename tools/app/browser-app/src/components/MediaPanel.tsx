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

const ACTOR_PROFILE_KEY = 'aibrand_actor_profile';

function loadCachedProfile(): { gender?: 'male' | 'female'; age?: number; name?: string; voice_tone?: string } | null {
  try {
    const raw = localStorage.getItem(ACTOR_PROFILE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

export function MediaPanel({ onMediaUpdated }: MediaPanelProps) {
  const cached = loadCachedProfile();
  const [profile, setProfile] = useState<MediaItem | null>(null);
  const [contextList, setContextList] = useState<MediaItem[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actorGender, setActorGender] = useState<'male' | 'female'>(
    cached?.gender === 'female' ? 'female' : 'male'
  );
  const [actorAge, setActorAge] = useState<number>(
    typeof cached?.age === 'number' && cached.age >= 15 && cached.age <= 80 ? cached.age : 28
  );
  const [actorName, setActorName] = useState<string>(cached?.name || '');
  const [actorTone, setActorTone] = useState<string>(
    cached?.voice_tone && ['Bắc', 'Trung', 'Nam'].includes(cached.voice_tone) ? cached.voice_tone : 'Bắc'
  );
  const [savingProfile, setSavingProfile] = useState(false);

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

  const fetchActorProfile = async () => {
    try {
      const res = await apiJson<{
        ok: boolean;
        profile: {
          gender?: 'male' | 'female';
          age?: number;
          name?: string;
          voice_tone?: string;
        };
      }>('/api/user/profile');
      if (res.ok && res.profile) {
        const p = res.profile;
        if (p.gender === 'male' || p.gender === 'female') setActorGender(p.gender);
        if (typeof p.age === 'number' && p.age >= 15 && p.age <= 80) setActorAge(p.age);
        if (p.name !== undefined) setActorName(p.name);
        const tone = p.voice_tone && ['Bắc', 'Trung', 'Nam'].includes(p.voice_tone) ? p.voice_tone : 'Bắc';
        setActorTone(tone);
        try {
          localStorage.setItem(
            ACTOR_PROFILE_KEY,
            JSON.stringify({
              gender: p.gender || 'male',
              age: typeof p.age === 'number' ? p.age : 28,
              name: p.name || '',
              voice_tone: tone,
            })
          );
        } catch {}
      }
    } catch {
      // ignore network errors, preserve cached state
    }
  };

  const handleUpdateActorProfile = async (
    updates: Partial<{ gender: 'male' | 'female'; age: number; name: string; voice_tone: string }>
  ) => {
    const nextGender = updates.gender ?? actorGender;
    const nextAge = updates.age ?? actorAge;
    const nextName = updates.name !== undefined ? updates.name : actorName;
    const nextTone = updates.voice_tone ?? actorTone;

    if (updates.gender !== undefined) setActorGender(nextGender);
    if (updates.age !== undefined) setActorAge(nextAge);
    if (updates.name !== undefined) setActorName(nextName);
    if (updates.voice_tone !== undefined) setActorTone(nextTone);

    try {
      localStorage.setItem(
        ACTOR_PROFILE_KEY,
        JSON.stringify({
          gender: nextGender,
          age: nextAge,
          name: nextName,
          voice_tone: nextTone,
        })
      );
    } catch {}

    try {
      setSavingProfile(true);
      await apiJson('/api/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gender: nextGender,
          age: nextAge,
          name: nextName,
          voice_tone: nextTone,
        }),
      });
    } catch (err: any) {
      setError(err?.message || 'Không thể lưu thông tin diễn viên');
    } finally {
      setSavingProfile(false);
    }
  };

  useEffect(() => {
    fetchMedia();
    fetchCredits();
    fetchActorProfile();
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

        <div className="actor-profile-box">
          <div className="actor-profile-head">
            <span className="actor-profile-title">
              <span>🎭</span>
              <span>Thông tin diễn viên & Giọng đọc AI</span>
            </span>
            <small className="muted">{savingProfile ? 'Đang lưu…' : 'Tự động đồng bộ với AI'}</small>
          </div>

          <p className="actor-field-hint" style={{ margin: 0 }}>
            Cung cấp thông tin nhân vật mẫu để AI tự động chọn <strong>giọng đọc chuẩn xác</strong> (nam/nữ, độ tuổi, âm điệu) và phong thái phù hợp với ảnh chân dung, không bị nhầm lẫn giọng.
          </p>

          {/* 1. Giới tính */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>Giới tính diễn viên:</span>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="button"
                className={`actor-chip ${actorGender === 'male' ? 'selected' : ''}`}
                onClick={() => handleUpdateActorProfile({ gender: 'male' })}
                style={{ flex: 1, padding: '8px 12px', fontSize: 13, fontWeight: 600 }}
              >
                👨 Nam (Male Voice)
              </button>
              <button
                type="button"
                className={`actor-chip ${actorGender === 'female' ? 'selected' : ''}`}
                onClick={() => handleUpdateActorProfile({ gender: 'female' })}
                style={{ flex: 1, padding: '8px 12px', fontSize: 13, fontWeight: 600 }}
              >
                👩 Nữ (Female Voice)
              </button>
            </div>
          </div>

          {/* 2. Độ tuổi */}
          <div className="actor-field">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="actor-field-label" style={{ margin: 0 }}>Độ tuổi diễn viên:</span>
              <input
                type="number"
                min={15}
                max={80}
                className="actor-text-input"
                value={actorAge}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val)) {
                    setActorAge(val);
                    handleUpdateActorProfile({ age: val });
                  }
                }}
                onBlur={(e) => {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val)) handleUpdateActorProfile({ age: val });
                }}
                style={{ width: 65, textAlign: 'center', fontWeight: 600 }}
              />
              <span style={{ fontSize: 13 }} className="muted">tuổi</span>
            </div>
          </div>

          {/* 3. Giọng đọc (Vùng miền) */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>Giọng đọc (Bắc - Trung - Nam):</span>
            </div>
            <div className="actor-chips-row">
              {(['Bắc', 'Trung', 'Nam'] as const).map((region) => (
                <button
                  key={region}
                  type="button"
                  className={`actor-chip ${actorTone === region ? 'selected' : ''}`}
                  onClick={() => handleUpdateActorProfile({ voice_tone: region })}
                  style={{ minWidth: 70, textAlign: 'center', fontWeight: 600 }}
                >
                  {region}
                </button>
              ))}
            </div>
          </div>

          {/* 4. Tên / Danh xưng diễn viên (tùy chọn) */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>Tên / Danh xưng người dẫn <span className="muted" style={{ fontWeight: 400 }}>(tùy chọn):</span></span>
            </div>
            <input
              type="text"
              className="actor-text-input"
              placeholder="Ví dụ: Minh Quân, Thu Hà, MC Nam, Host..."
              value={actorName}
              onChange={(e) => setActorName(e.target.value)}
              onBlur={(e) => handleUpdateActorProfile({ name: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleUpdateActorProfile({ name: (e.target as HTMLInputElement).value });
              }}
            />
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
