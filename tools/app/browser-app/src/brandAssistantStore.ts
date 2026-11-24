import { apiJson } from './api';
import {
  BRAND_ASSISTANT_STORAGE_KEY,
  type BrandProfile,
  cacheBrandProfile,
  loadCachedBrand,
  saveBrandProfile,
} from './brandProfile';

export type AssistantMode = 'brand_setup';

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  brandDraft?: Partial<BrandProfile>;
  keywords?: string[];
  saved?: boolean;
};

type BrandAssistantResponse = {
  ok: boolean;
  mode?: AssistantMode;
  reply?: string;
  brand_draft?: Partial<Omit<BrandProfile, 'keywords'>>;
  keywords?: string[];
  ready?: boolean;
  job_id?: string;
  status?: 'running' | 'done' | 'error';
};

export type BrandAssistantState = {
  mode: AssistantMode;
  histories: Record<AssistantMode, ChatMessage[]>;
  pending: Record<AssistantMode, boolean>;
  errors: Record<AssistantMode, string | null>;
  savingMsgId: string | null;
};

const MAX_STORED_MESSAGES = 40;
let activeUserId: string | null = null;

function storageKeyFor(userId: string | null): string {
  return userId ? `${BRAND_ASSISTANT_STORAGE_KEY}:${userId}` : BRAND_ASSISTANT_STORAGE_KEY;
}

function loadStoredState(userId: string | null): Pick<BrandAssistantState, 'mode' | 'histories'> {
  try {
    const raw = localStorage.getItem(storageKeyFor(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        mode: 'brand_setup',
        histories: {
          brand_setup: Array.isArray(parsed?.histories?.brand_setup)
            ? parsed.histories.brand_setup.slice(-MAX_STORED_MESSAGES)
            : [],
        },
      };
    }
  } catch {
    // ignore storage errors
  }
  return { mode: 'brand_setup', histories: { brand_setup: [] } };
}

function persistState(s: Pick<BrandAssistantState, 'mode' | 'histories'>, userId: string | null = activeUserId): void {
  try {
    localStorage.setItem(
      storageKeyFor(userId),
      JSON.stringify({
        mode: s.mode,
        histories: {
          brand_setup: s.histories.brand_setup.slice(-MAX_STORED_MESSAGES),
        },
      }),
    );
  } catch {
    // ignore storage errors
  }
}

function syncHistoryToBackend(histories: Record<AssistantMode, ChatMessage[]>, userId: string | null): void {
  if (!userId) return;
  apiJson('/api/user/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assistant_chat: histories }),
  }).catch(() => {});
}

function createInitialState(): BrandAssistantState {
  const stored = loadStoredState(null);
  return {
    mode: stored.mode,
    histories: stored.histories,
    pending: { brand_setup: false },
    errors: { brand_setup: null },
    savingMsgId: null,
  };
}

let state: BrandAssistantState = createInitialState();
const draftInputs: Record<AssistantMode, string> = { brand_setup: '' };
const epochs: Record<AssistantMode, number> = { brand_setup: 0 };
let userEpoch = 0;
const listeners = new Set<() => void>();

function updateState(patch: Partial<BrandAssistantState>, persist = false): void {
  state = { ...state, ...patch };
  if (persist) {
    persistState(state);
  }
  listeners.forEach((listener) => listener());
}

