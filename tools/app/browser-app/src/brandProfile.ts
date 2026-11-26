import { apiJson } from './api';

export type BrandProfile = {
  identity: string;
  audience: string;
  differentiator: string;
  tone: string;
  keywords: string[];
};

export const BRAND_PROFILE_KEY = 'aibrand_brand_profile';
export const BRAND_UPDATED_EVENT = 'aibrand-brand-updated';
export const BRAND_ASSISTANT_STORAGE_KEY = 'aibrand-brand-assistant-v1';

const EMPTY_BRAND: BrandProfile = {
  identity: '',
  audience: '',
  differentiator: '',
  tone: '',
  keywords: [],
};

export function normalizeKeywords(items: unknown): string[] {
  const raw = Array.isArray(items) ? items : typeof items === 'string' ? items.split(',') : [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of raw) {
    const cleaned = String(item || '')
      .trim()
      .slice(0, 80);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
    if (out.length >= 20) break;
  }
  return out;
}

export function normalizeBrand(raw?: Partial<BrandProfile> | null): BrandProfile {
  return {
    identity: String(raw?.identity || ''),
    audience: String(raw?.audience || ''),
    differentiator: String(raw?.differentiator || ''),
    tone: String(raw?.tone || ''),
    keywords: normalizeKeywords(raw?.keywords),
  };
}

export function loadCachedBrand(): BrandProfile {
  try {
    const raw = localStorage.getItem(BRAND_PROFILE_KEY);
    if (raw) {
      return normalizeBrand(JSON.parse(raw));
    }
  } catch {
    // ignore storage errors
  }
  return { ...EMPTY_BRAND };
}

export function hasBrandProfile(b: BrandProfile): boolean {
  return Boolean(
    b.identity.trim() || b.audience.trim() || b.differentiator.trim() || b.tone.trim() || b.keywords.length > 0,
  );
}

export function cacheBrandProfile(raw?: Partial<BrandProfile> | null): BrandProfile {
  const next = normalizeBrand(raw);
  try {
    localStorage.setItem(BRAND_PROFILE_KEY, JSON.stringify(next));
  } catch {
    // ignore storage errors
  }
  window.dispatchEvent(new CustomEvent<BrandProfile>(BRAND_UPDATED_EVENT, { detail: next }));
  return next;
}

export async function saveBrandProfile(patch: Partial<BrandProfile>): Promise<BrandProfile> {
  const current = loadCachedBrand();
  const nextKeywords =
    patch.keywords !== undefined ? normalizeKeywords(patch.keywords) : current.keywords;

  const next: BrandProfile = {
    identity: patch.identity !== undefined ? patch.identity : current.identity,
    audience: patch.audience !== undefined ? patch.audience : current.audience,
    differentiator: patch.differentiator !== undefined ? patch.differentiator : current.differentiator,
    tone: patch.tone !== undefined ? patch.tone : current.tone,
    keywords: nextKeywords,
  };

  try {
    localStorage.setItem(BRAND_PROFILE_KEY, JSON.stringify(next));
  } catch {
    // ignore storage errors
  }

  await apiJson('/api/user/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brand: next }),
  });

  window.dispatchEvent(new CustomEvent<BrandProfile>(BRAND_UPDATED_EVENT, { detail: next }));
  return next;
}
