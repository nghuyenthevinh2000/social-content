import { IonToast } from '@ionic/react';
import React, { useEffect, useState } from 'react';

import { apiJson } from '../api';
import { useLocale } from '../locales';
import './MediaPanel.css';

export type BrandProfile = {
  identity: string;
  audience: string;
  differentiator: string;
  tone: string;
};

const BRAND_PROFILE_KEY = 'aibrand_brand_profile';

const EMPTY_BRAND: BrandProfile = {
  identity: '',
  audience: '',
  differentiator: '',
  tone: '',
};

function loadCachedBrand(): BrandProfile {
  try {
    const raw = localStorage.getItem(BRAND_PROFILE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        identity: String(parsed?.identity || ''),
        audience: String(parsed?.audience || ''),
        differentiator: String(parsed?.differentiator || ''),
        tone: String(parsed?.tone || ''),
      };
    }
  } catch {
    // ignore storage errors
  }
  return { ...EMPTY_BRAND };
}

export function BrandPanel(): React.ReactElement {
  const { t } = useLocale();
  const [brand, setBrand] = useState<BrandProfile>(() => loadCachedBrand());
  const [saving, setSaving] = useState(false);
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    apiJson<{ ok: boolean; profile?: { brand?: Partial<BrandProfile> } }>('/api/user/profile')
      .then((res) => {
        if (ignore || !res.ok || !res.profile?.brand) return;
        const b = res.profile.brand;
        const next: BrandProfile = {
          identity: String(b.identity || ''),
          audience: String(b.audience || ''),
          differentiator: String(b.differentiator || ''),
          tone: String(b.tone || ''),
        };
        setBrand(next);
        try {
          localStorage.setItem(BRAND_PROFILE_KEY, JSON.stringify(next));
        } catch {
          // ignore storage errors
        }
      })
      .catch(() => {
        // preserve cached state
      });
    return () => {
      ignore = true;
    };
  }, []);

  const saveBrand = async (next: BrandProfile, showPopup = false) => {
    try {
      localStorage.setItem(BRAND_PROFILE_KEY, JSON.stringify(next));
    } catch {
      // ignore storage errors
    }
    try {
      setSaving(true);
      setError(null);
      await apiJson('/api/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brand: next }),
      });
      if (showPopup) {
        setToastOpen(true);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t.brand.saveError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="actor-profile-box" style={{ marginTop: 0 }}>
      {error && <div className="alert error">{error}</div>}
      {t.brand.questions.map((q) => (
        <div key={q.key} className="actor-field">
          <div className="actor-field-label">
            <label htmlFor={`brand-${q.key}`}>{q.label}:</label>
          </div>
          <p className="actor-field-hint actor-field-hint-compact">{q.hint}</p>
          <input
            id={`brand-${q.key}`}
            type="text"
            className="actor-text-input"
            placeholder={q.placeholder}
            value={brand[q.key]}
            onChange={(e) => {
              setBrand((prev) => ({ ...prev, [q.key]: e.target.value }));
            }}
            onBlur={(e) => {
              const next = { ...brand, [q.key]: e.target.value };
              saveBrand(next);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const next = { ...brand, [q.key]: (e.target as HTMLInputElement).value };
                saveBrand(next);
              }
            }}
          />
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
        <button type="button" className="primary small" onClick={() => saveBrand(brand, true)} disabled={saving}>
          {t.brand.saveBtn}
        </button>
      </div>
      <IonToast
        isOpen={toastOpen}
        message={t.brand.savedToast}
        color="success"
        duration={2500}
        position="top"
        onDidDismiss={() => setToastOpen(false)}
      />
    </div>
  );
}
