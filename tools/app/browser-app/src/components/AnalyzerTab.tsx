import React, { useEffect, useRef, useState } from 'react';

import { JobResult } from '../analysis/JobResult';
import { cleanTopicTitle, formatTime, TERMINAL } from '../analysis/format';
import type { Job, JobKind, JobSummary, Topic } from '../analysis/types';
import { useLocale } from '../locales';

import { BrandAssistant } from './BrandAssistant';

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
  onSelectJob: (id: string | null) => void;
  onDeleteJob: (id: string, e: React.MouseEvent) => void;
  tourDemoId: string;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator: (creator: { name: string; url: string; platform?: string }) => void;
  onAnalyzeCreators?: (creators: { name: string; url: string; platform?: string }[], sheetName: string) => void;
  onAnalyzeVideo?: (topic: Topic) => void;
  onGoToLibrary: () => void;
  forceView?: 'chat' | 'history' | null;
};

type ResultsSectionProps = {
  id: string;
  title: string;
  items: JobSummary[];
  activeJob: Job | null;
  blocked: boolean;
  emptyText: string;
  emptyActionLabel?: string;
  onEmptyAction?: () => void;
  onSelectJob: (id: string | null) => void;
  onDeleteJob: (id: string, e: React.MouseEvent) => void;
  tourDemoId: string;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator: (creator: { name: string; url: string; platform?: string }) => void;
  onAnalyzeCreators?: (creators: { name: string; url: string; platform?: string }[], sheetName: string) => void;
  onAnalyzeVideo?: (topic: Topic) => void;
  highlighted?: boolean;
};

const JOB_KINDS: JobKind[] = ['keyword', 'profile', 'reel'];

const ResultsSection: React.FC<ResultsSectionProps> = ({
  id,
  title,
  items,
  activeJob,
  blocked,
  emptyText,
  emptyActionLabel,
  onEmptyAction,
  onSelectJob,
  onDeleteJob,
  tourDemoId,
  copiedKey,
  onCopyTopic,
  onAddCreator,
  onAnalyzeCreators,
  onAnalyzeVideo,
  highlighted = false,
}) => {
  const { t } = useLocale();
  const m = t.analyzer;
  const [filterKind, setFilterKind] = useState<'all' | JobKind>('all');
  const filteredItems =
    filterKind === 'all' ? items : items.filter((item) => (item.job_kind ?? 'profile') === filterKind);

  return (
    <section className={`panel results-section ${highlighted ? 'results-highlight' : ''}`} id={id}>
      {!activeJob ? (
        items.length === 0 ? (
          <div className="empty">
            <p className="muted">{emptyText}</p>
            {emptyActionLabel && onEmptyAction && (
              <button type="button" className="ghost" onClick={onEmptyAction}>
                {emptyActionLabel}
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="source-breakdown" role="group" aria-label={title}>
              {JOB_KINDS.map((kind) => {
                const count = items.filter((item) => (item.job_kind ?? 'profile') === kind).length;
                const active = filterKind === kind;
                return (
                  <button
                    key={kind}
                    type="button"
                    className={`platform-filter-btn ${active ? 'active' : ''}`}
                    aria-pressed={active}
                    onClick={() => setFilterKind(active ? 'all' : kind)}
                  >
                    {m.kindLabel[kind]} ({count})
                  </button>
                );
              })}
            </div>
            {filteredItems.length === 0 ? (
              <p className="muted empty">{m.historyFilteredEmpty}</p>
            ) : (
              <div className="history-list">
                {filteredItems.map((item) => {
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
                        {item.id !== tourDemoId && !item.id.startsWith('__tour_demo__') && (
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
            )}
          </>
        )
      ) : (
        <JobResult
          job={activeJob}
          historyCount={items.length}
          copiedKey={copiedKey}
          blocked={blocked}
          onBack={() => onSelectJob(null)}
          onCopyTopic={onCopyTopic}
          onAddCreator={onAddCreator}
          onAnalyzeCreators={onAnalyzeCreators}
          onAnalyzeVideo={onAnalyzeVideo}
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
  onSelectJob,
  onDeleteJob,
  tourDemoId,
  copiedKey,
  onCopyTopic,
  onAddCreator,
  onAnalyzeCreators,
  onAnalyzeVideo,
  onGoToLibrary,
  forceView = null,
}) => {
  const { t } = useLocale();
  const m = t.analyzer;
  const [activeView, setActiveView] = useState<'chat' | 'history'>(() => (jobId || starting ? 'history' : 'chat'));
  const showHistory =
    forceView === 'chat' ? false : forceView === 'history' || activeView === 'history' || starting || Boolean(jobId);
  const [highlightResults, setHighlightResults] = useState(false);
  const highlightTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!highlightResults || starting || (jobId && !job)) return;
    document.getElementById('results-analysis')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [highlightResults, starting, jobId, job]);

  const focusBrandResults = () => {
    setActiveView('history');
    setHighlightResults(true);
    if (highlightTimerRef.current !== null) {
      window.clearTimeout(highlightTimerRef.current);
    }
    highlightTimerRef.current = window.setTimeout(() => {
      setHighlightResults(false);
      highlightTimerRef.current = null;
    }, 2200);
  };

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
                id="results-analysis"
                title={m.brandAssistant.historyTab}
                items={visibleHistory}
                activeJob={job}
                blocked={blocked}
                emptyText={m.historyEmpty}
                emptyActionLabel={m.goToLibraryBtn}
                onEmptyAction={onGoToLibrary}
                onSelectJob={onSelectJob}
                onDeleteJob={onDeleteJob}
                tourDemoId={tourDemoId}
                copiedKey={copiedKey}
                onCopyTopic={onCopyTopic}
                onAddCreator={onAddCreator}
                onAnalyzeCreators={onAnalyzeCreators}
                onAnalyzeVideo={onAnalyzeVideo}
                highlighted={highlightResults}
              />
            </>
          )}
        </div>
      )}
    </>
  );
};
