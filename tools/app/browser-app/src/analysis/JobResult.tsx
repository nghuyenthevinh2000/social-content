import { IonIcon } from '@ionic/react';
import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useLocale } from '../locales';

import { KeywordResult } from './KeywordResult';
import { TopicCard } from './TopicCard';
import './analysis.css';
import {
  formatTime,
  getPlatformIcon,
  getTopicReelUrl,
  inferPlatform,
  PLATFORM_LABELS,
  sortPlatformCounts,
  TERMINAL,
} from './format';
import { createRenderers, type JobRenderer } from './renderers';
import type { Job, Sheet, Topic } from './types';

type JobResultProps = {
  job: Job;
  historyCount: number;
  copiedKey: string | null;
  blocked?: boolean;
  onBack: () => void;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onAnalyzeCreators?: (creators: { name: string; url: string; platform?: string }[], sheetName: string) => void;
  onAnalyzeVideo?: (topic: Topic) => void;
};

const SheetSection: React.FC<{
  sheet: Sheet;
  index: number;
  renderer: JobRenderer;
  copiedKey: string | null;
  blocked: boolean;
  isKeyword: boolean;
  showPlatformFilter: boolean;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onAnalyzeCreators?: (creators: { name: string; url: string; platform?: string }[], sheetName: string) => void;
  onAnalyzeVideo?: (topic: Topic) => void;
}> = ({
  sheet,
  index,
  renderer,
  copiedKey,
  blocked,
  isKeyword,
  showPlatformFilter,
  onCopyTopic,
  onAddCreator,
  onAnalyzeCreators,
  onAnalyzeVideo,
}) => {
  const { t } = useLocale();
  const orderedTopics = useMemo(() => renderer.order(sheet.topics), [renderer, sheet.topics]);
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(() => new Set());
  const togglePlatform = (platform: string) => {
    setSelectedPlatforms((prev) => {
      const next = new Set(prev);
      if (next.has(platform)) next.delete(platform);
      else next.add(platform);
      return next;
    });
  };
  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    orderedTopics.forEach((topic) => {
      const p = topic.platform || inferPlatform(topic, getTopicReelUrl(topic)) || 'facebook';
      counts[p] = (counts[p] || 0) + 1;
    });
    return counts;
  }, [orderedTopics]);
  const visibleTopics = useMemo(() => {
    if (selectedPlatforms.size === 0) return orderedTopics;
    return orderedTopics.filter((topic) => {
      const p = topic.platform || inferPlatform(topic, getTopicReelUrl(topic)) || 'facebook';
      return selectedPlatforms.has(p);
    });
  }, [orderedTopics, selectedPlatforms]);

  return (
    <div className="sheet">
      <div className="sheet-head">
        <span className="sheet-index">{String(index + 1).padStart(2, '0')}</span>
        <span className="sheet-title">
          <strong>{renderer.sheetTitle(sheet)}</strong>
          <small className="muted">{renderer.summaryMeta(sheet)}</small>
        </span>
        <span className={`badge ${sheet.status}`}>{sheet.status}</span>
      </div>

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
          blocked={blocked}
          onAddCreator={onAddCreator}
          onAnalyzeCreators={onAnalyzeCreators}
        />
      ) : (
        orderedTopics.length > 0 && (
          <>
            {showPlatformFilter && Object.keys(platformCounts).length > 0 && (
              <div className="source-breakdown muted">
                {sortPlatformCounts(platformCounts).map(([p, c]) => {
                  const active = selectedPlatforms.has(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      className={`platform-filter-btn ${active ? 'active' : ''}`}
                      aria-pressed={active}
                      aria-label={`${p}: ${c}`}
                      title={`${PLATFORM_LABELS[p] || p}: ${c}`}
                      onClick={() => togglePlatform(p)}
                    >
                      <IonIcon icon={getPlatformIcon(p)} aria-hidden="true" />
                      <span>{c}</span>
                    </button>
                  );
                })}
              </div>
            )}
            <div className="topics topics-carousel">
              {visibleTopics.map((topic, topicIndex) => {
                const key = `${sheet.slug}-${topicIndex}`;
                return (
                  <TopicCard
                    key={topicIndex}
                    topic={topic}
                    index={topicIndex}
                    copied={copiedKey === key}
                    blocked={blocked}
                    sections={renderer.sections(topic)}
                    onCopy={() => onCopyTopic(topic, sheet.name, key)}
                    onAnalyzeVideo={onAnalyzeVideo ? () => onAnalyzeVideo(topic) : undefined}
                  />
                );
              })}
            </div>
          </>
        )
      )}
    </div>
  );
};

