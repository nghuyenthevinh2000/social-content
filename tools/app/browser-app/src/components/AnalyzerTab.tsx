import React, { useEffect, useRef, useState } from 'react';

import { JobResult } from '../analysis/JobResult';
import { cleanTopicTitle, formatTime, TERMINAL } from '../analysis/format';
import type { Job, JobKind, JobSummary, Topic } from '../analysis/types';
import { useLocale } from '../locales';

import { BrandAssistant } from './BrandAssistant';

const BRAND_COLLAPSED_KEY = 'aibrand-results-brand-collapsed';
const ANALYSIS_COLLAPSED_KEY = 'aibrand-results-analysis-collapsed';

function readCollapsed(key: string): boolean {
  try {
    return localStorage.getItem(key) === '1';
  } catch {
    return false;
  }
}

type AnalyzerTabProps = {
  keyword: string;
  onKeywordChange: (value: string) => void;
  onSearchKeyword: (keyword: string) => void;
  onSearchKeywords?: (keywords: string[]) => void;
  blocked: boolean;
  error: string | null;
  starting: boolean;
  jobId: string | null;
  job: Job | null;
  visibleHistory: JobSummary[];
  loadingHistory: boolean;
  onFetchHistory: () => void;
  onSelectJob: (id: string | null) => void;
  onDeleteJob: (id: string, e: React.MouseEvent) => void;
  tourDemoId: string;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo: (topic: Topic) => void;
  onGoToLibrary: () => void;
  forceHistoryView?: boolean;
};

type ResultsSectionProps = {
  id: string;
  title: string;
  storageKey: string;
  items: JobSummary[];
  activeJob: Job | null;
  emptyText: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  loadingHistory: boolean;
  onFetchHistory: () => void;
  onSelectJob: (id: string | null) => void;
  onDeleteJob: (id: string, e: React.MouseEvent) => void;
  tourDemoId: string;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo: (topic: Topic) => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  highlighted?: boolean;
};

