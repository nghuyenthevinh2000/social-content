import React from 'react';

import type { AnalysisSection } from './TopicCard';
import { formatNumber, getTopicReelUrl } from './format';
import type { JobKind, Sheet, Topic } from './types';

export type JobRenderer = {
  meta: (sheet: Sheet) => React.ReactNode;
  sheetTitle: (sheet: Sheet) => string;
  summaryMeta: (sheet: Sheet) => string;
  runningText: string;
  emptyText: string;
  sections: (topic: Topic) => AnalysisSection[];
  order: (topics: Topic[]) => Topic[];
};

function commonSections(topic: Topic): AnalysisSection[] {
  const sections: AnalysisSection[] = [
    {
      label: '🎙️ Transcript nội dung:',
      body: (
        <p className="transcript-text">
          {topic.transcript && topic.transcript.trim()
            ? topic.transcript
            : 'Không có lời thoại (video dạng nhạc nền / hình ảnh).'}
        </p>
      ),
    },
  ];
  if (topic.why_viral) {
    sections.push({ label: '🔥 Vì sao viral:', body: <p>{topic.why_viral}</p> });
  }
  if (topic.hook) {
    sections.push({ label: '🎣 Hook mở đầu (3s):', body: <p className="hook-quote">“{topic.hook}”</p> });
  }
  if (topic.angle) {
    sections.push({ label: '📐 Góc tiếp cận:', body: <p>{topic.angle}</p> });
  }
  if (topic.outline && topic.outline.length > 0) {
    sections.push({
      label: '📋 Dàn ý triển khai:',
      body: (
        <ol className="analysis-outline">
          {topic.outline.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      ),
    });
  }
  return sections;
}

function renderProfileMeta(sheet: Sheet): React.ReactNode {
  const glasserCount = sheet.source_breakdown?.glasser_api?.length ?? 0;
  const cacheCount = sheet.source_breakdown?.cache?.length ?? 0;
  const poolEntries = Object.entries(sheet.pool_distribution || {});

  return (
    <>
      {poolEntries.length > 0 && (
        <div className="pools">
          {poolEntries.map(([pool, count]) => (
            <span key={pool} className="pool">
              {pool.replace('pool_', 'P')} · {count}
            </span>
          ))}
        </div>
      )}
      {(glasserCount > 0 || cacheCount > 0) && (
        <div className="source-breakdown muted">
          {glasserCount > 0 && (
            <span title={sheet.source_breakdown?.glasser_api?.join(', ')}>⚡ Glasser API: {glasserCount} kênh</span>
          )}
          {glasserCount > 0 && cacheCount > 0 && ' · '}
          {cacheCount > 0 && <span title={sheet.source_breakdown?.cache?.join(', ')}>💾 Cache: {cacheCount} kênh</span>}
        </div>
      )}
    </>
  );
}

export const RENDERERS: Record<JobKind, JobRenderer> = {
  profile: {
    meta: renderProfileMeta,
    sheetTitle: (sheet) => sheet.name,
    summaryMeta: (sheet) => `${sheet.targets} kênh · ${formatNumber(sheet.reels)} reel`,
    runningText: 'Đang crawl, phân pool và hỏi agent…',
    emptyText: 'Không tìm thấy reel mới nào trong 48 giờ qua. Vui lòng cập nhật thêm danh sách kênh.',
    sections: commonSections,
    order: (topics) => [...topics].sort((a, b) => (b.views || 0) - (a.views || 0)).slice(0, 10),
  },
  reel: {
    meta: () => null,
    sheetTitle: (sheet) => {
      const url = sheet.target_list?.[0]?.url || (sheet.topics[0] ? getTopicReelUrl(sheet.topics[0]) : '') || '';
      const match = url.match(/\/(?:reel|videos)\/(\d+)/) || url.match(/\/share\/[rv]\/([^/?#]+)/);
      return sheet.topics[0]?.video_id || match?.[1] || url || sheet.name;
    },
    summaryMeta: (sheet) => `${sheet.targets} reel`,
    runningText: 'Đang tải transcript và phân tích Reel…',
    emptyText: 'Không có kết quả phân tích cho Reel này.',
    sections: (topic) => {
      const base = commonSections(topic);
      if (topic.visual && topic.visual.trim()) {
        return [{ label: '🎬 Hình ảnh / Bối cảnh:', body: <p>{topic.visual}</p> }, ...base];
      }
      return base;
    },
    order: (topics) => topics,
  },
};