type RunningStage = 'collect' | 'transcript' | 'acp';

const ACP_STAGE_RE =
  /\bACP\b|harness|Phân tích hình ảnh|Đã phân tích hình ảnh|Đã trích xuất transcript|Không tìm thấy transcript|Hoàn tất:\s*\d+\s*reel/i;
const TRANSCRIPT_STAGE_RE = /transcript|phụ đề|Đang xử lý|Tải video để phân tích|Đang phân tích Reel/i;

function getSheetLogs(sheet: Sheet, job: Job) {
  return job.logs.filter(
    (l) => l.sheet === sheet.name || l.sheet === sheet.slug || (job.sheets.length === 1 && l.sheet !== null),
  );
}

function detectSheetStage(sheet: Sheet, sheetLogs: { message: string }[]): RunningStage {
  if (
    sheet.reels > 0 ||
    (sheet.topics && sheet.topics.length > 0) ||
    (sheet.creators && sheet.creators.length > 0) ||
    sheetLogs.some((l) => ACP_STAGE_RE.test(l.message))
  ) {
    return 'acp';
  }
  if (sheetLogs.some((l) => TRANSCRIPT_STAGE_RE.test(l.message))) {
    return 'transcript';
  }
  return 'collect';
}

function estimateRunningSheetFraction(
  sheet: Sheet,
  job: Job,
  stage: RunningStage,
  sheetLogs: { message: string }[],
  ticksInStage: number,
): number {
  const logCount = sheetLogs.length || job.logs.length;

  if (stage === 'collect') {
    let signal = 0.05 + 0.1 * (1 - Math.exp(-logCount / 6));
    if (sheet.queries && sheet.queries.length > 0) {
      signal = Math.max(signal, 0.14);
    }
    return Math.min(0.2, signal + (0.2 - signal) * (1 - Math.exp(-ticksInStage / 18)));
  }

  if (stage === 'transcript') {
    const trLogs = sheetLogs.filter((l) => TRANSCRIPT_STAGE_RE.test(l.message));
    let ratioSignal = 0;
    for (let i = trLogs.length - 1; i >= 0; i -= 1) {
      const m = trLogs[i].message.match(/(\d+)\s*\/\s*(\d+)/);
      if (m) {
        const idx = Number(m[1]);
        const total = Number(m[2]);
        if (total > 0) {
          ratioSignal = 0.2 + 0.26 * Math.min(1, idx / total);
          break;
        }
      }
    }
    const logSignal = Math.max(0.22 + 0.22 * (1 - Math.exp(-trLogs.length / 4)), ratioSignal);
    return Math.min(0.55, logSignal + (0.55 - logSignal) * (1 - Math.exp(-ticksInStage / 30)));
  }

  const acpLogs = sheetLogs.filter((l) =>
    /\bACP\b|harness|Phân tích hình ảnh|Đã phân tích hình ảnh|Agent đã trả về/i.test(l.message),
  );
  let signal = 0.55 + 0.22 * (1 - Math.exp(-acpLogs.length / 3));
  if ((sheet.topics && sheet.topics.length > 0) || (sheet.creators && sheet.creators.length > 0)) {
    signal = Math.max(signal, 0.88);
  }
  return Math.min(0.95, signal + (0.95 - signal) * (1 - Math.exp(-ticksInStage / 35)));
}

