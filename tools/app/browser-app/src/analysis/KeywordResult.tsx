import React, { useState } from 'react';

import { useLocale } from '../locales';

import { ReelPlayerBox } from './TopicCard';
import { formatCompact, formatNumber, getEmbedUrl, getTopicReelUrl, inferPlatform, PLATFORM_LABELS } from './format';
import type { Sheet, Topic } from './types';

type KeywordResultProps = {
  sheet: Sheet;
  orderedTopics: Topic[];
  savedUrls: Set<string>;
  addedCreatorUrls: Set<string>;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo?: (topic: Topic) => void;
};

const KIND_LABELS: Record<string, string> = {
  original: 'Original',
  abbreviation: 'Abbr',
  vi: 'VI',
};

export const KeywordResult: React.FC<KeywordResultProps> = ({
  sheet,
  orderedTopics,
  savedUrls,
  addedCreatorUrls,
  onAddCreator,
  onSaveVideo,
}) => {
  const { t } = useLocale();
  const m = t.analysis;
  const km = m.keywordResult;
  const queries = sheet.queries ?? [];
  const creators = sheet.creators ?? [];
  const counts: Record<string, number> = {};
  sheet.topics.forEach((t) => {
    const p = t.platform || 'facebook';
    counts[p] = (counts[p] || 0) + 1;
  });

  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(() => new Set());
  const togglePlatform = (platform: string) => {
    setSelectedPlatforms((prev) => {
      const next = new Set(prev);
      if (next.has(platform)) next.delete(platform);
      else next.add(platform);
      return next;
    });
  };

  const relevantCreators = creators.filter((c) => (c.relevance || '').toLowerCase() !== 'off_topic');
  const filteredCreators =
    selectedPlatforms.size > 0
      ? relevantCreators.filter((c) => selectedPlatforms.has(c.platform || 'facebook'))
      : relevantCreators;
  const filteredTopics =
    selectedPlatforms.size > 0
      ? orderedTopics.filter((t) => selectedPlatforms.has(t.platform || inferPlatform(t, getTopicReelUrl(t))))
      : orderedTopics;

  const creatorsWithUrl = filteredCreators.filter((c) => !!c.url);
  const allCreatorsAdded =
    creatorsWithUrl.length > 0 && creatorsWithUrl.every((c) => addedCreatorUrls.has(c.url));
  const videosWithUrl = filteredTopics.filter((t) => !!getTopicReelUrl(t));
  const allVideosSaved =
    videosWithUrl.length > 0 && videosWithUrl.every((t) => savedUrls.has(getTopicReelUrl(t)));

  return (
    <div className="keyword-meta">
      {queries.length > 0 && (
        <div className="pools">
          {queries.map((q) => (
            <span key={`${q.kind}:${q.text}`} className="pool">
              {KIND_LABELS[q.kind] || q.kind}: {q.text}
            </span>
          ))}
        </div>
      )}

      {Object.keys(counts).length > 0 && (
        <div className="source-breakdown muted">
          {Object.entries(counts).map(([p, c]) => {
            const active = selectedPlatforms.has(p);
            return (
              <button
                key={p}
                type="button"
                className={`platform-filter-btn ${active ? 'active' : ''}`}
                aria-pressed={active}
                onClick={() => togglePlatform(p)}
              >
                {p}: {c}
              </button>
            );
          })}
        </div>
      )}

      {filteredCreators.length > 0 && (
        <details className="sheet keyword-subpanel">
          <summary>
            <span className="sheet-title">
              <strong>{km.creatorsHeading}</strong>
              <small className="muted">{km.creatorsCount(filteredCreators.length)}</small>
            </span>
            {onAddCreator && creatorsWithUrl.length > 0 && (
              <button
                type="button"
                className={`ghost small ${allCreatorsAdded ? 'copied' : ''}`}
                aria-label={allCreatorsAdded ? km.addedAllCreatorsAria : km.addAllCreatorsAria}
                title={km.addAllCreatorsTitle}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  creatorsWithUrl.forEach((c) => {
                    if (!addedCreatorUrls.has(c.url)) {
                      onAddCreator({ name: c.name || c.handle, url: c.url, platform: c.platform });
                    }
                  });
                }}
              >
                {allCreatorsAdded ? '✓' : '+'}
              </button>
            )}
          </summary>
          <div className="creator-list">
            {filteredCreators.map((c) => (
              <div key={c.url || `${c.platform}:${c.handle}`} className="creator-row">
                <div className="creator-row-main">
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noreferrer" className="creator-link creator-name">
                      {c.name || `@${c.handle}`} ↗
                    </a>
                  ) : (
                    <span className="creator-name">{c.name || `@${c.handle}`}</span>
                  )}
                  <span className="pool">{c.platform}</span>
                </div>
                <div className="creator-row-meta">
                  <span className="muted">
                    {c.followers && c.followers > 0 ? km.followers(formatCompact(c.followers)) : '—'}
                  </span>
                  <button
                    type="button"
                    className={`ghost small ${c.url && addedCreatorUrls.has(c.url) ? 'copied' : ''}`}
                    aria-label={c.url && addedCreatorUrls.has(c.url) ? km.addedCreatorAria : km.addCreatorAria}
                    title={
                      !c.url
                        ? km.noCreatorUrlTitle
                        : addedCreatorUrls.has(c.url)
                          ? km.addedCreatorTitle
                          : km.addCreatorTitle
                    }
                    disabled={!onAddCreator || !c.url}
                    onClick={() =>
                      c.url && onAddCreator?.({ name: c.name || c.handle, url: c.url, platform: c.platform })
                    }
                  >
                    {c.url && addedCreatorUrls.has(c.url) ? '✓' : '+'}
                  </button>
                </div>
                {c.why_relevant && <div className="creator-why muted">{c.why_relevant}</div>}
              </div>
            ))}
          </div>
        </details>
      )}

      {filteredTopics.length > 0 && (
        <details className="sheet keyword-subpanel">
          <summary>
            <span className="sheet-title">
              <strong>{km.videosHeading}</strong>
              <small className="muted">{km.videosSwipeHint(filteredTopics.length)}</small>
            </span>
            {onSaveVideo && videosWithUrl.length > 0 && (
              <button
                type="button"
                className={`ghost small ${allVideosSaved ? 'copied' : ''}`}
                aria-label={allVideosSaved ? km.savedAllVideosAria : km.saveAllVideosAria}
                title={km.saveAllVideosTitle}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  videosWithUrl.forEach((t) => {
                    const u = getTopicReelUrl(t);
                    if (u && !savedUrls.has(u)) {
                      onSaveVideo(t);
                    }
                  });
                }}
              >
                {allVideosSaved ? '✓' : '+'}
              </button>
            )}
          </summary>
          <div className="topics topics-carousel">
            {filteredTopics.map((topic, idx) => {
              const reelUrl = getTopicReelUrl(topic);
              const platform = inferPlatform(topic, reelUrl);
              const platformLabel = PLATFORM_LABELS[platform] || 'Facebook';
              const embedUrl = getEmbedUrl(reelUrl, platform);
              const isSaved = !!reelUrl && savedUrls.has(reelUrl);

              return (
                <article key={idx} className="topic reel-card">
                  <div className="topic-top">
                    <div className="reel-meta-left">
                      <span className="topic-num">#{idx + 1}</span>
                      {(topic.author_handle || topic.author_name) && (
                        <span className="reel-author">@{topic.author_handle || topic.author_name}</span>
                      )}
                    </div>
                    <span className="source-tag glasser">{platformLabel}</span>
                  </div>

                  <h3 className="reel-title">{topic.title}</h3>

                  <div className="reel-badges">
                    {typeof topic.views === 'number' && topic.views > 0 && (
                      <span className="metric-badge views" title={m.viewsTitle(formatNumber(topic.views))}>
                        🔥 {m.viewsShort(formatCompact(topic.views))}
                      </span>
                    )}
                    {topic.matched_query && (
                      <span className="metric-badge" title={m.matchedQueryTitle}>
                        🔎 {topic.matched_query}
                      </span>
                    )}
                  </div>

                  <ReelPlayerBox
                    videoUrl={topic.video_url}
                    embedUrl={embedUrl}
                    title={topic.title || `Video ${idx + 1}`}
                  />

                  <div className="reel-card-foot">
                    <div className="reel-card-foot-left">
                      {reelUrl && (
                        <a href={reelUrl} target="_blank" rel="noreferrer" className="reel-ext-link">
                          {platformLabel} ↗
                        </a>
                      )}
                      {onSaveVideo && reelUrl && (
                        <button
                          type="button"
                          className={`ghost small ${isSaved ? 'copied' : ''}`}
                          onClick={() => onSaveVideo(topic)}
                        >
                          {isSaved ? km.savedVideoBtn : km.saveVideoBtn}
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </details>
      )}
    </div>
  );
};
