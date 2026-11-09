import { IonContent, IonFooter, IonHeader, IonIcon, IonPage } from '@ionic/react';
import { analyticsOutline, libraryOutline, personCircleOutline } from 'ionicons/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { apiFetch, apiJson } from '../api';
import { AuthModal } from '../components/AuthModal';
import { auth, onAuthStateChanged, signOut, type User } from '../firebase';
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
  source_breakdown?: {
    glasser_api?: string[];
    cache?: string[];
    empty?: string[];
  };
  topics: Topic[];
  error: string | null;
  notice?: string | null;
};

type Job = {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  filename: string;
  created_at?: string;
  current_sheet: string | null;
  sheets: Sheet[];
  logs: { at: string; sheet: string | null; message: string }[];
};

type JobSummary = {
  id: string;
  status: Job['status'];
  filename: string;
  created_at: string;
  finished_at: string | null;
  current_sheet: string | null;
  total_sheets: number;
  completed_sheets: number;
  total_topics: number;
};

export type TargetItem = { name: string; url: string };
export type TopicItem = { name: string; slug: string; targets: TargetItem[] };
type Tab = 'library' | 'analyzer' | 'profile';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'library', label: 'Thư viện', icon: libraryOutline },
  { id: 'analyzer', label: 'Phân tích', icon: analyticsOutline },
  { id: 'profile', label: 'Hồ sơ', icon: personCircleOutline },
];

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
const reelLink = (url: string) => {
  if (!url) return '';
  const trimmed = url.trim();
  if (trimmed.includes('/reel/') || trimmed.includes('/videos/') || trimmed.includes('/watch/')) {
    return trimmed;
  }
  if (trimmed.includes('facebook.com') && !trimmed.includes('/reels')) {
    return trimmed.replace(/\/+$/, '') + '/reels/';
  }
  return trimmed;
};

function formatTopicForAI(topic: Topic, sheetName?: string): string {
  const lines: string[] = [];
  lines.push(`### Chủ đề: ${topic.title}`);
  if (sheetName) lines.push(`- **Nhóm chủ đề**: ${sheetName}`);
  if (topic.format) lines.push(`- **Định dạng**: ${topic.format}`);
  if (topic.hook) lines.push(`- **Hook (3s đầu)**: "${topic.hook}"`);
  if (topic.angle) lines.push(`- **Góc tiếp cận**: ${topic.angle}`);
  if (topic.why_viral) lines.push(`- **Lý do viral & Bằng chứng**: ${topic.why_viral}`);
  if (topic.outline && topic.outline.length > 0) {
    lines.push(`- **Dàn ý triển khai**:`);
    topic.outline.forEach((step, idx) => lines.push(`  ${idx + 1}. ${step}`));
  }
  if (topic.source_urls && topic.source_urls.length > 0) {
    const urls = topic.source_urls.map((u) => reelLink(u)).join('\n  - ');
    lines.push(`- **Reel tham khảo**:\n  - ${urls}`);
  }
  lines.push('');
  lines.push('---');
  lines.push('Nhiệm vụ cho AI: Dựa trên dàn ý và hook ở trên, hãy viết kịch bản chi tiết cho video ngắn (Reels/TikTok/Shorts khoảng 30-45 giây). Kịch bản cần có 3 cột: Thời lượng (giây) | Hình ảnh / Cảnh quay (Visual) | Lời thoại / Voiceover (Audio). Nhịp điệu nhanh, giữ chân người xem ngay từ 3 giây đầu.');
  return lines.join('\n');
}

