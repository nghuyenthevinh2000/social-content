import React, { useMemo, useState } from 'react';

import { KeywordResult } from './KeywordResult';
import { TopicCard } from './TopicCard';
import './analysis.css';
import { cleanTopicTitle, formatTime, STATUS_LABEL, TERMINAL } from './format';
import { type JobRenderer, RENDERERS } from './renderers';
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
  savedUrls: Set<string>;
  addedCreatorUrls: Set<string>;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo?: (topic: Topic) => void;
}> = ({
  sheet,
  index,
  totalSheets,
  renderer,
  copiedKey,
  isKeyword,
  savedUrls,
  addedCreatorUrls,
  onCopyTopic,
  onAddCreator,
  onSaveVideo,
}) => {
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
      {sheet.status === 'pending' && <p className="muted">Đang chờ tới lượt…</p>}
      {sheet.status === 'running' && <p className="muted">{renderer.runningText}</p>}

      {isKeyword ? (
        <KeywordResult
          sheet={sheet}
          orderedTopics={orderedTopics}
          savedUrls={savedUrls}
          addedCreatorUrls={addedCreatorUrls}
          onAddCreator={onAddCreator}
          onSaveVideo={onSaveVideo}
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
  onSaveVideo,
}) => {
  const [showLogs, setShowLogs] = useState(false);
  const [savedUrls, setSavedUrls] = useState<Set<string>>(() => new Set());
  const [addedCreatorUrls, setAddedCreatorUrls] = useState<Set<string>>(() => new Set());
  const renderer = RENDERERS[job.job_kind ?? 'profile'] ?? RENDERERS.profile;
  const isKeyword = job.job_kind === 'keyword';

  const handleSave = onSaveVideo
    ? (topic: Topic) => {
        const url = topic.reel_url || topic.source_urls?.[0] || '';
        if (url) {
          setSavedUrls((prev) => new Set(prev).add(url));
        }
        onSaveVideo(topic);
      }
    : undefined;

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
            ← Lịch sử chạy ({historyCount})
          </button>
          <h2>Kết quả</h2>
          <p className="muted count">
            {cleanTopicTitle(job.filename)} · {progress.done}/{progress.total} · {STATUS_LABEL[job.status]}
            {job.created_at && ` · ${formatTime(job.created_at)}`}
          </p>
        </div>
        {onToggleCollapse && (
          <button
            type="button"
            className="panel-collapse-btn"
            aria-expanded={!collapsed}
            aria-label={collapsed ? 'Mở rộng kết quả' : 'Thu gọn kết quả'}
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
            <span>{job.current_sheet ? `Đang xử lý: ${job.current_sheet}` : ''}</span>
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
              savedUrls={savedUrls}
              addedCreatorUrls={addedCreatorUrls}
              onCopyTopic={onCopyTopic}
              onAddCreator={handleAddCreator}
              onSaveVideo={handleSave}
            />
          ))}

          <button className="ghost logs-toggle" type="button" onClick={() => setShowLogs((v) => !v)}>
            {showLogs ? 'Ẩn log' : `Xem log (${job.logs.length})`}
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
