import { useEffect, useRef, useState } from 'react';

import { apiFetch, apiJson } from '../api';
import { useLocale } from '../locales';
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
  const { t } = useLocale();
  const m = t.media;
  const cached = loadCachedProfile();
  const [profile, setProfile] = useState<MediaItem | null>(null);
  const [contextList, setContextList] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actorGender, setActorGender] = useState<'male' | 'female'>(cached?.gender === 'female' ? 'female' : 'male');
  const [actorAge, setActorAge] = useState<number>(
    typeof cached?.age === 'number' && cached.age >= 15 && cached.age <= 80 ? cached.age : 28,
  );
  const [actorName, setActorName] = useState<string>(cached?.name || '');
  const [actorTone, setActorTone] = useState<string>(
    cached?.voice_tone && ['Bắc', 'Trung', 'Nam'].includes(cached.voice_tone) ? cached.voice_tone : 'Bắc',
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
      setError(err?.message || m.loadError);
    } finally {
      setLoading(false);
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
            }),
          );
        } catch {}
      }
    } catch {
      // ignore network errors, preserve cached state
    }
  };

  const handleUpdateActorProfile = async (
    updates: Partial<{ gender: 'male' | 'female'; age: number; name: string; voice_tone: string }>,
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
        }),
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
      setError(err?.message || m.saveActorError);
    } finally {
      setSavingProfile(false);
    }
  };

  useEffect(() => {
    fetchMedia();
    fetchActorProfile();
  }, []);

  const handleUpload = async (kind: 'profile' | 'context', file: File) => {
    try {
      setLoading(true);
      setError(null);
      const ext = file.name.toLowerCase();
      const mime =
        file.type || (ext.endsWith('.png') ? 'image/png' : ext.endsWith('.webp') ? 'image/webp' : 'image/jpeg');
      const res = await apiFetch(`/api/media?kind=${kind}`, {
        method: 'POST',
        headers: {
          'Content-Type': mime,
        },
        body: file,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || m.uploadError);
      }
      await fetchMedia();
      onMediaUpdated?.();
    } catch (err: any) {
      setError(err?.message || m.uploadFailed);
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
      setError(err?.message || m.deleteFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="media-panel">
      {error && <div className="notice error">{error}</div>}

      <div className="media-section">
        <div className="media-section-title">
          <span>{m.profileSectionTitle}</span>
          <small className="muted">{profile ? m.profileCountYes : m.profileCountNo}</small>
        </div>

        <div className="profile-card">
          {profile ? (
            <img src={mediaUrl(profile)} alt="Profile" className="profile-preview" />
          ) : (
            <div className="profile-placeholder">👤</div>
          )}

          <div className="profile-info">
            <strong>{profile ? m.profileHasPhoto : m.profileNoPhoto}</strong>
            <small>{profile ? `${(profile.bytes / 1024).toFixed(0)} KB` : m.profileHint}</small>

            <div className="media-btn-row">
              <input
                ref={profileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden-file-input"
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
                {profile ? m.replacePhoto : m.uploadPhoto}
              </button>

              {profile && (
                <button
                  type="button"
                  className="media-action-btn danger"
                  onClick={() => handleDelete(profile.id)}
                  disabled={loading}
                >
                  {t.common.delete}
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="actor-profile-box">
          <div className="actor-profile-head">
            <span className="actor-profile-title">
              <span>🎭</span>
              <span>{m.actorSectionTitle}</span>
            </span>
          </div>

          <p className="actor-field-hint actor-field-hint-compact">
            {m.actorHintPrefix}
            <strong>{m.actorHintStrong}</strong>
            {m.actorHintSuffix}
          </p>

          {/* 1. Gender */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>{m.genderLabel}</span>
            </div>
            <div className="actor-gender-row">
              <button
                type="button"
                className={`actor-chip actor-chip-gender ${actorGender === 'male' ? 'selected' : ''}`}
                onClick={() => handleUpdateActorProfile({ gender: 'male' })}
              >
                {m.male}
              </button>
              <button
                type="button"
                className={`actor-chip actor-chip-gender ${actorGender === 'female' ? 'selected' : ''}`}
                onClick={() => handleUpdateActorProfile({ gender: 'female' })}
              >
                {m.female}
              </button>
            </div>
          </div>

          {/* 2. Age */}
          <div className="actor-field">
            <div className="actor-age-row">
              <span className="actor-field-label actor-age-label">{m.ageLabel}</span>
              <input
                type="number"
                min={15}
                max={80}
                className="actor-text-input actor-age-input"
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
              />
              <span className="muted actor-age-unit">{m.ageUnit}</span>
            </div>
          </div>

          {/* 3. Voice accent */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>{m.regionLabel}</span>
            </div>
            <div className="actor-chips-row">
              {(['Bắc', 'Trung', 'Nam'] as const).map((region) => (
                <button
                  key={region}
                  type="button"
                  className={`actor-chip actor-chip-region ${actorTone === region ? 'selected' : ''}`}
                  onClick={() => handleUpdateActorProfile({ voice_tone: region })}
                >
                  {m.regions[region] || region}
                </button>
              ))}
            </div>
          </div>

          {/* 4. Actor name (optional) */}
          <div className="actor-field">
            <div className="actor-field-label">
              <span>
                {m.actorNameLabel}
                <span className="muted actor-optional-label">{m.actorNameOptional}</span>
              </span>
            </div>
            <input
              type="text"
              className="actor-text-input"
              placeholder={m.actorNamePlaceholder}
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
          <span>{m.contextSectionTitle}</span>
          <small className="muted">{m.contextCount(contextList.length)}</small>
        </div>

        <div className="context-grid">
          {contextList.map((item) => (
            <div key={item.id} className="context-card">
              <img src={mediaUrl(item)} alt="Context" />
              <button
                type="button"
                className="delete-chip"
                title={m.deletePhotoTitle}
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
            className="hidden-file-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload('context', file);
              e.target.value = '';
            }}
          />
          <div className="context-upload-card" onClick={() => contextInputRef.current?.click()}>
            <span>+</span>
            <div>{m.addPhoto}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
