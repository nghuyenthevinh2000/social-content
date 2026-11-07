import { IonContent, IonFooter, IonHeader, IonPage } from '@ionic/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { apiFetch, apiJson } from '../api';
import './Home.css';

type Topic = {
  title: string;
  hook: string;
  angle: string;
  why_viral: string;
  outline: string[];
  format: string;
  source_urls: string[];
  generated_by: string;
};

type Sheet = {
  name: string;
  slug: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  targets: number;
  reels: number;
  pool_distribution: Record<string, number>;
  topics: Topic[];
  error: string | null;
};

type Job = {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  filename: string;
  current_sheet: string | null;
  sheets: Sheet[];
  logs: { at: string; sheet: string | null; message: string }[];
};

export type TargetItem = { name: string; url: string };
export type TopicItem = { name: string; slug: string; targets: TargetItem[] };
type Tab = 'library' | 'analyzer';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

const STATUS_LABEL: Record<Job['status'], string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  completed: 'Hoàn tất',
  failed: 'Có lỗi',
  cancelled: 'Đã dừng',
};

const EXCEL_ACCEPT =
  '.xlsx,.xlsm,.xls,.gsheet,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.google-apps.spreadsheet';

const formatNumber = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
const shortUrl = (url: string) => url.replace(/^https?:\/\/(www\.)?/, '');
const errorText = (err: unknown) => (err instanceof Error ? err.message : String(err));

function reportClientLog(message: string, stack?: string, source = 'client') {
  apiFetch('/api/logs/client', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, stack, source }),
  }).catch(() => {});
}