export const JobResult: React.FC<JobResultProps> = ({
  job,
  historyCount,
  copiedKey,
  blocked = false,
  onBack,
  onCopyTopic,
  onAddCreator,
  onAnalyzeCreators,
  onAnalyzeVideo,
}) => {
  const { t } = useLocale();
  const m = t.analysis;
  const [showLogs, setShowLogs] = useState(false);
  const isRunning = !TERMINAL.has(job.status);
  const [tick, setTick] = useState(0);
  const maxPctRef = useRef<{ id: string; pct: number }>({ id: job.id, pct: 0 });
  const stageStartRef = useRef<{ key: string; tick: number }>({ key: '', tick: 0 });
  const renderers = useMemo(() => createRenderers(m), [m]);
  const renderer = renderers[job.job_kind ?? 'profile'] ?? renderers.profile;
  const isKeyword = job.job_kind === 'keyword';

  useEffect(() => {
    setTick(0);
    stageStartRef.current = { key: '', tick: 0 };
    if (!isRunning) return;
    const timer = window.setInterval(() => setTick((prev) => prev + 1), 1000);
    return () => window.clearInterval(timer);
  }, [job.id, isRunning]);
  const progress = useMemo(() => {
    const total = job.sheets.length;
    const done = job.sheets.filter((sheet) => TERMINAL.has(sheet.status)).length;
    if (!total) return { done: 0, total: 0, pct: 0 };
    if (!isRunning) {
      return { done, total, pct: Math.round((done / total) * 100) };
    }

    let hasActiveSheet = false;
    const earned = job.sheets.reduce((acc, sheet) => {
      if (TERMINAL.has(sheet.status)) {
        hasActiveSheet = true;
        return acc + 1;
      }
      if (sheet.status === 'running' || job.current_sheet === sheet.name) {
        hasActiveSheet = true;
        const sheetLogs = getSheetLogs(sheet, job);
        const stage = detectSheetStage(sheet, sheetLogs);
        const stageKey = `${job.id}:${sheet.slug}:${stage}`;
        if (stageStartRef.current.key !== stageKey) {
          stageStartRef.current = { key: stageKey, tick };
        }
        const ticksInStage = Math.max(0, tick - stageStartRef.current.tick);
        return acc + estimateRunningSheetFraction(sheet, job, stage, sheetLogs, ticksInStage);
      }
      return acc;
    }, 0);

    const effectiveEarned = hasActiveSheet ? earned : Math.min(0.1, 0.04 + tick * 0.01) * total;
    const rawPct = Math.min(95, Math.max(4, Math.round((effectiveEarned / total) * 100)));

    if (maxPctRef.current.id !== job.id) {
      maxPctRef.current = { id: job.id, pct: rawPct };
    } else if (rawPct > maxPctRef.current.pct) {
      maxPctRef.current.pct = rawPct;
    }

    return { done, total, pct: maxPctRef.current.pct };
  }, [job, isRunning, tick]);

  return (
    <>
      <div className="panel-head">
        <div>
          <button type="button" className="history-back-btn" onClick={onBack}>
            {m.historyBack(historyCount)}
          </button>
          <h2>{m.resultsHeading}</h2>
          {job.created_at && <p className="muted count">{formatTime(job.created_at)}</p>}
        </div>
      </div>

      <div
        className={`bar ${isRunning ? 'running' : ''}`}
        role="progressbar"
        aria-valuenow={progress.pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
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
          renderer={renderer}
          copiedKey={copiedKey}
          blocked={blocked}
          isKeyword={isKeyword}
          showPlatformFilter={!isKeyword && job.job_kind !== 'reel'}
          onCopyTopic={onCopyTopic}
          onAddCreator={onAddCreator}
          onAnalyzeCreators={onAnalyzeCreators}
          onAnalyzeVideo={job.job_kind !== 'reel' ? onAnalyzeVideo : undefined}
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
  );
};