const ResultsSection: React.FC<ResultsSectionProps> = ({
  id,
  title,
  storageKey,
  items,
  activeJob,
  emptyText,
  emptyActionLabel,
  onEmptyAction,
  loadingHistory,
  onFetchHistory,
  onSelectJob,
  onDeleteJob,
  tourDemoId,
  copiedKey,
  onCopyTopic,
  onAddCreator,
  onSaveVideo,
  collapsed: controlledCollapsed,
  onToggleCollapsed,
  highlighted = false,
}) => {
  const { t } = useLocale();
  const m = t.analyzer;
  const [internalCollapsed, setInternalCollapsed] = useState(() => readCollapsed(storageKey));
  const collapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;
  const isTour = items.some((item) => item.id === tourDemoId) || activeJob?.id === tourDemoId;
  const isCollapsed = collapsed && !isTour;

  const toggleCollapsed = () => {
    if (onToggleCollapsed) {
      onToggleCollapsed();
      return;
    }
    setInternalCollapsed((prev) => {
      const next = !prev;
      try {
        if (next) {
          localStorage.setItem(storageKey, '1');
        } else {
          localStorage.removeItem(storageKey);
        }
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  return (
    <section className={`panel results-section ${highlighted ? 'results-highlight' : ''}`} id={id}>
      {!activeJob ? (
        <>
          <div className="panel-head collapsible-head" onClick={toggleCollapsed}>
            <div>
              <h2>{title}</h2>
              <p className="muted count">{items.length > 0 ? m.runCount(items.length) : m.noRuns}</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', flexShrink: 0 }}>
              <button
                type="button"
                className="ghost small"
                onClick={(e) => {
                  e.stopPropagation();
                  onFetchHistory();
                }}
                disabled={loadingHistory}
              >
                {loadingHistory ? t.common.loading : m.refreshBtn}
              </button>
              <button
                type="button"
                className="panel-collapse-btn"
                aria-expanded={!isCollapsed}
                aria-label={isCollapsed ? m.expandLabel(title) : m.collapseLabel(title)}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleCollapsed();
                }}
              >
                <span className={`store-toggle-icon ${!isCollapsed ? 'open' : ''}`} aria-hidden="true" />
              </button>
            </div>
          </div>

          {!isCollapsed &&
            (items.length === 0 ? (
              <div className="empty">
                <p className="muted">{emptyText}</p>
                {emptyActionLabel && onEmptyAction && (
                  <button type="button" className="ghost" onClick={onEmptyAction}>
                    {emptyActionLabel}
                  </button>
                )}
              </div>
            ) : (
              <div className="history-list">
                {items.map((item) => {
                  const isRunning = !TERMINAL.has(item.status);
                  const kind: JobKind = item.job_kind ?? 'profile';
                  return (
                    <div
                      key={item.id}
                      className={`history-card ${isRunning ? 'running-card' : ''}`}
                      onClick={() => onSelectJob(item.id)}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="history-head">
                        <span className="history-filename" title={cleanTopicTitle(item.filename)}>
                          {cleanTopicTitle(item.filename)}
                        </span>
                        <div className="history-badges">
                          <span className={`badge kind-${kind}`}>{m.kindLabel[kind]}</span>
                          <span className={`badge ${item.status}`}>
                            {isRunning && <span className="live-dot" />}
                            {t.analysis.statusLabel[item.status] || item.status}
                          </span>
                        </div>
                      </div>
                      <div className="history-meta muted">
                        <span>{formatTime(item.created_at)}</span>
                        <span>·</span>
                        <span>{m.topicsCount(item.total_sheets)}</span>
                        {item.total_topics > 0 && (
                          <>
                            <span>·</span>
                            <span className="history-topics">
                              {item.total_topics} {kind === 'keyword' ? m.videoUnit : m.ideaUnit}
                            </span>
                          </>
                        )}
                        {isRunning && item.total_sheets > 0 && (
                          <>
                            <span>·</span>
                            <span>{m.doneProgress(item.completed_sheets, item.total_sheets)}</span>
                          </>
                        )}
                      </div>
                      <div className="history-actions">
                        <button
                          type="button"
                          className="ghost small history-view-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectJob(item.id);
                          }}
                        >
                          {isRunning ? m.viewProgress : m.viewResults}
                        </button>
                        {item.id !== tourDemoId && (
                          <button
                            type="button"
                            className="channel-del-btn"
                            aria-label={m.deleteRunAria(cleanTopicTitle(item.filename))}
                            title={m.deleteRunTitle}
                            onClick={(e) => onDeleteJob(item.id, e)}
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
        </>
      ) : (
        <JobResult
          job={activeJob}
          historyCount={items.length}
          copiedKey={copiedKey}
          collapsed={isCollapsed}
          onToggleCollapse={toggleCollapsed}
          onBack={() => onSelectJob(null)}
          onCopyTopic={onCopyTopic}
          onAddCreator={onAddCreator}
          onSaveVideo={onSaveVideo}
        />
      )}
    </section>
  );
};

export const AnalyzerTab: React.FC<AnalyzerTabProps> = ({
  onSearchKeyword,
  onSearchKeywords,
  blocked,
  error,
  starting,
  jobId,
  job,
  visibleHistory,
  loadingHistory,
  onFetchHistory,
  onSelectJob,
  onDeleteJob,
  tourDemoId,
  copiedKey,
  onCopyTopic,
  onAddCreator,
  onSaveVideo,
  onGoToLibrary,
  forceHistoryView = false,
}) => {
  const { t } = useLocale();
  const m = t.analyzer;
  const [activeView, setActiveView] = useState<'chat' | 'history'>(() => (jobId || starting ? 'history' : 'chat'));
  const showHistory = forceHistoryView || activeView === 'history' || starting || Boolean(jobId);
  const [brandCollapsed, setBrandCollapsed] = useState(() => readCollapsed(BRAND_COLLAPSED_KEY));
  const [highlightBrand, setHighlightBrand] = useState(false);
  const highlightTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!highlightBrand || starting || (jobId && !job)) return;
    document.getElementById('results-brand')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [highlightBrand, starting, jobId, job]);

  const toggleBrandCollapsed = () => {
    setBrandCollapsed((prev) => {
      const next = !prev;
      try {
        if (next) {
          localStorage.setItem(BRAND_COLLAPSED_KEY, '1');
        } else {
          localStorage.removeItem(BRAND_COLLAPSED_KEY);
        }
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  const focusBrandResults = () => {
    setActiveView('history');
    setBrandCollapsed(false);
    try {
      localStorage.removeItem(BRAND_COLLAPSED_KEY);
    } catch {
      // ignore storage errors
    }
    setHighlightBrand(true);
    if (highlightTimerRef.current !== null) {
      window.clearTimeout(highlightTimerRef.current);
    }
    highlightTimerRef.current = window.setTimeout(() => {
      setHighlightBrand(false);
      highlightTimerRef.current = null;
    }, 2200);
  };

  const brandHistory = visibleHistory.filter((item) => item.job_kind === 'keyword');
  const analysisHistory = visibleHistory.filter((item) => item.job_kind !== 'keyword');
  const activeIsBrand = job?.job_kind === 'keyword';

  return (
    <>
      <BrandAssistant
        onSearchKeyword={(kw) => {
          focusBrandResults();
          onSearchKeyword(kw);
        }}
        onSearchKeywords={
          onSearchKeywords
            ? (kws) => {
                focusBrandResults();
                onSearchKeywords(kws);
              }
            : undefined
        }
        blocked={blocked}
        showHistory={showHistory}
        onSelectHistory={() => setActiveView('history')}
        onSelectChat={() => {
          setActiveView('chat');
          if (jobId) onSelectJob(null);
        }}
      />

      {showHistory && (
        <div id="results" style={{ display: 'contents' }}>
          {error && <div className="alert error">{error}</div>}
          {starting ? (
            <section className="panel">
              <div className="empty">
                <p className="muted">{m.creatingJob}</p>
              </div>
            </section>
          ) : jobId && !job ? (
            <section className="panel">
              <div className="empty">
                <p className="muted">{m.loadingResults}</p>
              </div>
            </section>
          ) : (
            <>
              <ResultsSection
                id="results-brand"
                title={m.brandResultsTitle}
                storageKey={BRAND_COLLAPSED_KEY}
                items={brandHistory}
                activeJob={job && activeIsBrand ? job : null}
                emptyText={m.brandResultsEmpty}
                loadingHistory={loadingHistory}
                onFetchHistory={onFetchHistory}
                onSelectJob={onSelectJob}
                onDeleteJob={onDeleteJob}
                tourDemoId={tourDemoId}
                copiedKey={copiedKey}
                onCopyTopic={onCopyTopic}
                onAddCreator={onAddCreator}
                onSaveVideo={onSaveVideo}
                collapsed={brandCollapsed}
                onToggleCollapsed={toggleBrandCollapsed}
                highlighted={highlightBrand}
              />
              <ResultsSection
                id="results-analysis"
                title={m.analysisResultsTitle}
                storageKey={ANALYSIS_COLLAPSED_KEY}
                items={analysisHistory}
                activeJob={job && !activeIsBrand ? job : null}
                emptyText={m.analysisResultsEmpty}
                emptyActionLabel={m.goToLibraryBtn}
                onEmptyAction={onGoToLibrary}
                loadingHistory={loadingHistory}
                onFetchHistory={onFetchHistory}
                onSelectJob={onSelectJob}
                onDeleteJob={onDeleteJob}
                tourDemoId={tourDemoId}
                copiedKey={copiedKey}
                onCopyTopic={onCopyTopic}
                onAddCreator={onAddCreator}
                onSaveVideo={onSaveVideo}
              />
            </>
          )}
        </div>
      )}
    </>
  );
};