export function subscribeBrandAssistant(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getBrandAssistantSnapshot(): BrandAssistantState {
  return state;
}

export function setBrandAssistantUser(userId: string | null): void {
  if (userId === activeUserId) return;
  activeUserId = userId;
  userEpoch += 1;
  epochs.brand_setup += 1;
  draftInputs.brand_setup = '';

  if (!userId) {
    state = {
      mode: 'brand_setup',
      histories: { brand_setup: [] },
      pending: { brand_setup: false },
      errors: { brand_setup: null },
      savingMsgId: null,
    };
    listeners.forEach((listener) => listener());
    return;
  }

  const stored = loadStoredState(userId);
  state = {
    mode: stored.mode,
    histories: stored.histories,
    pending: { brand_setup: false },
    errors: { brand_setup: null },
    savingMsgId: null,
  };
  listeners.forEach((listener) => listener());

  const capturedUserEpoch = userEpoch;
  const capturedSetupEpoch = epochs.brand_setup;
  apiJson<{
    ok?: boolean;
    profile?: {
      brand?: Partial<BrandProfile>;
      assistant_chat?: Partial<Record<AssistantMode, ChatMessage[]>>;
    };
  }>('/api/user/profile')
    .then((res) => {
      if (userEpoch !== capturedUserEpoch || !res?.ok || !res.profile) {
        return;
      }
      if (res.profile.brand) {
        cacheBrandProfile(res.profile.brand);
      }
      if (epochs.brand_setup !== capturedSetupEpoch || !res.profile.assistant_chat) {
        return;
      }
      const remote = res.profile.assistant_chat;
      const remoteSetup = Array.isArray(remote.brand_setup) ? remote.brand_setup.slice(-MAX_STORED_MESSAGES) : [];
      if (remoteSetup.length === 0) return;

      const nextHistories: Record<AssistantMode, ChatMessage[]> = {
        brand_setup:
          remoteSetup.length >= state.histories.brand_setup.length ? remoteSetup : state.histories.brand_setup,
      };
      updateState({ histories: nextHistories }, true);
    })
    .catch(() => {});
}

export function setAssistantMode(mode: AssistantMode): void {
  updateState(
    {
      mode,
      errors: { ...state.errors, [mode]: null },
    },
    true,
  );
}

export function getAssistantInput(mode: AssistantMode): string {
  return draftInputs[mode];
}

export function setAssistantInput(mode: AssistantMode, value: string): void {
  draftInputs[mode] = value;
}

export function resetAssistantMode(mode: AssistantMode): void {
  epochs[mode] += 1;
  const nextHistories = { ...state.histories, [mode]: [] };
  updateState(
    {
      histories: nextHistories,
      pending: { ...state.pending, [mode]: false },
      errors: { ...state.errors, [mode]: null },
    },
    true,
  );
  syncHistoryToBackend(nextHistories, activeUserId);
}

export function resetBrandAssistantStore(): void {
  activeUserId = null;
  userEpoch += 1;
  epochs.brand_setup += 1;
  draftInputs.brand_setup = '';
  try {
    localStorage.removeItem(BRAND_ASSISTANT_STORAGE_KEY);
  } catch {
    // ignore storage errors
  }
  state = {
    mode: 'brand_setup',
    histories: { brand_setup: [] },
    pending: { brand_setup: false },
    errors: { brand_setup: null },
    savingMsgId: null,
  };
  listeners.forEach((listener) => listener());
}

export async function sendAssistantMessage(
  activeMode: AssistantMode,
  rawText: string,
  locale: string,
  fallbackError: string,
): Promise<void> {
  const text = rawText.trim();
  if (!text || state.pending[activeMode]) return;

  const reqEpoch = epochs[activeMode];
  const reqUser = activeUserId;
  const userMsg: ChatMessage = {
    id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    role: 'user',
    content: text,
  };
  const nextHistory = [...state.histories[activeMode], userMsg];
  draftInputs[activeMode] = '';

  updateState(
    {
      histories: { ...state.histories, [activeMode]: nextHistory },
      pending: { ...state.pending, [activeMode]: true },
      errors: { ...state.errors, [activeMode]: null },
    },
    true,
  );

  try {
    const payloadMessages = nextHistory.map((item) => ({ role: item.role, content: item.content }));
    let res = await apiJson<BrandAssistantResponse>('/api/brand-assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: activeMode,
        messages: payloadMessages,
        brand: loadCachedBrand(),
        language: locale,
        async: true,
      }),
    });

    if (res.job_id && res.reply === undefined) {
      const jobId = res.job_id;
      const deadline = Date.now() + 120_000;
      let netErrors = 0;
      while (res.status === 'running' || res.reply === undefined) {
        if (epochs[activeMode] !== reqEpoch || activeUserId !== reqUser) return;
        if (Date.now() > deadline) {
          throw new Error(fallbackError);
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (epochs[activeMode] !== reqEpoch || activeUserId !== reqUser) return;
        try {
          res = await apiJson<BrandAssistantResponse>(
            `/api/brand-assistant/chat?job_id=${encodeURIComponent(jobId)}`,
          );
          netErrors = 0;
        } catch (pollErr: unknown) {
          if (pollErr instanceof TypeError && netErrors < 5) {
            netErrors += 1;
            continue;
          }
          throw pollErr;
        }
        if (res.status === 'done' || res.reply !== undefined) break;
      }
    }

    if (epochs[activeMode] !== reqEpoch || activeUserId !== reqUser) return;

    const assistantMsg: ChatMessage = {
      id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      role: 'assistant',
      content: res.reply || '',
      brandDraft: activeMode === 'brand_setup' ? res.brand_draft : undefined,
      keywords: Array.isArray(res.keywords) ? res.keywords : [],
    };
    const nextHistories = {
      ...state.histories,
      [activeMode]: [...state.histories[activeMode], assistantMsg],
    };
    updateState(
      {
        histories: nextHistories,
        pending: { ...state.pending, [activeMode]: false },
      },
      true,
    );
    syncHistoryToBackend(nextHistories, reqUser);
  } catch (err: unknown) {
    if (epochs[activeMode] !== reqEpoch || activeUserId !== reqUser) return;
    updateState({
      pending: { ...state.pending, [activeMode]: false },
      errors: {
        ...state.errors,
        [activeMode]: err instanceof Error ? err.message : fallbackError,
      },
    });
  }
}

export async function saveAssistantDraft(msg: ChatMessage, saveErrorFallback: string): Promise<void> {
  updateState({
    savingMsgId: msg.id,
    errors: { ...state.errors, brand_setup: null },
  });
  try {
    await saveBrandProfile(
      {
        ...(msg.brandDraft || {}),
        keywords: msg.keywords || [],
      },
      { mergeKeywords: true },
    );
    const nextHistories = {
      ...state.histories,
      brand_setup: state.histories.brand_setup.map((item) => (item.id === msg.id ? { ...item, saved: true } : item)),
    };
    updateState(
      {
        savingMsgId: null,
        histories: nextHistories,
      },
      true,
    );
    syncHistoryToBackend(nextHistories, activeUserId);
  } catch (err: unknown) {
    updateState({
      savingMsgId: null,
      errors: {
        ...state.errors,
        brand_setup: err instanceof Error ? err.message : saveErrorFallback,
      },
    });
  }
}
