import { IonIcon } from '@ionic/react';
import React, { useState } from 'react';

import { useLocale } from '../locales';

import { formatCompact, getPlatformIcon, PLATFORM_LABELS, sortPlatformCounts } from './format';
import type { Sheet } from './types';

type KeywordResultProps = {
  sheet: Sheet;
  blocked?: boolean;
  onAddCreator?: (creator: { name: string; url: string; platform?: string }) => void;
  onAnalyzeCreators?: (creators: { name: string; url: string; platform?: string }[], sheetName: string) => void;
};

const KIND_LABELS: Record<string, string> = {
  original: 'Original',
  abbreviation: 'Abbr',
  vi: 'VI',
};

export const KeywordResult: React.FC<KeywordResultProps> = ({
  sheet,
  blocked = false,
  onAddCreator,
  onAnalyzeCreators,
}) => {
  const { t } = useLocale();
  const m = t.analysis;
  const km = m.keywordResult;
  const queries = sheet.queries ?? [];
  const creators = sheet.creators ?? [];
  const relevantCreators = creators.filter((c) => (c.relevance || '').toLowerCase() !== 'off_topic');
  const counts: Record<string, number> = {};
  relevantCreators.forEach((c) => {
    const p = c.platform || 'facebook';
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

  const filteredCreators =
    selectedPlatforms.size > 0
      ? relevantCreators.filter((c) => selectedPlatforms.has(c.platform || 'facebook'))
      : relevantCreators;

  const creatorsWithUrl = filteredCreators.filter((c) => !!c.url);

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
          {sortPlatformCounts(counts).map(([p, c]) => {
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

      {filteredCreators.length > 0 && (
        <details className="sheet keyword-subpanel">
          <summary>
            <span className="sheet-title">
              <strong>{km.creatorsHeading}</strong>
              <small className="muted">{km.creatorsCount(filteredCreators.length)}</small>
            </span>
            {onAnalyzeCreators && creatorsWithUrl.length > 0 && (
              <button
                type="button"
                className="topic-run-btn"
                disabled={blocked}
                aria-label={km.analyzeCreatorsAria}
                title={km.analyzeCreatorsTitle}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onAnalyzeCreators(
                    creatorsWithUrl.map((c) => ({
                      name: c.name || c.handle,
                      url: c.url,
                      platform: c.platform,
                    })),
                    sheet.name,
                  );
                }}
              >
                ▶
              </button>
            )}
            {onAddCreator && creatorsWithUrl.length > 0 && (
              <button
                type="button"
                className="ghost small"
                aria-label={km.addAllCreatorsAria}
                title={km.addAllCreatorsTitle}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  creatorsWithUrl.forEach((c) => {
                    onAddCreator({ name: c.name || c.handle, url: c.url, platform: c.platform });
                  });
                }}
              >
                +
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
                    className="ghost small"
                    aria-label={km.addCreatorAria}
                    title={!c.url ? km.noCreatorUrlTitle : km.addCreatorTitle}
                    disabled={!onAddCreator || !c.url}
                    onClick={() =>
                      c.url && onAddCreator?.({ name: c.name || c.handle, url: c.url, platform: c.platform })
                    }
                  >
                    +
                  </button>
                </div>
                {c.why_relevant && <div className="creator-why muted">{c.why_relevant}</div>}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
};
