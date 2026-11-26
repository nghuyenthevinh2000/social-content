import React, { useState } from 'react';

import { useLocale } from '../locales';

import { formatCompact, formatNumber, getEmbedUrl, getTopicReelUrl, inferPlatform, PLATFORM_LABELS } from './format';
import type { Topic } from './types';

export type AnalysisSection = {
  label: string;
  body: React.ReactNode;
};

type TopicCardProps = {
  topic: Topic;
  index: number;
  copied: boolean;
  copiedEdit?: boolean;
  blocked?: boolean;
  sections: AnalysisSection[];
  onCopy: () => void;
  onCopyEdit?: () => void;
  onAnalyzeVideo?: () => void;
};

export const ReelPlayerBox: React.FC<{
  videoUrl?: string;
  embedUrl: string | null;
  title: string;
}> = ({ videoUrl, embedUrl, title }) => {
  const [mode, setMode] = useState<'video' | 'iframe'>(videoUrl ? 'video' : 'iframe');

  if (!videoUrl && !embedUrl) return null;

  return (
    <div className="reel-player-box">
      {mode === 'video' && videoUrl ? (
        <video
          src={videoUrl}
          controls
          playsInline
          preload="metadata"
          className="reel-video-player"
          onError={() => {
            if (embedUrl) setMode('iframe');
          }}
        />
      ) : embedUrl ? (
        <iframe
          src={embedUrl}
          title={title}
          className="reel-iframe-player"
          scrolling="no"
          frameBorder="0"
          allowFullScreen={true}
          allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"
          loading="lazy"
        />
      ) : null}
    </div>
  );
};

export const TopicCard: React.FC<TopicCardProps> = ({
  topic,
  index,
  copied,
  copiedEdit = false,
  blocked = false,
  sections,
  onCopy,
  onCopyEdit,
  onAnalyzeVideo,
}) => {
  const { t } = useLocale();
  const m = t.analysis;
  const reelUrl = getTopicReelUrl(topic);
  const platform = inferPlatform(topic, reelUrl);
  const platformLabel = PLATFORM_LABELS[platform] || 'Facebook';
  const embedUrl = getEmbedUrl(reelUrl, platform);

  return (
    <article className="topic reel-card">
      <div className="topic-top">
        <div className="reel-meta-left">
          <span className="topic-num">#{index + 1}</span>
          {(topic.author_handle || topic.author_name) && (
            <span className="reel-author">@{topic.author_handle || topic.author_name}</span>
          )}
        </div>
        <span className={`source-tag ${topic.generated_by}`}>
          {topic.platform ? platformLabel : topic.generated_by === 'agent' ? 'agent' : m.backupTag}
        </span>
      </div>

      <h3 className="reel-title">{topic.title}</h3>

      <div className="reel-badges">
        {typeof topic.views === 'number' && topic.views > 0 && (
          <span className="metric-badge views" title={m.viewsTitle(formatNumber(topic.views))}>
            🔥 {m.viewsShort(formatCompact(topic.views))}
          </span>
        )}
        {typeof topic.velocity_per_hour === 'number' && topic.velocity_per_hour > 0 && (
          <span className="metric-badge velocity" title={m.velocityTitle(formatNumber(topic.velocity_per_hour))}>
            ⚡ {formatCompact(topic.velocity_per_hour)}/h
          </span>
        )}
        {topic.matched_query && (
          <span className="metric-badge" title={m.matchedQueryTitle}>
            🔎 {topic.matched_query}
          </span>
        )}
      </div>

      <ReelPlayerBox videoUrl={topic.video_url} embedUrl={embedUrl} title={topic.title || `Reel ${index + 1}`} />

      {sections.length > 0 && (
        <details className="reel-analysis-details">
          <summary className="reel-analysis-summary">
            <span>{m.transcriptAndViralSummary}</span>
          </summary>
          <div className="reel-analysis-content">
            {sections.map((sec) => (
              <div className="analysis-item" key={sec.label}>
                <strong>{sec.label}</strong>
                {sec.body}
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="reel-card-foot">
        <div className="reel-card-foot-left">
          {reelUrl && (
            <a href={reelUrl} target="_blank" rel="noreferrer" className="reel-ext-link">
              {platformLabel} ↗
            </a>
          )}
        </div>
        {onAnalyzeVideo && reelUrl && (
          <button
            type="button"
            className="topic-run-btn"
            disabled={blocked}
            onClick={onAnalyzeVideo}
            aria-label={m.analyzeVideoBtn}
            title={m.analyzeVideoTitle}
          >
            ▶
          </button>
        )}
        {onCopyEdit && (reelUrl || topic.video_url) && (
          <button
            type="button"
            className={`copy-edit-btn ${copiedEdit ? 'copied' : ''}`}
            onClick={onCopyEdit}
            title={m.copyEditTitle}
          >
            {copiedEdit ? m.copiedEditBtn : m.copyEdit}
          </button>
        )}
        {sections.length > 0 && (
          <button
            type="button"
            className={`copy-topic-btn ${copied ? 'copied' : ''}`}
            onClick={onCopy}
            title={m.copyBtnTitle}
          >
            {copied ? m.copiedBtn : m.copyForAI}
          </button>
        )}
      </div>
    </article>
  );
};
