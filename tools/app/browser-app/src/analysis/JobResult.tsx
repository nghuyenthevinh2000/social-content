import React, { useMemo, useState } from 'react';

import { TopicCard } from './TopicCard';
import './analysis.css';
import { cleanTopicTitle, formatTime, STATUS_LABEL, TERMINAL } from './format';
import { type JobRenderer, RENDERERS } from './renderers';
import type { Job, Sheet, Topic } from './types';

type JobResultProps = {
  job: Job;
  historyCount: number;
  copiedKey: string | null;
  onBack: () => void;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
};

const SheetSection: React.FC<{
  sheet: Sheet;
  index: number;
  totalSheets: number;
  renderer: JobRenderer;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
}> = ({ sheet, index, totalSheets, renderer, copiedKey, onCopyTopic }) => {
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

      {renderer.meta(sheet)}
      {sheet.error && <div className="alert error">{sheet.error}</div>}
      {sheet.notice && <div className="alert warn">{sheet.notice}</div>}
      {sheet.status === 'completed' && sheet.reels === 0 && !sheet.error && !sheet.notice && (
        <div className="alert warn">{renderer.emptyText}</div>
      )}
      {sheet.status === 'pending' && <p className="muted">Đang chờ tới lượt…</p>}
      {sheet.status === 'running' && <p className="muted">{renderer.runningText}</p>}

      {orderedTopics.length > 0 && (
        <div className="topics">
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
      )}
    </details>
  );
};

export const JobResult: React.FC<JobResultProps> = ({ job, historyCount, copiedKey, onBack, onCopyTopic }) => {
  const [showLogs, setShowLogs] = useState(false);
  const renderer = RENDERERS[job.job_kind ?? 'profile'] ?? RENDERERS.profile;
  const progress = useMemo(() => {
    const done = job.sheets.filter((sheet) => TERMINAL.has(sheet.status)).length;
    const total = job.sheets.length;
    return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
  }, [job]);

  return (
    <>
      <div className="panel-head">
        <div>
          <button type="button" className="history-back-btn" onClick={onBack}>
            ← Lịch sử chạy ({historyCount})
          </button>
          <h2>Kết quả</h2>
          <p className="muted count">
            {cleanTopicTitle(job.filename)} · {progress.done}/{progress.total} · {STATUS_LABEL[job.status]}
            {job.created_at && ` · ${formatTime(job.created_at)}`}
          </p>
        </div>
      </div>

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
          onCopyTopic={onCopyTopic}
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
  );
};