const Home: React.FC = () => {
  const location = useLocation();
  const query = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const [tab, setTab] = useState<Tab>(query.get('job_id') || query.get('tab') === 'analyzer' ? 'analyzer' : 'library');

  // Library (backend is the source of truth)
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [search, setSearch] = useState('');
  const [sheetUrl, setSheetUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [inlineUrls, setInlineUrls] = useState<Record<string, string>>({});
  const [newTopic, setNewTopic] = useState({ name: '', url: '' });
  const fileRef = useRef<HTMLInputElement>(null);

  // Analyzer
  // @deprecated [OBSOLETE]: Local video download + transcribe is obsolete. Retained for backward-compat; do not delete.
  const [media] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(query.get('job_id'));
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  function switchTab(next: Tab) {
    setTab(next);
    window.history.replaceState(null, '', jobId ? `?tab=${next}&job_id=${jobId}` : `?tab=${next}`);
  }

  // Every library mutation goes through here; the server returns the full, normalized topic list.
  async function library(path: string, body?: BodyInit, headers?: HeadersInit, success?: string) {
    setBusy(true);
    setNotice(null);
    try {
      const data = await apiJson<{ topics?: TopicItem[] }>(path, body ? { method: 'POST', headers, body } : undefined);
      setTopics(data.topics || []);
      if (success) setNotice({ type: 'success', text: success });
      return true;
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  const postJson = (path: string, payload: object, success?: string) =>
    library(path, JSON.stringify(payload), { 'Content-Type': 'application/json' }, success);

  useEffect(() => {
    apiJson<{ topics?: TopicItem[] }>('/api/sources/topics')
      .then((data) => setTopics(data.topics || []))
      .catch((err) => setNotice({ type: 'error', text: `Không tải được thư viện: ${errorText(err)}` }));
  }, []);

  useEffect(() => {
    const onError = (e: ErrorEvent) =>
      reportClientLog(e.message, e.error?.stack || `${e.filename}:${e.lineno}`, 'window.error');
    const onRejection = (e: PromiseRejectionEvent) =>
      reportClientLog(String(e.reason?.message || e.reason), e.reason?.stack, 'unhandledrejection');
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    const tick = async () => {
      try {
        const data = await apiJson<Job>(`/api/jobs/${jobId}`);
        if (stopped) return;
        setJob(data);
        if (TERMINAL.has(data.status)) stopped = true;
      } catch {
        // keep polling
      }
    };
    tick();
    const timer = window.setInterval(() => (stopped ? window.clearInterval(timer) : tick()), 1500);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [jobId]);

  const progress = useMemo(() => {
    if (!job) return { done: 0, total: 0, pct: 0 };
    const done = job.sheets.filter((sheet) => TERMINAL.has(sheet.status)).length;
    const total = job.sheets.length;
    return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
  }, [job]);

  const running = job ? !TERMINAL.has(job.status) : false;
  const runnable = topics.filter((t) => t.targets.length > 0);
  const totalChannels = topics.reduce((acc, t) => acc + t.targets.length, 0);

  const filteredTopics = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return topics;
    return topics.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.targets.some((tg) => tg.name.toLowerCase().includes(q) || tg.url.toLowerCase().includes(q)),
    );
  }, [topics, search]);

  async function run(selected: TopicItem[], filename: string) {
    setError(null);
    setStarting(true);
    setJob(null);
    switchTab('analyzer');
    try {
      const params = new URLSearchParams(media ? { media: '1' } : {});
      const qs = params.toString();
      const endpoint = qs ? `/api/jobs?${qs}` : '/api/jobs';
      const payload = { sheets: selected.map((t) => ({ name: t.name, targets: t.targets })) };
      const data = await apiJson<Job>(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Filename': encodeURIComponent(filename) },
        body: JSON.stringify(payload),
      });
      setJob(data);
      setJobId(data.id);
      window.history.replaceState(null, '', `?tab=analyzer&job_id=${data.id}`);
    } catch (err) {
      setError(errorText(err));
      reportClientLog(errorText(err), err instanceof Error ? err.stack : undefined, 'start-job');
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (jobId) await apiFetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
  }

  function importSource(source: File | string) {
    const isUrl = typeof source === 'string';
    return library(
      '/api/sources/parse',
      source,
      {
        'Content-Type': isUrl ? 'text/plain' : source.type || 'application/octet-stream',
        'X-Filename': encodeURIComponent(isUrl ? 'sheet_import.xlsx' : source.name),
      },
      'Đã nạp vào thư viện.',
    ).then((ok) => ok && isUrl && setSheetUrl(''));
  }

  async function addChannel(topic: string, url: string) {
    return postJson('/api/sources/topics', { topic, url }, `Đã thêm kênh vào "${topic}".`);
  }

  async function createTopic(e: React.FormEvent) {
    e.preventDefault();
    const name = newTopic.name.trim();
    const url = newTopic.url.trim();
    if (!name) return;
    const ok = url ? await addChannel(name, url) : await postJson('/api/sources/topics', { topic: name });
    if (ok) setNewTopic({ name: '', url: '' });
  }

  const blocked = starting || running;

  return (
    <IonPage className="ab">
      <IonHeader className="ion-no-border">
        <div className="topbar">
          <span className="brand">
            <span className="brand-mark">AB</span>AIBrand
          </span>
          <div className="tab-nav" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'library'}
              className={`tab-nav-btn ${tab === 'library' ? 'active' : ''}`}
              onClick={() => switchTab('library')}
            >
              Thư viện
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'analyzer'}
              className={`tab-nav-btn ${tab === 'analyzer' ? 'active' : ''}`}
              onClick={() => switchTab('analyzer')}
            >
              Phân tích
              {running && <span className="live-dot" aria-label="đang chạy" />}
            </button>
          </div>
        </div>
      </IonHeader>

      <IonContent>
        <div className="ab-page">
          {tab === 'library' ? (
            <>
              <section className="panel" id="import">
                <h2>Nhập vào thư viện</h2>
                <button className="picker" type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
                  <input
                    ref={fileRef}
                    type="file"
                    accept={EXCEL_ACCEPT}
                    hidden
                    onChange={(event) => {
                      const picked = event.target.files?.[0];
                      event.target.value = '';
                      if (picked) importSource(picked);
                    }}
                  />
                  <span className="picker-icon">⇪</span>
                  <span>
                    <strong>{busy ? 'Đang xử lý…' : 'Chọn file Excel'}</strong>
                    <small className="muted">Mỗi sheet thành một chủ đề · .xlsx / .xlsm</small>
                  </span>
                </button>
                <form
                  className="row"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (sheetUrl.trim()) importSource(sheetUrl.trim());
                  }}
                >
                  <input
                    type="url"
                    className="text-input"
                    placeholder="hoặc dán link Google Sheet"
                    aria-label="Link Google Sheet"
                    value={sheetUrl}
                    onChange={(e) => setSheetUrl(e.target.value)}
                  />
                  <button type="submit" className="ghost" disabled={busy || !sheetUrl.trim()}>
                    Nạp
                  </button>
                </form>
                <small className="muted hint">
                  Google Sheet: <strong>Chia sẻ</strong> → <strong>Bất kỳ ai có đường liên kết</strong> (Xem).
                </small>
                {notice && <div className={`alert ${notice.type}`}>{notice.text}</div>}
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2>Chủ đề</h2>
                  <span className="muted count">
                    {topics.length} chủ đề · {totalChannels} kênh
                  </span>
                </div>
                <input
                  type="search"
                  className="text-input search-input"
                  placeholder="Tìm chủ đề, kênh, link…"
                  aria-label="Tìm trong thư viện"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />

                {filteredTopics.length === 0 ? (
                  <p className="muted empty">
                    {topics.length ? 'Không có kết quả phù hợp.' : 'Thư viện trống. Nhập file hoặc tạo chủ đề.'}
                  </p>
                ) : (
                  filteredTopics.map((topic) => (
                    <details key={topic.slug} className="topic-accordion">
                      <summary>
                        <span className="sheet-title">
                          <strong>{topic.name}</strong>
                          <small className="muted">{topic.targets.length} kênh</small>
                        </span>
                        <button
                          type="button"
                          className="topic-run-btn"
                          onClick={(e) => {
                            e.preventDefault();
                            run([topic], `${topic.slug}.json`);
                          }}
                          disabled={blocked || topic.targets.length === 0}
                        >
                          ▶ Chạy
                        </button>
                      </summary>

                      <div className="accordion-body">
                        {topic.targets.map((target) => (
                          <div key={target.url} className="channel-card">
                            <div className="channel-info">
                              <span className="channel-name">{target.name}</span>
                              <a href={target.url} target="_blank" rel="noreferrer" className="channel-link">
                                {shortUrl(target.url)} ↗
                              </a>
                            </div>
                            <button
                              type="button"
                              className="channel-del-btn"
                              aria-label={`Xoá kênh ${target.name}`}
                              onClick={() =>
                                postJson('/api/sources/profiles/delete', { slug: topic.slug, url: target.url })
                              }
                            >
                              ✕
                            </button>
                          </div>
                        ))}

                        <form
                          className="row"
                          onSubmit={async (e) => {
                            e.preventDefault();
                            const url = (inlineUrls[topic.slug] || '').trim();
                            if (url && (await addChannel(topic.name, url)))
                              setInlineUrls((prev) => ({ ...prev, [topic.slug]: '' }));
                          }}
                        >
                          <input
                            type="url"
                            className="text-input small"
                            placeholder="Dán link kênh…"
                            aria-label={`Thêm kênh vào ${topic.name}`}
                            value={inlineUrls[topic.slug] || ''}
                            onChange={(e) => setInlineUrls((prev) => ({ ...prev, [topic.slug]: e.target.value }))}
                          />
                          <button
                            type="submit"
                            className="ghost small"
                            disabled={busy || !(inlineUrls[topic.slug] || '').trim()}
                          >
                            + Thêm
                          </button>
                        </form>

                        <button
                          type="button"
                          className="btn-text-danger"
                          onClick={() =>
                            window.confirm(`Xoá chủ đề "${topic.name}" cùng toàn bộ kênh?`) &&
                            postJson('/api/sources/topics/delete', { slug: topic.slug })
                          }
                        >
                          Xoá chủ đề
                        </button>
                      </div>
                    </details>
                  ))
                )}

                <form className="new-topic" onSubmit={createTopic}>
                  <input
                    type="text"
                    className="text-input small"
                    placeholder="Tên chủ đề mới"
                    aria-label="Tên chủ đề mới"
                    value={newTopic.name}
                    onChange={(e) => setNewTopic((v) => ({ ...v, name: e.target.value }))}
                  />
                  <input
                    type="url"
                    className="text-input small"
                    placeholder="Link kênh đầu tiên (tuỳ chọn)"
                    aria-label="Link kênh đầu tiên"
                    value={newTopic.url}
                    onChange={(e) => setNewTopic((v) => ({ ...v, url: e.target.value }))}
                  />
                  <button type="submit" className="ghost small" disabled={busy || !newTopic.name.trim()}>
                    + Tạo chủ đề
                  </button>
                </form>
              </section>
            </>
          ) : (
            <section className="panel" id="results">
              {error && <div className="alert error">{error}</div>}
              {!job ? (
                <div className="empty">
                  <p className="muted">{starting ? 'Đang tạo job…' : 'Chưa có lần chạy nào.'}</p>
                  {!starting && (
                    <button type="button" className="ghost" onClick={() => switchTab('library')}>
                      Chọn chủ đề trong Thư viện
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <div className="panel-head">
                    <div>
                      <h2>Kết quả</h2>
                      <p className="muted count">
                        {job.filename} · {progress.done}/{progress.total} · {STATUS_LABEL[job.status]}
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
                    <details
                      key={sheet.slug}
                      className="sheet"
                      open={sheet.status === 'running' || job.sheets.length === 1 ? true : undefined}
                    >
                      <summary>
                        <span className="sheet-index">{String(index + 1).padStart(2, '0')}</span>
                        <span className="sheet-title">
                          <strong>{sheet.name}</strong>
                          <small className="muted">
                            {sheet.targets} kênh · {formatNumber(sheet.reels)} reel
                          </small>
                        </span>
                        <span className={`badge ${sheet.status}`}>{sheet.status}</span>
                      </summary>

                      {Object.keys(sheet.pool_distribution || {}).length > 0 && (
                        <div className="pools">
                          {Object.entries(sheet.pool_distribution).map(([pool, count]) => (
                            <span key={pool} className="pool">
                              {pool.replace('pool_', 'P')} · {count}
                            </span>
                          ))}
                        </div>
                      )}
                      {sheet.error && <div className="alert error">{sheet.error}</div>}
                      {sheet.status === 'pending' && <p className="muted">Đang chờ tới lượt…</p>}
                      {sheet.status === 'running' && <p className="muted">Đang crawl, phân pool và hỏi agent…</p>}

                      {sheet.topics.length > 0 && (
                        <div className="topics">
                          {sheet.topics.map((topic, topicIndex) => (
                            <article className="topic" key={topicIndex}>
                              <div className="topic-top">
                                <span className="topic-num">{topicIndex + 1}</span>
                                <span className={`source-tag ${topic.generated_by}`}>
                                  {topic.generated_by === 'agent' ? 'agent' : 'dự phòng'}
                                </span>
                              </div>
                              <h3>{topic.title}</h3>
                              {topic.hook && <p className="hook">“{topic.hook}”</p>}
                              {topic.angle && (
                                <p>
                                  <strong>Góc:</strong> {topic.angle}
                                </p>
                              )}
                              {topic.why_viral && (
                                <p>
                                  <strong>Vì sao viral:</strong> {topic.why_viral}
                                </p>
                              )}
                              {topic.outline?.length > 0 && (
                                <ol>
                                  {topic.outline.map((step, stepIndex) => (
                                    <li key={stepIndex}>{step}</li>
                                  ))}
                                </ol>
                              )}
                              <div className="topic-foot">
                                {topic.format && <span>{topic.format}</span>}
                                {topic.source_urls?.[0] && (
                                  <a href={topic.source_urls[0]} target="_blank" rel="noreferrer">
                                    Reel gốc ↗
                                  </a>
                                )}
                              </div>
                            </article>
                          ))}
                        </div>
                      )}
                    </details>
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
            </section>
          )}
        </div>
      </IonContent>

      {(tab === 'library' || running) && (
        <IonFooter className="ion-no-border">
          <div className="actionbar">
            {tab === 'library' && (
              <button
                className="primary"
                type="button"
                onClick={() => run(runnable, 'all_topics.json')}
                disabled={blocked || runnable.length === 0}
              >
                {running ? 'Đang chạy…' : `▶ Chạy tất cả (${runnable.length} chủ đề)`}
              </button>
            )}
            {running && (
              <button className="ghost danger" type="button" onClick={cancel}>
                Dừng
              </button>
            )}
          </div>
        </IonFooter>
      )}
    </IonPage>
  );
};

export default Home;
