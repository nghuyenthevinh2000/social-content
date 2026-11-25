import { IonIcon } from '@ionic/react';
import { checkmarkOutline, copyOutline, sendOutline } from 'ionicons/icons';
import React, { useEffect, useRef, useState, useSyncExternalStore } from 'react';

import {
  type AssistantMode,
  getAssistantInput,
  getBrandAssistantSnapshot,
  researchAssistantHashtags,
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
import { copyToClipboard } from '../analysis/format';
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

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  const trimmed = line.trim();
  return /^\|(?:\s*:?-{3,}:?\s*\|)+$/.test(trimmed);
}

function isHashtagCopyLine(line: string): boolean {
  const tokens = line.trim().split(/\s+/).filter(Boolean);
  return tokens.length >= 1 && tokens.every((tok) => /^#[^\s#]+$/.test(tok));
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
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const copiedTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
    };
  }, []);

  const handleCopyMessage = (msgId: string, text: string) => {
    void copyToClipboard(text)
      .then(() => {
        setCopiedId(msgId);
        if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
        copiedTimerRef.current = window.setTimeout(() => setCopiedId(null), 1500);
      })
      .catch(() => {});
  };

  const renderCopyBtn = (msgId: string, text: string) => {
    const isCopied = copiedId === msgId;
    return (
      <button
        type="button"
        className={`brand-chat-copy-btn ${isCopied ? 'copied' : ''}`}
        aria-label={isCopied ? m.copiedToast : m.copyMsgBtn}
        title={isCopied ? m.copiedToast : m.copyMsgBtn}
        onClick={() => handleCopyMessage(msgId, text)}
      >
        <IonIcon icon={isCopied ? checkmarkOutline : copyOutline} aria-hidden="true" />
      </button>
    );
  };

  const renderAssistantContent = (text: string, msgId: string): React.ReactNode => {
    const lines = text.split('\n');
    const blocks: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      if (
        i + 1 < lines.length &&
        lines[i].trim().startsWith('|') &&
        lines[i].trim().endsWith('|') &&
        isTableSeparator(lines[i + 1])
      ) {
        const headers = splitTableRow(lines[i]);
        i += 2;
        const bodyRows: string[][] = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          bodyRows.push(splitTableRow(lines[i]));
          i += 1;
        }
        blocks.push(
          <div key={`tbl-${i}`} className="brand-table-wrap">
            <table className="brand-chat-table">
              <thead>
                <tr>
                  {headers.map((h, idx) => (
                    <th key={idx}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {headers.map((_, cIdx) => (
                      <td key={cIdx}>{renderFormattedText(row[cIdx] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
        continue;
      }

      if (isHashtagCopyLine(lines[i])) {
        const tagLine = lines[i].trim();
        const isTagsCopied = copiedId === `${msgId}-tags`;
        blocks.push(
          <div key={`tags-${i}`} className="brand-hashtag-copy">
            <code>{tagLine}</code>
            <button
              type="button"
              className={`brand-hashtag-copy-btn ${isTagsCopied ? 'copied' : ''}`}
              onClick={() => handleCopyMessage(`${msgId}-tags`, tagLine)}
            >
              {isTagsCopied ? m.copiedToast : m.copyHashtagsBtn}
            </button>
          </div>,
        );
        i += 1;
        continue;
      }

      const textLines: string[] = [];
      while (
        i < lines.length &&
        !(
          i + 1 < lines.length &&
          lines[i].trim().startsWith('|') &&
          lines[i].trim().endsWith('|') &&
          isTableSeparator(lines[i + 1])
        ) &&
        !isHashtagCopyLine(lines[i])
      ) {
        textLines.push(lines[i]);
        i += 1;
      }
      const chunk = textLines.join('\n').trim();
      if (chunk) {
        blocks.push(
          <p key={`txt-${i}`} className="brand-chat-text">
            {renderFormattedText(chunk)}
          </p>,
        );
      }
    }

    return blocks.length > 0 ? blocks : <p className="brand-chat-text">{renderFormattedText(text)}</p>;
  };

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
        {(['brand_setup'] as AssistantMode[]).map((id) => (
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
            <div className="brand-chat-row assistant">
              <div className="brand-chat-msg assistant">
                <p className="brand-chat-text">{welcomeText}</p>
              </div>
              {renderCopyBtn('welcome', welcomeText)}
            </div>
            {messages.map((msg) => {
              const draftEntries = msg.brandDraft
                ? (Object.entries(msg.brandDraft).filter(([, v]) => Boolean(v)) as [string, string][])
                : [];
              const hasKeywords = Boolean(msg.keywords && msg.keywords.length > 0);
              const showDraftCard =
                mode === 'brand_setup' && msg.role === 'assistant' && (draftEntries.length > 0 || hasKeywords);

              return (
                <div key={msg.id} className={`brand-chat-row ${msg.role}`}>
                  {msg.role === 'user' && renderCopyBtn(msg.id, msg.content)}
                  <div className={`brand-chat-msg ${msg.role}`}>
                    {msg.role === 'assistant' ? (
                      renderAssistantContent(msg.content, msg.id)
                    ) : (
                      <p className="brand-chat-text">{msg.content}</p>
                    )}

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
                            <span key={kw} className="brand-kw-chip">
                              {kw}
                            </span>
                          ))}
                        </div>
                        <div className="brand-kw-actions">
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
                          <button
                            type="button"
                            className="secondary small brand-hashtag-cta"
                            disabled={sending}
                            onClick={() =>
                              void researchAssistantHashtags(
                                mode,
                                msg.keywords!,
                                locale,
                                m.hashtagPrompt(msg.keywords!),
                                m.errorFallback,
                              )
                            }
                          >
                            {m.hashtagResearchBtn}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                  {msg.role === 'assistant' && renderCopyBtn(msg.id, msg.content)}
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
