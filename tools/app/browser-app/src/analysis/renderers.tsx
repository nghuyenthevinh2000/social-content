import React from 'react';

import type { LocaleMessages } from '../locales';

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

function commonSections(topic: Topic, m: LocaleMessages['analysis']): AnalysisSection[] {
  const sections: AnalysisSection[] = [
    {
      label: m.transcriptLabel,
      body: (
        <p className="transcript-text">
          {topic.transcript && topic.transcript.trim() ? topic.transcript : m.noTranscript}
        </p>
      ),
    },
  ];
  if (topic.why_viral) {
    sections.push({ label: m.whyViralLabel, body: <p>{topic.why_viral}</p> });
  }
  if (topic.hook) {
    sections.push({ label: m.hookLabel, body: <p className="hook-quote">“{topic.hook}”</p> });
  }
  if (topic.angle) {
    sections.push({ label: m.angleLabel, body: <p>{topic.angle}</p> });
  }
  if (topic.outline && topic.outline.length > 0) {
    sections.push({
      label: m.outlineLabel,
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

export function createRenderers(m: LocaleMessages['analysis']): Record<JobKind, JobRenderer> {
  return {
    profile: {
      meta: () => null,
      sheetTitle: (sheet) => sheet.name,
      summaryMeta: (sheet) => m.profileSummaryMeta(sheet.targets, formatNumber(sheet.reels)),
      runningText: m.profileRunningText,
      emptyText: m.profileEmptyText,
      sections: () => [],
      order: (topics) => [...topics].sort((a, b) => (b.views || 0) - (a.views || 0)),
    },
    reel: {
      meta: () => null,
      sheetTitle: (sheet) => {
        const url = sheet.target_list?.[0]?.url || (sheet.topics[0] ? getTopicReelUrl(sheet.topics[0]) : '') || '';
        const match = url.match(/\/(?:reel|videos)\/(\d+)/) || url.match(/\/share\/[rv]\/([^/?#]+)/);
        return sheet.topics[0]?.video_id || match?.[1] || url || sheet.name;
      },
      summaryMeta: (sheet) => m.reelSummaryMeta(sheet.targets),
      runningText: m.reelRunningText,
      emptyText: m.reelEmptyText,
      sections: (topic) => commonSections(topic, m),
      order: (topics) => topics,
    },
    keyword: {
      meta: () => null,
      sheetTitle: (sheet) => sheet.name,
      summaryMeta: (sheet) => m.keywordSummaryMeta(sheet.queries?.length || 0, formatNumber(sheet.reels)),
      runningText: m.keywordRunningText,
      emptyText: m.keywordEmptyText,
      sections: () => [],
      order: (topics) => [...topics].sort((a, b) => (b.views || 0) - (a.views || 0)),
    },
  };
}