function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-999999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand('copy');
    textarea.remove();
    return Promise.resolve();
  } catch (err) {
    textarea.remove();
    return Promise.reject(err);
  }
}
const errorText = (err: unknown) => (err instanceof Error ? err.message : String(err));
const formatTime = (iso?: string) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    }).format(d);
  } catch {
    return iso;
  }
};

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
  const initialJobId = query.get('job_id') || localStorage.getItem('aibrand-active-job-id');
  const [tab, setTab] = useState<Tab>(
    query.get('tab') === 'profile'
      ? 'profile'
      : initialJobId || query.get('tab') === 'analyzer'
        ? 'analyzer'
        : 'library',
  );

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
  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const [history, setHistory] = useState<JobSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopyTopic = async (topic: Topic, sheetName: string, key: string) => {
    try {
      const text = formatTopicForAI(topic, sheetName);
      await copyToClipboard(text);
      setCopiedKey(key);
      setTimeout(() => {
        setCopiedKey((prev) => (prev === key ? null : prev));
      }, 2000);
    } catch (err) {
      console.error('Failed to copy topic:', err);
    }
  };

  // Firebase Auth
  const [user, setUser] = useState<User | null>(auth.currentUser);
  const [authReady, setAuthReady] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser: User | null) => {
      setUser(currentUser);
      setAuthReady(true);
      if (!currentUser) {
        setTopics([]);
        setJob(null);
        setJobId(null);
        setHistory([]);
        localStorage.removeItem('aibrand-active-job-id');
      }
    });
    return () => unsubscribe();
  }, []);

  function selectJob(id: string | null) {
    setJobId(id);
    if (id) {
      localStorage.setItem('aibrand-active-job-id', id);
      window.history.replaceState(null, '', `?tab=${tab}&job_id=${id}`);
    } else {
      localStorage.removeItem('aibrand-active-job-id');
      setJob(null);
      window.history.replaceState(null, '', `?tab=${tab}`);
    }
  }

  function switchTab(next: Tab) {
    setTab(next);
    window.history.replaceState(null, '', jobId ? `?tab=${next}&job_id=${jobId}` : `?tab=${next}`);
  }

  async function fetchHistory() {
    if (!user) return [];
    setLoadingHistory(true);
    try {
      const data = await apiJson<{ ok: boolean; jobs: JobSummary[] }>('/api/jobs');
      const jobs = data.jobs || [];
      setHistory(jobs);
      return jobs;
    } catch {
      return [];
    } finally {
      setLoadingHistory(false);
    }
  }

  async function deleteJob(id: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    if (!window.confirm('Bạn có chắc muốn xoá lần chạy này khỏi lịch sử?')) return;
    try {
      await apiFetch(`/api/jobs/${id}/delete`, { method: 'POST' });
      setHistory((prev) => prev.filter((j) => j.id !== id));
      if (jobId === id) {
        selectJob(null);
      }
    } catch (err) {
      alert(`Không thể xoá: ${errorText(err)}`);
    }
  }

  // Every library mutation goes through here; the server returns the full, normalized topic list.
  async function library(path: string, body?: BodyInit, headers?: HeadersInit, success?: string) {
    if (!user) {
      setShowAuthModal(true);
      return false;
    }
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
    if (!authReady || !user) return;
    let ignore = false;
    apiJson<{ topics?: TopicItem[] }>('/api/sources/topics')
      .then((data) => {
        if (!ignore) setTopics(data.topics || []);
      })
      .catch((err) => {
        if (!ignore) setNotice({ type: 'error', text: `Không tải được thư viện: ${errorText(err)}` });
      });

    apiJson<{ ok: boolean; jobs: JobSummary[] }>('/api/jobs')
      .then((data) => {
        if (ignore) return;
        const jobs = data.jobs || [];
        setHistory(jobs);
        const activeRunning = jobs.find((j) => !TERMINAL.has(j.status));
        const storedId = query.get('job_id') || localStorage.getItem('aibrand-active-job-id');
        const targetId = storedId || activeRunning?.id;
        if (targetId) {
          selectJob(targetId);
        }
      })
      .catch(() => {});

    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, user?.uid]);

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
    if (!jobId || !user) return;
    let stopped = false;
    const tick = async () => {
      try {
        const data = await apiJson<Job>(`/api/jobs/${jobId}`);
        if (stopped) return;
        setJob(data);
        if (TERMINAL.has(data.status)) {
          stopped = true;
          fetchHistory();
        }
      } catch {
        stopped = true;
        selectJob(null);
      }
    };
    tick();
    const timer = window.setInterval(() => (stopped ? window.clearInterval(timer) : tick()), 1500);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, user?.uid]);

  const progress = useMemo(() => {
    if (!job) return { done: 0, total: 0, pct: 0 };
    const done = job.sheets.filter((sheet) => TERMINAL.has(sheet.status)).length;
    const total = job.sheets.length;
    return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
  }, [job]);

  const running = job ? !TERMINAL.has(job.status) : false;
  const hasActiveJob = useMemo(() => {
    return running || history.some((j) => !TERMINAL.has(j.status));
  }, [running, history]);
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
    if (!user) {
      setShowAuthModal(true);
      return;
    }
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
      selectJob(data.id);
      fetchHistory();
    } catch (err) {
      setError(errorText(err));
      reportClientLog(errorText(err), err instanceof Error ? err.stack : undefined, 'start-job');
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    if (jobId) {
      await apiFetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      fetchHistory();
    }
  }

  function importSource(source: File | string) {
    if (!user) {
      setShowAuthModal(true);
      return Promise.resolve(false);
    }
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
    if (!user) {
      setShowAuthModal(true);
      return false;
    }
    return postJson('/api/sources/topics', { topic, url }, `Đã thêm kênh vào "${topic}".`);
  }

  async function createTopic(e: React.FormEvent) {
    e.preventDefault();
    if (!user) {
      setShowAuthModal(true);
      return;
    }
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
        </div>
      </IonHeader>

      <IonContent>
        <div className="ab-page">
          {!authReady ? (
            <div className="empty">
              <p className="muted">Đang kiểm tra đăng nhập…</p>
            </div>
          ) : tab === 'profile' ? (
            <section className="panel profile">
              <div className="profile-head">
                <span className="avatar">{user ? (user.email || user.uid)[0].toUpperCase() : '?'}</span>
                <div className="sheet-title">
                  <strong>{user ? user.displayName || user.email || 'Người dùng' : 'Chưa đăng nhập'}</strong>
                  {!user && <small className="muted">Đăng nhập để đồng bộ tài khoản của bạn.</small>}
                </div>
              </div>
              {user ? (
                <>
                  <dl className="details">
                    <dt>Email</dt>
                    <dd>{user.email || '—'}</dd>
                    <dt>Đăng nhập gần nhất</dt>
                    <dd>{user.metadata.lastSignInTime || '—'}</dd>
                  </dl>
                  <button
                    type="button"
                    className="ghost danger profile-btn"
                    onClick={() => {
                      setTopics([]);
                      setJob(null);
                      setJobId(null);
                      setHistory([]);
                      localStorage.removeItem('aibrand-active-job-id');
                      window.history.replaceState(null, '', '?tab=profile');
                      signOut(auth);
                    }}
                  >
                    Đăng xuất
                  </button>
                </>
              ) : (
                <button type="button" className="primary profile-btn" onClick={() => setShowAuthModal(true)}>
                  Đăng nhập / Đăng ký
                </button>
              )}
            </section>
          ) : tab === 'library' ? (
            !user ? (
              <section className="panel">
                <div className="empty">
                  <span className="gate-icon">🔒</span>
                  <h2>Yêu cầu đăng nhập</h2>
                  <p className="muted">Vui lòng đăng nhập tài khoản để xem, quản lý Thư viện kênh và chạy phân tích.</p>
                  <button type="button" className="primary auth-gate-btn" onClick={() => setShowAuthModal(true)}>
                    Đăng nhập / Đăng ký
                  </button>
                </div>
              </section>
            ) : (
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
            )
          ) : (
            <section className="panel" id="results">
              {error && <div className="alert error">{error}</div>}
              {!user ? (
                <div className="empty">
                  <span className="gate-icon">🔒</span>
                  <h2>Yêu cầu đăng nhập</h2>
                  <p className="muted">Vui lòng đăng nhập tài khoản để bắt đầu chạy phân tích.</p>
                  <button type="button" className="primary auth-gate-btn" onClick={() => setShowAuthModal(true)}>
                    Đăng nhập / Đăng ký
                  </button>
                </div>
              ) : starting ? (
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
                        {history.length > 0 ? `${history.length} lần chạy` : 'Chưa có lần chạy nào'}
                      </p>
                    </div>
                    <button type="button" className="ghost small" onClick={fetchHistory} disabled={loadingHistory}>
                      {loadingHistory ? 'Đang tải…' : '↻ Làm mới'}
                    </button>
                  </div>

                  {history.length === 0 ? (
                    <div className="empty">
                      <p className="muted">Chưa có lần chạy nào trong lịch sử.</p>
                      <button type="button" className="ghost" onClick={() => switchTab('library')}>
                        Chọn chủ đề trong Thư viện để chạy
                      </button>
                    </div>
                  ) : (
                    <div className="history-list">
                      {history.map((item) => {
                        const isRunning = !TERMINAL.has(item.status);
                        return (
                          <div
                            key={item.id}
                            className={`history-card ${isRunning ? 'running-card' : ''}`}
                            onClick={() => selectJob(item.id)}
                            role="button"
                            tabIndex={0}
                          >
                            <div className="history-head">
                              <span className="history-filename" title={item.filename}>
                                {item.filename}
                              </span>
                              <span className={`badge ${item.status}`}>
                                {isRunning && <span className="live-dot" />}
                                {STATUS_LABEL[item.status] || item.status}
                              </span>
                            </div>
                            <div className="history-meta muted">
                              <span>{formatTime(item.created_at)}</span>
                              <span>·</span>
                              <span>{item.total_sheets} chủ đề</span>
                              {item.total_topics > 0 && (
                                <>
                                  <span>·</span>
                                  <span className="history-topics">{item.total_topics} ý tưởng</span>
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
                                  selectJob(item.id);
                                }}
                              >
                                {isRunning ? '▶ Xem tiến độ' : 'Xem kết quả'}
                              </button>
                              <button
                                type="button"
                                className="channel-del-btn"
                                aria-label={`Xoá lần chạy ${item.filename}`}
                                title="Xoá lần chạy"
                                onClick={(e) => deleteJob(item.id, e)}
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="panel-head">
                    <div>
                      <button type="button" className="history-back-btn" onClick={() => selectJob(null)}>
                        ← Lịch sử chạy ({history.length})
                      </button>
                      <h2>Kết quả</h2>
                      <p className="muted count">
                        {job.filename} · {progress.done}/{progress.total} · {STATUS_LABEL[job.status]}
                        {job.created_at && ` · ${formatTime(job.created_at)}`}
                      </p>
                    </div>
                    <div className="panel-head-actions">
                      <a
                        href={`/api/jobs/${job.id}/export`}
                        download={`viral-research-${job.id}.json`}
                        className="ghost small"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Xuất JSON
                      </a>
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
                      {sheet.source_breakdown && ((sheet.source_breakdown.glasser_api?.length ?? 0) > 0 || (sheet.source_breakdown.cache?.length ?? 0) > 0) && (
                        <div className="source-breakdown muted" style={{ fontSize: '0.82rem', margin: '0.35rem 0' }}>
                          {(sheet.source_breakdown.glasser_api?.length ?? 0) > 0 && (
                            <span title={sheet.source_breakdown.glasser_api?.join(', ')}>
                              ⚡ Glasser API: {sheet.source_breakdown.glasser_api?.length} kênh
                            </span>
                          )}
                          {(sheet.source_breakdown.glasser_api?.length ?? 0) > 0 && (sheet.source_breakdown.cache?.length ?? 0) > 0 && ' · '}
                          {(sheet.source_breakdown.cache?.length ?? 0) > 0 && (
                            <span title={sheet.source_breakdown.cache?.join(', ')}>
                              💾 Cache: {sheet.source_breakdown.cache?.length} kênh
                            </span>
                          )}
                        </div>
                      )}
                      {sheet.error && <div className="alert error">{sheet.error}</div>}
                      {sheet.notice && <div className="alert warn">{sheet.notice}</div>}
                      {sheet.status === 'completed' && sheet.reels === 0 && !sheet.error && !sheet.notice && (
                        <div className="alert warn">
                          Không tìm thấy reel mới nào trong 48 giờ qua. Vui lòng cập nhật thêm danh sách kênh.
                        </div>
                      )}
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
                                <div className="topic-foot-left">
                                  {topic.format && <span>{topic.format}</span>}
                                  {topic.source_urls && topic.source_urls.length > 0 && (
                                    <span className="topic-reels">
                                      {topic.source_urls.map((url, i) => (
                                        <a
                                          key={i}
                                          href={reelLink(url)}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{ marginLeft: i > 0 ? 8 : 0 }}
                                        >
                                          {topic.source_urls.length > 1 ? `Reel gốc ${i + 1} ↗` : 'Reel gốc ↗'}
                                        </a>
                                      ))}
                                    </span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  className={`copy-topic-btn ${copiedKey === `${sheet.slug}-${topicIndex}` ? 'copied' : ''}`}
                                  onClick={() => handleCopyTopic(topic, sheet.name, `${sheet.slug}-${topicIndex}`)}
                                  title="Sao chép nội dung kịch bản để dán vào AI Agent"
                                >
                                  {copiedKey === `${sheet.slug}-${topicIndex}` ? (
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

      <IonFooter className="ion-no-border">
        {((tab === 'library' && user) || (tab === 'analyzer' && running)) && (
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
        )}
        <nav className="tabbar" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`tabbar-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => switchTab(t.id)}
            >
              <span className="tabbar-icon">
                <IonIcon icon={t.icon} aria-hidden="true" />
                {t.id === 'analyzer' && hasActiveJob && <span className="live-dot" aria-label="đang chạy" />}
                {t.id === 'profile' && user && <span className="live-dot online" aria-label="đã đăng nhập" />}
              </span>
              {t.label}
            </button>
          ))}
        </nav>
      </IonFooter>

      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </IonPage>
  );
};

export default Home;
