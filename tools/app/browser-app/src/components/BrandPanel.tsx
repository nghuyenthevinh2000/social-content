import { IonToast } from '@ionic/react';
import React, { useEffect, useState } from 'react';

import { apiJson } from '../api';
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

const BRAND_QUESTIONS: {
  key: keyof BrandProfile;
  label: string;
  hint: string;
  placeholder: string;
}[] = [
  {
    key: 'identity',
    label: 'Nhân hiệu',
    hint: 'Khi nhắc tới bạn, mọi người sẽ nhớ tới gì? VD: Chin-su là nước tương, Hảo hảo là mì gói',
    placeholder: 'VD: Chuyên gia chăm sóc da khoa học dễ hiểu, mẹ bỉm nấu ăn 15 phút...',
  },
  {
    key: 'audience',
    label: 'Khách hàng mục tiêu',
    hint: 'Bạn có nhiều mối quan hệ trong nhóm khách hàng này',
    placeholder: 'VD: Dân văn phòng 25–35 tuổi bận rộn, chủ quán nhỏ...',
  },
  {
    key: 'differentiator',
    label: 'Điểm khác biệt',
    hint: 'Điều gì khiến người xem nhớ và chọn bạn thay vì kênh khác?',
    placeholder: 'VD: Thử nghiệm thực tế, giải thích ngắn gọn không vòng vo...',
  },
  {
    key: 'tone',
    label: 'Phong cách & Giọng điệu',
    hint: 'Nếu nhân hiệu là một người, bạn nói chuyện theo phong thái nào?',
    placeholder: 'VD: Thẳng thắn, gần gũi, hài hước đời thường...',
  },
];

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
      setError(err instanceof Error ? err.message : 'Không thể lưu thông tin nhân hiệu');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="actor-profile-box" style={{ marginTop: 0 }}>
      {error && <div className="alert error">{error}</div>}
      {BRAND_QUESTIONS.map((q) => (
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
          Cập nhật Brand
        </button>
      </div>
      <IonToast
        isOpen={toastOpen}
        message="Đã cập nhật Brand"
        color="success"
        duration={2500}
        position="top"
        onDidDismiss={() => setToastOpen(false)}
      />
    </div>
  );
}
