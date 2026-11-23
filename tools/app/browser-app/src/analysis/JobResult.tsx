import React, { useMemo, useState } from 'react';

import { useLocale } from '../locales';

import { KeywordResult } from './KeywordResult';
import { TopicCard } from './TopicCard';
import './analysis.css';
import { formatTime, TERMINAL } from './format';
import { createRenderers, type JobRenderer } from './renderers';
import type { Job, Sheet, Topic } from './types';

type JobResultProps = {
  job: Job;
  historyCount: number;
  copiedKey: string | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onBack: () => void;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo?: (topic: Topic) => void;
};

const SheetSection: React.FC<{
  sheet: Sheet;
  index: number;
  totalSheets: number;
  renderer: JobRenderer;
  copiedKey: string | null;
  isKeyword: boolean;
  addedCreatorUrls: Set<string>;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
}> = ({
  sheet,
  index,
  totalSheets,
  renderer,
  copiedKey,
  isKeyword,
  addedCreatorUrls,
  onCopyTopic,
  onAddCreator,
}) => {
  const { t } = useLocale();
  const orderedTopics = useMemo(() => renderer.order(sheet.topics), [renderer, sheet.topics]);

  return (
    <details className="sheet" open={sheet.status === 'running' || totalSheets === 1 ? true : undefined}>
      <summary>
        <span className="sheet-index">{String(index + 1).padStart(2, '0')}</span>
        <span className="sheet-title">
          <strong>{renderer.sheetTitle(sheet)}</strong>
          <small className="muted">{renderer.summaryMeta(sheet)}</small>
        </span>
        <span className={`badge ${sheet.status}`}>{sheet.status}</span>
      </summary>

      {!isKeyword && renderer.meta(sheet)}
      {sheet.error && <div className="alert error">{sheet.error}</div>}
      {sheet.notice && <div className="alert warn">{sheet.notice}</div>}
      {sheet.status === 'completed' && sheet.reels === 0 && !sheet.error && !sheet.notice && (
        <div className="alert warn">{renderer.emptyText}</div>
      )}
      {sheet.status === 'pending' && <p className="muted">{t.analysis.waitingTurn}</p>}
      {sheet.status === 'running' && <p className="muted">{renderer.runningText}</p>}

      {isKeyword ? (
        <KeywordResult
          sheet={sheet}
          addedCreatorUrls={addedCreatorUrls}
          onAddCreator={onAddCreator}
        />
      ) : (
        orderedTopics.length > 0 && (
          <div className="topics topics-carousel">
            {orderedTopics.map((topic, topicIndex) => {
              const key = `${sheet.slug}-${topicIndex}`;
              return (
                <TopicCard
                  key={topicIndex}
                  topic={topic}
                  index={topicIndex}
                  copied={copiedKey === key}
                  sections={renderer.sections(topic)}
                  onCopy={() => onCopyTopic(topic, sheet.name, key)}
                />
              );
            })}
          </div>
        )
      )}
    </details>
  );
};

export const JobResult: React.FC<JobResultProps> = ({
  job,
  historyCount,
  copiedKey,
  collapsed = false,
  onToggleCollapse,
  onBack,
  onCopyTopic,
  onAddCreator,
}) => {
  const { t } = useLocale();
  const m = t.analysis;
  const [showLogs, setShowLogs] = useState(false);
  const [addedCreatorUrls, setAddedCreatorUrls] = useState<Set<string>>(() => new Set());
  const renderers = useMemo(() => createRenderers(m), [m]);
  const renderer = renderers[job.job_kind ?? 'profile'] ?? renderers.profile;
  const isKeyword = job.job_kind === 'keyword';

  const handleAddCreator = onAddCreator
    ? (creator: { name: string; url: string; platform?: string }) => {
        if (creator.url) {
          setAddedCreatorUrls((prev) => new Set(prev).add(creator.url));
        }
        onAddCreator(creator);
      }
    : undefined;
  const progress = useMemo(() => {
    const done = job.sheets.filter((sheet) => TERMINAL.has(sheet.status)).length;
    const total = job.sheets.length;
    return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
  }, [job]);

  return (
    <>
      <div className={`panel-head${onToggleCollapse ? ' collapsible-head' : ''}`} onClick={onToggleCollapse}>
        <div>
          <button
            type="button"
            className="history-back-btn"
            onClick={(e) => {
              e.stopPropagation();
              onBack();
            }}
          >
            {m.historyBack(historyCount)}
          </button>
          <h2>{m.resultsHeading}</h2>
          {job.created_at && <p className="muted count">{formatTime(job.created_at)}</p>}
        </div>
        {onToggleCollapse && (
          <button
            type="button"
            className="panel-collapse-btn"
            aria-expanded={!collapsed}
            aria-label={collapsed ? m.expandResultsAria : m.collapseResultsAria}
            onClick={(e) => {
              e.stopPropagation();
              onToggleCollapse();
            }}
          >
            <span className={`store-toggle-icon ${!collapsed ? 'open' : ''}`} aria-hidden="true" />
          </button>
        )}
      </div>

      {!collapsed && (
        <>
          <div className="bar">
            <span style={{ width: `${progress.pct}%` }} />
          </div>
          <div className="progress-meta muted">
            <span>{progress.pct}%</span>
            <span>{job.current_sheet ? m.processingSheet(job.current_sheet) : ''}</span>
          </div>

          {job.sheets.map((sheet, index) => (
            <SheetSection
              key={sheet.slug}
              sheet={sheet}
              index={index}
              totalSheets={job.sheets.length}
              renderer={renderer}
              copiedKey={copiedKey}
              isKeyword={isKeyword}
              addedCreatorUrls={addedCreatorUrls}
              onCopyTopic={onCopyTopic}
              onAddCreator={handleAddCreator}
            />
          ))}

          <button className="ghost logs-toggle" type="button" onClick={() => setShowLogs((v) => !v)}>
            {showLogs ? m.hideLogs : m.showLogs(job.logs.length)}
          </button>
          {showLogs && (
            <pre className="logs">
              {job.logs
                .slice(-120)
                .map((e) => `${e.at.slice(11, 19)} ${e.sheet ? `[${e.sheet}] ` : ''}${e.message}`)
                .join('\n')}
            </pre>
          )}
        </>
      )}
    </>
  );
};
