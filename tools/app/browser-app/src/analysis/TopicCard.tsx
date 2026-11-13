import React, { useState } from 'react';

import { formatCompact, formatNumber, getTopicReelUrl } from './format';
import type { Topic } from './types';

export type AnalysisSection = {
  label: string;
  body: React.ReactNode;
};

type TopicCardProps = {
  topic: Topic;
  index: number;
  copied: boolean;
  sections: AnalysisSection[];
  onCopy: () => void;
};

export const TopicCard: React.FC<TopicCardProps> = ({ topic, index, copied, sections, onCopy }) => {
  const reelUrl = getTopicReelUrl(topic);
  const [mode, setMode] = useState<'video' | 'iframe'>(topic.video_url ? 'video' : 'iframe');

  return (
    <article className="topic reel-card">
      <div className="topic-top">
        <div className="reel-meta-left">
          <span className="topic-num">#{index + 1}</span>
          {topic.author_handle && <span className="reel-author">@{topic.author_handle}</span>}
        </div>
        <span className={`source-tag ${topic.generated_by}`}>
          {topic.generated_by === 'agent' ? 'agent' : 'dự phòng'}
        </span>
      </div>

      <h3 className="reel-title">{topic.title}</h3>

      <div className="reel-badges">
        {typeof topic.views === 'number' && topic.views > 0 && (
          <span className="metric-badge views" title={`${formatNumber(topic.views)} lượt xem`}>
            🔥 {formatCompact(topic.views)} views
          </span>
        )}
        {typeof topic.velocity_per_hour === 'number' && topic.velocity_per_hour > 0 && (
          <span className="metric-badge velocity" title={`${formatNumber(topic.velocity_per_hour)} lượt xem/giờ`}>
            ⚡ {formatCompact(topic.velocity_per_hour)}/h
          </span>
        )}
      </div>

      <div className="reel-player-box">
        {mode === 'video' && topic.video_url ? (
          <video
            src={topic.video_url}
            controls
            playsInline
            preload="metadata"
            className="reel-video-player"
            onError={() => {
              if (reelUrl) setMode('iframe');
            }}
          />
        ) : reelUrl ? (
          <iframe
            src={`https://www.facebook.com/plugins/video.php?href=${encodeURIComponent(reelUrl)}&show_text=0&width=280`}
            title={topic.title || `Reel ${index + 1}`}
            className="reel-iframe-player"
            scrolling="no"
            frameBorder="0"
            allowFullScreen={true}
            allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"
            loading="lazy"
          />
        ) : (
          <div className="reel-player-placeholder">
            <span>Không có link video</span>
          </div>
        )}
      </div>

      <details className="reel-analysis-details">
        <summary className="reel-analysis-summary">
          <span>💡 Transcript nội dung & Phân tích viral</span>
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

      <div className="reel-card-foot">
        <div className="reel-card-foot-left">
          {reelUrl && (
            <a href={reelUrl} target="_blank" rel="noreferrer" className="reel-ext-link">
              Facebook ↗
            </a>
          )}
        </div>
        <button
          type="button"
          className={`copy-topic-btn ${copied ? 'copied' : ''}`}
          onClick={onCopy}
          title="Sao chép kịch bản và mở tab Tạo Video"
        >
          {copied ? (
            <>✓ Đã chép</>
          ) : (
            <>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              Copy cho AI
            </>
          )}
        </button>
      </div>
    </article>
  );
};
