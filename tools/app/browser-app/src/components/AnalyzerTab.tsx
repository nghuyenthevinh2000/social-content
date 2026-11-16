import React from 'react';

import { JobResult } from '../analysis/JobResult';
import { cleanTopicTitle, formatTime, STATUS_LABEL, TERMINAL } from '../analysis/format';
import type { Job, JobKind, JobSummary, Topic } from '../analysis/types';

const KIND_LABEL: Record<JobKind, string> = {
  profile: 'Kênh',
  reel: 'Reel',
  keyword: 'Từ khoá',
};

type AnalyzerTabProps = {
  keyword: string;
  onKeywordChange: (value: string) => void;
  onSearchKeyword: (keyword: string) => void;
  blocked: boolean;
  error: string | null;
  starting: boolean;
  jobId: string | null;
  job: Job | null;
  visibleHistory: JobSummary[];
  loadingHistory: boolean;
  onFetchHistory: () => void;
  onSelectJob: (id: string | null) => void;
  onDeleteJob: (id: string, e: React.MouseEvent) => void;
  tourDemoId: string;
  copiedKey: string | null;
  onCopyTopic: (topic: Topic, sheetName: string, key: string) => void;
  onAddCreator: (creator: { name: string; url: string; platform?: string }) => void;
  onSaveVideo: (topic: Topic) => void;
  onGoToLibrary: () => void;
};

export const AnalyzerTab: React.FC<AnalyzerTabProps> = ({
  keyword,
  onKeywordChange,
  onSearchKeyword,
  blocked,
  error,
  starting,
  jobId,
  job,
  visibleHistory,
  loadingHistory,
  onFetchHistory,
  onSelectJob,
  onDeleteJob,
  tourDemoId,
  copiedKey,
  onCopyTopic,
  onAddCreator,
  onSaveVideo,
  onGoToLibrary,
}) => {
  return (
    <>
      <section className="panel keyword-search-panel">
        <h2>Tìm video viral</h2>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            const kw = keyword.trim();
            if (kw) onSearchKeyword(kw);
          }}
        >
          <input
            type="text"
            className="text-input"
            placeholder="Tìm video viral theo từ khoá (vd: gyno conditions)"
            aria-label="Tìm video viral theo từ khoá"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
          />
          <button
            type="submit"
            className="primary"
            style={{ flex: 'none', width: 'auto', padding: '0 var(--space-4)' }}
            disabled={blocked || !keyword.trim()}
          >
            Tìm Video Viral
          </button>
        </form>
      </section>

      <section className="panel" id="results">
        {error && <div className="alert error">{error}</div>}
        {starting ? (
          <div className="empty">
            <p className="muted">Đang tạo job…</p>
          </div>
        ) : jobId && !job ? (
          <div className="empty">
            <p className="muted">Đang tải kết quả phân tích…</p>
          </div>
        ) : !job ? (
          <>
            <div className="panel-head">
              <div>
                <h2>Lịch sử phân tích</h2>
                <p className="muted count">
                  {visibleHistory.length > 0 ? `${visibleHistory.length} lần chạy` : 'Chưa có lần chạy nào'}
                </p>
              </div>
              <button type="button" className="ghost small" onClick={onFetchHistory} disabled={loadingHistory}>
                {loadingHistory ? 'Đang tải…' : '↻ Làm mới'}
              </button>
            </div>

            {visibleHistory.length === 0 ? (
              <div className="empty">
                <p className="muted">Chưa có lần chạy nào trong lịch sử.</p>
                <button type="button" className="ghost" onClick={onGoToLibrary}>
                  Chọn chủ đề trong Thư viện để chạy
                </button>
              </div>
            ) : (
              <div className="history-list">
                {visibleHistory.map((item) => {
                  const isRunning = !TERMINAL.has(item.status);
                  const kind: JobKind = item.job_kind ?? 'profile';
                  return (
                    <div
                      key={item.id}
                      className={`history-card ${isRunning ? 'running-card' : ''}`}
                      onClick={() => onSelectJob(item.id)}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="history-head">
                        <span className="history-filename" title={cleanTopicTitle(item.filename)}>
                          {cleanTopicTitle(item.filename)}
                        </span>
                        <div className="history-badges">
                          <span className={`badge kind-${kind}`}>{KIND_LABEL[kind]}</span>
                          <span className={`badge ${item.status}`}>
                            {isRunning && <span className="live-dot" />}
                            {STATUS_LABEL[item.status] || item.status}
                          </span>
                        </div>
                      </div>
                      <div className="history-meta muted">
                        <span>{formatTime(item.created_at)}</span>
                        <span>·</span>
                        <span>{item.total_sheets} chủ đề</span>
                        {item.total_topics > 0 && (
                          <>
                            <span>·</span>
                            <span className="history-topics">
                              {item.total_topics} {kind === 'keyword' ? 'video' : 'ý tưởng'}
                            </span>
                          </>
                        )}
                        {isRunning && item.total_sheets > 0 && (
                          <>
                            <span>·</span>
                            <span>
                              {item.completed_sheets}/{item.total_sheets} xong
                            </span>
                          </>
                        )}
                      </div>
                      <div className="history-actions">
                        <button
                          type="button"
                          className="ghost small history-view-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectJob(item.id);
                          }}
                        >
                          {isRunning ? '▶ Xem tiến độ' : 'Xem kết quả'}
                        </button>
                        {item.id !== tourDemoId && (
                          <button
                            type="button"
                            className="channel-del-btn"
                            aria-label={`Xoá lần chạy ${cleanTopicTitle(item.filename)}`}
                            title="Xoá lần chạy"
                            onClick={(e) => onDeleteJob(item.id, e)}
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <JobResult
            job={job}
            historyCount={visibleHistory.length}
            copiedKey={copiedKey}
            onBack={() => onSelectJob(null)}
            onCopyTopic={onCopyTopic}
            onAddCreator={onAddCreator}
            onSaveVideo={onSaveVideo}
          />
        )}
      </section>
    </>
  );
};
