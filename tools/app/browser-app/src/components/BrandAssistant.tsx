import { IonIcon } from '@ionic/react';
import { sendOutline } from 'ionicons/icons';
import React, { useState } from 'react';

import { apiJson } from '../api';
import { type BrandProfile, loadCachedBrand, saveBrandProfile } from '../brandProfile';
import { useLocale } from '../locales';
import './BrandAssistant.css';

export type AssistantMode = 'brand_setup' | 'keyword_explore';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  brandDraft?: Partial<BrandProfile>;
  keywords?: string[];
  saved?: boolean;
};

type BrandAssistantResponse = {
  ok: boolean;
  mode: AssistantMode;
  reply: string;
  brand_draft?: Partial<Omit<BrandProfile, 'keywords'>>;
  keywords?: string[];
  ready?: boolean;
};

type BrandAssistantProps = {
  onSearchKeyword: (keyword: string) => void;
  onSearchKeywords?: (keywords: string[]) => void;
  blocked: boolean;
};

function makeWelcome(mode: AssistantMode, welcomeText: string): ChatMessage {
  return {
    id: `welcome-${mode}`,
    role: 'assistant',
    content: welcomeText,
  };
}

export const BrandAssistant: React.FC<BrandAssistantProps> = ({ onSearchKeyword, onSearchKeywords, blocked }) => {
  const { locale, t } = useLocale();
  const m = t.analyzer.brandAssistant;

  const [mode, setMode] = useState<AssistantMode>('brand_setup');
  const [histories, setHistories] = useState<Record<AssistantMode, ChatMessage[]>>(() => ({
    brand_setup: [makeWelcome('brand_setup', m.modes.brand_setup.welcome)],
    keyword_explore: [makeWelcome('keyword_explore', m.modes.keyword_explore.welcome)],
  }));
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [savingMsgId, setSavingMsgId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const messages = histories[mode];
  const modeCopy = m.modes[mode];

  const handleReset = () => {
    setHistories((prev) => ({
      ...prev,
      [mode]: [makeWelcome(mode, m.modes[mode].welcome)],
    }));
    setError(null);
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const activeMode = mode;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
    };
    const nextHistory = [...histories[activeMode], userMsg];
    setHistories((prev) => ({ ...prev, [activeMode]: nextHistory }));
    setInput('');
    setError(null);
    setSending(true);

    try {
      const payloadMessages = nextHistory
        .filter((item) => !item.id.startsWith('welcome-'))
        .map((item) => ({ role: item.role, content: item.content }));

      const res = await apiJson<BrandAssistantResponse>('/api/brand-assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: activeMode,
          messages: payloadMessages,
          brand: loadCachedBrand(),
          language: locale,
        }),
      });

      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: res.reply || '',
        brandDraft: activeMode === 'brand_setup' ? res.brand_draft : undefined,
        keywords: Array.isArray(res.keywords) ? res.keywords : [],
      };
      setHistories((prev) => ({
        ...prev,
        [activeMode]: [...prev[activeMode], assistantMsg],
      }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : m.errorFallback);
    } finally {
      setSending(false);
    }
  };

  const handleSaveDraft = async (msg: ChatMessage) => {
    if (mode !== 'brand_setup') return;
    setSavingMsgId(msg.id);
    setError(null);
    try {
      await saveBrandProfile(
        {
          ...(msg.brandDraft || {}),
          keywords: msg.keywords || [],
        },
        { mergeKeywords: true },
      );
      setHistories((prev) => ({
        ...prev,
        brand_setup: prev.brand_setup.map((item) => (item.id === msg.id ? { ...item, saved: true } : item)),
      }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t.brand.saveError);
    } finally {
      setSavingMsgId(null);
    }
  };

  return (
    <section className="panel keyword-search-panel" id="brand-assistant">
      <div className="brand-assistant-head">
        <h2>{m.title}</h2>
        <button type="button" className="ghost small brand-assistant-reset" onClick={handleReset} disabled={sending}>
          {m.resetBtn}
        </button>
      </div>

      <div className="brand-mode-tabs" role="tablist">
        {(['brand_setup', 'keyword_explore'] as AssistantMode[]).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mode === id}
            className={`brand-mode-btn ${mode === id ? 'active' : ''}`}
            onClick={() => {
              setMode(id);
              setError(null);
            }}
          >
            {m.modes[id].label}
          </button>
        ))}
      </div>

      <p className="muted brand-mode-subtitle">{modeCopy.subtitle}</p>

      <div className="brand-chat-messages" aria-live="polite">
        {messages.map((msg) => {
          const draftEntries = msg.brandDraft
            ? (Object.entries(msg.brandDraft).filter(([, v]) => Boolean(v)) as [string, string][])
            : [];
          const hasKeywords = Boolean(msg.keywords && msg.keywords.length > 0);
          const showDraftCard =
            mode === 'brand_setup' && msg.role === 'assistant' && (draftEntries.length > 0 || hasKeywords);

          return (
            <div key={msg.id} className={`brand-chat-msg ${msg.role}`}>
              <p className="brand-chat-text">{msg.content}</p>

              {showDraftCard && (
                <div className="brand-draft-card">
                  <span className="brand-draft-title">{m.draftTitle}</span>
                  {draftEntries.map(([field, value]) => {
                    const qLabel = t.brand.questions.find((q) => q.key === field)?.label || field;
                    return (
                      <div key={field} className="brand-draft-row">
                        <strong>{qLabel}:</strong> {value}
                      </div>
                    );
                  })}
                  <button
                    type="button"
                    className="primary small brand-draft-save"
                    disabled={savingMsgId === msg.id || Boolean(msg.saved)}
                    onClick={() => handleSaveDraft(msg)}
                  >
                    {msg.saved ? m.savedToBrandBtn : m.saveToBrandBtn}
                  </button>
                </div>
              )}

              {hasKeywords && msg.role === 'assistant' && (
                <div className="brand-kw-wrap">
                  <span className="brand-kw-heading">{m.keywordsHeading}</span>
                  <div className="brand-kw-list">
                    {msg.keywords!.map((kw) => (
                      <button
                        key={kw}
                        type="button"
                        className="brand-kw-chip"
                        disabled={blocked}
                        title={m.exploreKeywordTitle(kw)}
                        onClick={() => onSearchKeyword(kw)}
                      >
                        {kw} ↗
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="primary small brand-search-cta"
                    disabled={blocked}
                    onClick={() =>
                      onSearchKeywords ? onSearchKeywords(msg.keywords!) : onSearchKeyword(msg.keywords![0])
                    }
                  >
                    {m.searchKeywordsBtn(msg.keywords!.length)}
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {sending && (
          <div className="brand-chat-msg assistant">
            <p className="brand-chat-text muted">{m.thinking}</p>
          </div>
        )}
      </div>

      {error && (
        <div className="alert error" style={{ marginBottom: 'var(--space-2)', marginTop: 0 }}>
          {error}
        </div>
      )}

      <form className="brand-chat-form" onSubmit={handleSend}>
        <input
          type="text"
          className="text-input brand-chat-input"
          placeholder={modeCopy.placeholder}
          aria-label={modeCopy.placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button
          type="submit"
          className="primary brand-chat-send"
          aria-label={m.sendBtn}
          title={m.sendBtn}
          disabled={sending || !input.trim()}
        >
          <IonIcon icon={sendOutline} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
};
