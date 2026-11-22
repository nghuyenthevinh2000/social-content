import { IonToast } from '@ionic/react';
import React, { useEffect, useState } from 'react';

import { apiJson } from '../api';
import {
  BRAND_PROFILE_KEY,
  BRAND_UPDATED_EVENT,
  type BrandProfile,
  loadCachedBrand,
  normalizeBrand,
  normalizeKeywords,
  saveBrandProfile,
} from '../brandProfile';
import { useLocale } from '../locales';
import './MediaPanel.css';

export type { BrandProfile };

export function BrandPanel(): React.ReactElement {
  const { t } = useLocale();
  const [brand, setBrand] = useState<BrandProfile>(() => loadCachedBrand());
  const [keywordsText, setKeywordsText] = useState<string>(() => loadCachedBrand().keywords.join(', '));
  const [saving, setSaving] = useState(false);
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    apiJson<{ ok: boolean; profile?: { brand?: Partial<BrandProfile> } }>('/api/user/profile')
      .then((res) => {
        if (ignore || !res.ok || !res.profile?.brand) return;
        const next = normalizeBrand(res.profile.brand);
        setBrand(next);
        setKeywordsText(next.keywords.join(', '));
        try {
          localStorage.setItem(BRAND_PROFILE_KEY, JSON.stringify(next));
        } catch {
          // ignore storage errors
        }
      })
      .catch(() => {
        // preserve cached state
      });

    const onUpdated = (e: Event) => {
      const detail = (e as CustomEvent<BrandProfile>).detail;
      if (!detail) return;
      const next = normalizeBrand(detail);
      setBrand(next);
      setKeywordsText(next.keywords.join(', '));
    };
    window.addEventListener(BRAND_UPDATED_EVENT, onUpdated);
    return () => {
      ignore = true;
      window.removeEventListener(BRAND_UPDATED_EVENT, onUpdated);
    };
  }, []);

  const saveBrand = async (next: BrandProfile, showPopup = false) => {
    try {
      setSaving(true);
      setError(null);
      await saveBrandProfile(next);
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
      <div className="actor-field">
        <div className="actor-field-label">
          <label htmlFor="brand-keywords">{t.brand.keywordsLabel}:</label>
        </div>
        <p className="actor-field-hint actor-field-hint-compact">{t.brand.keywordsHint}</p>
        <input
          id="brand-keywords"
          type="text"
          className="actor-text-input"
          placeholder={t.brand.keywordsPlaceholder}
          value={keywordsText}
          onChange={(e) => {
            const val = e.target.value;
            setKeywordsText(val);
            setBrand((prev) => ({ ...prev, keywords: normalizeKeywords(val) }));
          }}
          onBlur={(e) => {
            const parsed = normalizeKeywords(e.target.value);
            const next = { ...brand, keywords: parsed };
            setBrand(next);
            setKeywordsText(parsed.join(', '));
            saveBrand(next);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const parsed = normalizeKeywords((e.target as HTMLInputElement).value);
              const next = { ...brand, keywords: parsed };
              setBrand(next);
              setKeywordsText(parsed.join(', '));
              saveBrand(next);
            }
          }}
        />
        {brand.keywords.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)', marginTop: 'var(--space-1)' }}>
            {brand.keywords.map((kw) => (
              <span key={kw} className="badge">
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>
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
