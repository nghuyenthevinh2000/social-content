import { IonIcon } from '@ionic/react';
import { sendOutline } from 'ionicons/icons';
import React, { useEffect, useRef, useState, useSyncExternalStore } from 'react';

import {
  type AssistantMode,
  getAssistantInput,
  getBrandAssistantSnapshot,
  saveAssistantDraft,
  sendAssistantMessage,
  setAssistantInput,
  setAssistantMode,
  subscribeBrandAssistant,
} from '../brandAssistantStore';
import {
  BRAND_UPDATED_EVENT,
  type BrandProfile,
  hasBrandProfile,
  loadCachedBrand,
  normalizeBrand,
} from '../brandProfile';
import { useLocale } from '../locales';
import './BrandAssistant.css';

export type { AssistantMode };

type BrandAssistantProps = {
  onSearchKeyword: (keyword: string) => void;
  onSearchKeywords?: (keywords: string[]) => void;
  blocked: boolean;
  showHistory?: boolean;
  onSelectHistory?: () => void;
  onSelectChat?: () => void;
};

function renderFormattedText(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

export const BrandAssistant: React.FC<BrandAssistantProps> = ({
  onSearchKeyword,
  onSearchKeywords,
  blocked,
  showHistory = false,
  onSelectHistory,
  onSelectChat,
}) => {
  const { locale, t } = useLocale();
  const m = t.analyzer.brandAssistant;

  const state = useSyncExternalStore(subscribeBrandAssistant, getBrandAssistantSnapshot);
  const { mode, histories, pending, errors, savingMsgId } = state;

  const [input, setInput] = useState<string>(() => getAssistantInput(mode));
  const [brand, setBrand] = useState<BrandProfile>(() => loadCachedBrand());
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input, mode, showHistory]);

  useEffect(() => {
    const onUpdated = (e: Event) => {
      const detail = (e as CustomEvent<BrandProfile>).detail;
      setBrand(detail ? normalizeBrand(detail) : loadCachedBrand());
    };
    window.addEventListener(BRAND_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(BRAND_UPDATED_EVENT, onUpdated);
  }, []);

  const messages = histories[mode];
  const sending = pending[mode];
  const error = errors[mode];
  const modeCopy = m.modes[mode];
  const brandSummary = [
    ...t.brand.questions
      .map((q) => {
        const val = brand[q.key].trim();
        return val ? `• ${q.label}: ${val}` : '';
      })
      .filter(Boolean),
    ...(brand.keywords.length > 0 ? [`• ${t.brand.keywordsLabel}: ${brand.keywords.join(', ')}`] : []),
  ].join('\n');

  const welcomeText =
    mode === 'brand_setup' && hasBrandProfile(brand)
      ? m.modes.brand_setup.welcomeExisting(brandSummary)
      : modeCopy.welcome;

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (sending || !input.trim()) return;
    const text = input;
    setInput('');
    void sendAssistantMessage(mode, text, locale, m.errorFallback);
  };

  return (
    <section className={`panel keyword-search-panel ${showHistory ? '' : 'brand-assistant-full'}`} id="brand-assistant">
      <div className="brand-mode-tabs" role="tablist">
        {(['brand_setup', 'keyword_explore'] as AssistantMode[]).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={!showHistory && mode === id}
            className={`brand-mode-btn ${!showHistory && mode === id ? 'active' : ''}`}
            onClick={() => {
              setAssistantMode(id);
              setInput(getAssistantInput(id));
              onSelectChat?.();
            }}
          >
            {m.modes[id].label}
          </button>
        ))}
        {onSelectHistory && (
          <button
            type="button"
            role="tab"
            aria-selected={Boolean(showHistory)}
            className={`brand-mode-btn ${showHistory ? 'active' : ''}`}
            onClick={onSelectHistory}
          >
            {m.historyTab}
          </button>
        )}
      </div>

      {!showHistory && (
        <>
          <div className="brand-chat-messages" aria-live="polite">
            <div className="brand-chat-msg assistant">
              <p className="brand-chat-text">{welcomeText}</p>
            </div>
            {messages.map((msg) => {
              const draftEntries = msg.brandDraft
                ? (Object.entries(msg.brandDraft).filter(([, v]) => Boolean(v)) as [string, string][])
                : [];
              const hasKeywords = Boolean(msg.keywords && msg.keywords.length > 0);
              const showDraftCard =
                mode === 'brand_setup' && msg.role === 'assistant' && (draftEntries.length > 0 || hasKeywords);

              return (
                <div key={msg.id} className={`brand-chat-msg ${msg.role}`}>
                  <p className="brand-chat-text">
                    {msg.role === 'assistant' ? renderFormattedText(msg.content) : msg.content}
                  </p>

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
                        onClick={() => void saveAssistantDraft(msg, t.brand.saveError)}
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
            <textarea
              ref={textareaRef}
              rows={1}
              className="text-input brand-chat-input"
              placeholder={modeCopy.placeholder}
              aria-label={modeCopy.placeholder}
              value={input}
              onChange={(e) => {
                const next = e.target.value;
                setInput(next);
                setAssistantInput(mode, next);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  if (!sending && input.trim()) {
                    const text = input;
                    setInput('');
                    void sendAssistantMessage(mode, text, locale, m.errorFallback);
                  }
                }
              }}
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
        </>
      )}
    </section>
  );
};
