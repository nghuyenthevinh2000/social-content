import { IonContent, IonFooter, IonHeader, IonIcon, IonPage } from '@ionic/react';
import { analyticsOutline, libraryOutline, personCircleOutline, videocamOutline } from 'ionicons/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { apiFetch, apiJson } from '../api';
import { AuthModal } from '../components/AuthModal';
import { MediaPanel } from '../components/MediaPanel';
import { Tour, type TourStep } from '../components/Tour';
import { VideoTab } from '../components/VideoTab';
import { CREATOR_PACKS, type CreatorPack } from '../data/creatorPacks';
import {
  auth,
  FacebookAuthProvider,
  linkWithPopup,
  onAuthStateChanged,
  signOut,
  type User,
} from '../firebase';
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
  prompt?: string;
  reel_url?: string;
  video_url?: string;
  video_id?: string;
  views?: number;
  velocity_per_hour?: number;
  current_pool?: number;
  pool_name?: string;
  likes?: number;
  comments?: number;
  shares?: number;
  author_handle?: string;
  author_name?: string;
  transcript?: string;
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
type Tab = 'library' | 'analyzer' | 'video' | 'profile';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'library', label: 'Thư viện', icon: libraryOutline },
  { id: 'analyzer', label: 'Phân tích', icon: analyticsOutline },
  { id: 'video', label: 'Tạo Video', icon: videocamOutline },
  { id: 'profile', label: 'Hồ sơ', icon: personCircleOutline },
];

const DEFAULT_TOPIC = 'sở thích cá nhân';
const isDefaultTopic = (t: TopicItem) => t.name.toLowerCase() === DEFAULT_TOPIC;
const TOUR_KEY = 'aibrand-tour-done';
const TOUR_STEPS: TourStep[] = [
  { tab: 'library', target: '.tabbar-btn:nth-child(1)', title: 'Thư viện', text: 'Nơi lưu các chủ đề và kênh creator bạn muốn theo dõi.' },
  { tab: 'library', target: '#import', title: 'Nhập dữ liệu', text: 'Chọn file Excel hoặc dán link Google Sheet — mỗi sheet thành một chủ đề.' },
  { tab: 'library', target: '.topic-accordion', title: 'Chủ đề mặc định', text: 'Mở chủ đề để thêm/xoá kênh, hoặc bấm ▶ Chạy để phân tích riêng chủ đề này.' },
  { tab: 'library', target: '.new-topic', title: 'Tạo chủ đề mới', text: 'Nhập tên chủ đề và (tuỳ chọn) link kênh đầu tiên.' },
  { tab: 'library', target: '.actionbar .primary', title: 'Chạy tất cả', text: 'Phân tích mọi chủ đề trong thư viện cùng lúc.' },
  { tab: 'analyzer', target: '.tabbar-btn:nth-child(2)', title: 'Phân tích', text: 'Xem tiến độ, lịch sử và kết quả ý tưởng viral. Dùng "Copy cho AI" để lấy kịch bản.' },
  { tab: 'video', target: '.tabbar-btn:nth-child(3)', title: 'Tạo Video AI', text: 'Tạo video ngắn 10 giây với khuôn mặt mẫu và giọng đọc tiếng Việt tự nhiên.' },
  { tab: 'profile', target: '.tabbar-btn:nth-child(4)', title: 'Hồ sơ', text: 'Đăng nhập/đăng xuất, nạp gói creator và quản lý ảnh mẫu khuôn mặt.' },
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
const formatCompact = (val?: number | null) => {
  if (!val && val !== 0) return '0';
  if (val >= 1_000_000) return (val / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (val >= 1_000) return (val / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(val);
};
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

const getTopicReelUrl = (topic: Topic): string => {
  if (topic.reel_url) return reelLink(topic.reel_url);
  if (topic.source_urls && topic.source_urls.length > 0) return reelLink(topic.source_urls[0]);
  if (topic.video_id) return `https://www.facebook.com/reel/${topic.video_id}`;
  return '';
};

export function formatTopicForAI(topic: Topic, sheetName?: string): string {
  // Use the AI-generated director prompt directly from backend
  if (topic.prompt && topic.prompt.trim()) {
    return topic.prompt.trim();
  }
  // Minimal fallback for legacy topics without generated prompt
  const lines: string[] = [];
  lines.push(`### Chủ đề: ${topic.title}`);
  if (sheetName) lines.push(`- **Nhóm chủ đề**: ${sheetName}`);
  if (topic.format) lines.push(`- **Định dạng**: ${topic.format}`);
  if (topic.hook) lines.push(`- **Hook**: "${topic.hook}"`);
  if (topic.angle) lines.push(`- **Góc tiếp cận**: ${topic.angle}`);
  if (topic.outline && topic.outline.length > 0) {
    lines.push(`- **Dàn ý triển khai**:`);
    topic.outline.forEach((step, idx) => lines.push(`  ${idx + 1}. ${step}`));
  }
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
const cleanTopicTitle = (title?: string | null) => {
  if (!title) return 'Phân tích';
  const stripped = String(title).replace(/\.(xlsx|json)$/i, '');
  if (stripped === 'all_topics' || stripped === 'tong-hop') return 'Tất cả chủ đề';
  return stripped;
};
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
      : query.get('tab') === 'video'
        ? 'video'
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
  const [playerMode, setPlayerMode] = useState<Record<string, 'video' | 'iframe'>>({});
  const [videoPrompt, setVideoPrompt] = useState('');
  const [videoDuration, setVideoDuration] = useState<number>(
    Number(import.meta.env.VITE_VIDEO_GENERATION_DURATION) || 15,
  );

  const handleCopyTopic = async (topic: Topic, sheetName: string, key: string) => {
    const text = formatTopicForAI(topic, sheetName);
    setVideoPrompt(text);
    switchTab('video');
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey((prev) => (prev === key ? null : prev));
    }, 2000);
    try {
      await copyToClipboard(text);
    } catch (err) {
      console.error('Failed to copy topic:', err);
    }
  };

  // Firebase Auth
  const [user, setUser] = useState<User | null>(auth.currentUser);
  const [authReady, setAuthReady] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  // Seen-flag is per account, so a freshly registered user gets the tour even on a browser that showed it before.
  const [tourDismissed, setTourDismissed] = useState(false);
  const [tourReplay, setTourReplay] = useState(false);
  const [linkingFb, setLinkingFb] = useState(false);
  const [linkFbError, setLinkFbError] = useState<string | null>(null);

  const fbAccount = user?.providerData?.find((p) => p.providerId === 'facebook.com');
  const facebookId = fbAccount?.uid;

  const handleLinkFacebook = async () => {
    if (!auth.currentUser) return;
    setLinkingFb(true);
    setLinkFbError(null);
    try {
      const provider = new FacebookAuthProvider();
      provider.addScope('public_profile');
      provider.addScope('email');
      const res = await linkWithPopup(auth.currentUser, provider);
      setUser(res.user);
    } catch (err: any) {
      let msg = err.message || 'Lỗi khi liên kết tài khoản Facebook.';
      if (err.code === 'auth/credential-already-in-use') {
        msg = 'Tài khoản Facebook này đã được liên kết với một tài khoản khác.';
      } else if (err.code === 'auth/popup-closed-by-user') {
        msg = 'Bạn đã đóng cửa sổ liên kết.';
      } else if (err.code === 'auth/cancelled-popup-request') {
        msg = 'Yêu cầu liên kết bị hủy.';
      }
      setLinkFbError(msg);
    } finally {
      setLinkingFb(false);
    }
  };

  const tourKey = user ? `${TOUR_KEY}-${user.uid}` : '';
  const showTour = !!user && (tourReplay || (!tourDismissed && !localStorage.getItem(tourKey)));
  const closeTour = () => {
    if (tourKey) localStorage.setItem(tourKey, '1');
    setTourDismissed(true);
    setTourReplay(false);
  };

  // In-App Payment Mock
  const [activePaymentPack, setActivePaymentPack] = useState<CreatorPack | null>(null);
  const [claimingPack, setClaimingPack] = useState<string | null>(null);

  function resetUserSessionState() {
    setTourDismissed(false);
    setTourReplay(false);
    setTopics([]);
    setNotice(null);
    setError(null);
    setSearch('');
    setSheetUrl('');
    setInlineUrls({});
    setNewTopic({ name: '', url: '' });
    setJob(null);
    setJobId(null);
    setHistory([]);
    setActivePaymentPack(null);
    setVideoPrompt('');
    localStorage.removeItem('aibrand-active-job-id');
  }

  useEffect(() => {
    let lastUid = auth.currentUser?.uid ?? null;
    const unsubscribe = onAuthStateChanged(auth, (currentUser: User | null) => {
      const nextUid = currentUser?.uid ?? null;
      if (!currentUser || nextUid !== lastUid) {
        resetUserSessionState();
      }
      lastUid = nextUid;
      setUser(currentUser);
      setAuthReady(true);
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
    try {
      const data = await apiJson<{ ok: boolean; jobs?: JobSummary[] }>(`/api/jobs/${id}/delete`, { method: 'POST' });
      setHistory((prev) => data.jobs ?? prev.filter((j) => j.id !== id));
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

  const postTopic = (topic: string) =>
    apiJson<{ topics?: TopicItem[] }>('/api/sources/topics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    });

  const postJson = (path: string, payload: object, success?: string) =>
    library(path, JSON.stringify(payload), { 'Content-Type': 'application/json' }, success);

  useEffect(() => {
    if (!authReady || !user) return;
    let ignore = false;
    setNotice(null);
    setError(null);
    apiJson<{ topics?: TopicItem[] }>('/api/sources/topics')
      .then(async (data) => {
        let list = data.topics || [];
        // The default topic is permanent (the tour depends on it): recreate if missing.
        if (!list.some(isDefaultTopic)) list = (await postTopic(DEFAULT_TOPIC)).topics || list;
        if (!ignore) setTopics(list);
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

  function handleSelectPack(pack: CreatorPack) {
    if (pack.disabled) return;
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    setActivePaymentPack(pack);
  }

  async function handleConfirmMockPayment(pack: CreatorPack) {
    if (!pack.targets || pack.targets.length === 0) return;
    setClaimingPack(pack.id);
    try {
      await postJson('/api/sources/topics', { topic: pack.name, targets: pack.targets });
      setActivePaymentPack(null);
    } finally {
      setClaimingPack(null);
    }
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
            <>
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
                      <dd>{user.email ? <code>{user.email}</code> : '—'}</dd>
                      {facebookId ? (
                        <>
                          <dt>Facebook ID</dt>
                          <dd><code>{facebookId}</code></dd>
                        </>
                      ) : (
                        <>
                          <dt>Facebook</dt>
                          <dd>
                            <button
                              type="button"
                              className="link-fb-btn"
                              onClick={handleLinkFacebook}
                              disabled={linkingFb}
                            >
                              {linkingFb ? 'Đang liên kết…' : 'Liên kết tài khoản Facebook'}
                            </button>
                            {linkFbError && <div className="link-fb-error">{linkFbError}</div>}
                          </dd>
                        </>
                      )}
                    </dl>
                    <button
                      type="button"
                      className="ghost profile-btn"
                      onClick={() => {
                        setTourDismissed(false);
                        setTourReplay(true);
                      }}
                    >
                      ? Xem lại hướng dẫn
                    </button>
                    <button
                      type="button"
                      className="ghost danger profile-btn"
                      onClick={() => {
                        resetUserSessionState();
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

              {user && (
                <section className="panel">
                  <h2>Ảnh mẫu khuôn mặt & Bối cảnh</h2>
                  <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
                    Tải lên ảnh chân dung rõ mặt để AI giữ nhất quán khuôn mặt của bạn trong các video tạo ra.
                  </p>
                  <MediaPanel />
                </section>
              )}

              {user && (
                <details className="panel creator-store">
                <summary className="store-summary">
                  <div className="store-header-wrap">
                    <div>
                      <h2>Gói Content Creator</h2>
                      <p className="muted count">Nạp nhanh danh sách creator vào Thư viện để phân tích video</p>
                    </div>
                    <span className="store-toggle-icon" aria-hidden="true" />
                  </div>
                </summary>

                <div className="pack-list">
                  {CREATOR_PACKS.map((pack) => {
                    const isOwned = topics.some(
                      (t) => t.name.toLowerCase() === pack.name.toLowerCase(),
                    );
                    return (
                      <div
                        key={pack.id}
                        className={`pack-card ${pack.disabled ? 'disabled' : 'active'}`}
                        onClick={() => !pack.disabled && handleSelectPack(pack)}
                        role={pack.disabled ? undefined : 'button'}
                        tabIndex={pack.disabled ? undefined : 0}
                      >
                        <div className="pack-card-top">
                          <span className="pack-card-title">{pack.name}</span>
                        </div>

                        <p className="pack-card-desc">{pack.description}</p>

                        <div className="pack-card-bottom">
                          <button
                            type="button"
                            className={`pack-action-btn ${
                              pack.disabled ? 'disabled' : isOwned ? 'owned' : 'primary'
                            }`}
                            disabled={pack.disabled || busy || claimingPack === pack.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!pack.disabled) handleSelectPack(pack);
                            }}
                          >
                            {pack.disabled
                              ? `${pack.price} · Chưa mở bán`
                              : claimingPack === pack.id
                                ? 'Đang nạp…'
                                : isOwned
                                  ? '✓ Đã nhận (Nạp lại)'
                                  : `Nhận gói (${pack.price})`}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
                </details>
              )}
            </>
          ) : tab === 'video' ? (
            <VideoTab
              user={user}
              onOpenAuth={() => setShowAuthModal(true)}
              onGoToProfile={() => switchTab('profile')}
              prompt={videoPrompt}
              onPromptChange={setVideoPrompt}
              duration={videoDuration}
              onDurationChange={setVideoDuration}
            />
          ) : tab === 'library' ? (
            !user ? (
              <section className="panel">
                <div className="empty">
                  <span className="gate-icon">🔒</span>
                  <h2>Yêu cầu đăng nhập</h2>
                  <p className="muted">Vui lòng đăng nhập tài khoản để xem, quản lý Thư viện kênh</p>
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
                              run([topic], topic.name);
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

                          {!isDefaultTopic(topic) && (
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
                          )}
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
                              <span className="history-filename" title={cleanTopicTitle(item.filename)}>
                                {cleanTopicTitle(item.filename)}
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
                                aria-label={`Xoá lần chạy ${cleanTopicTitle(item.filename)}`}
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
                        {cleanTopicTitle(job.filename)} · {progress.done}/{progress.total} · {STATUS_LABEL[job.status]}
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
                      {sheet.source_breakdown &&
                        ((sheet.source_breakdown.glasser_api?.length ?? 0) > 0 ||
                          (sheet.source_breakdown.cache?.length ?? 0) > 0) && (
                          <div className="source-breakdown muted" style={{ fontSize: '0.82rem', margin: '0.35rem 0' }}>
                            {(sheet.source_breakdown.glasser_api?.length ?? 0) > 0 && (
                              <span title={sheet.source_breakdown.glasser_api?.join(', ')}>
                                ⚡ Glasser API: {sheet.source_breakdown.glasser_api?.length} kênh
                              </span>
                            )}
                            {(sheet.source_breakdown.glasser_api?.length ?? 0) > 0 &&
                              (sheet.source_breakdown.cache?.length ?? 0) > 0 &&
                              ' · '}
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

                      {sheet.topics.length > 0 && (() => {
                        const sortedTopics = [...sheet.topics]
                          .sort((a, b) => (b.views || 0) - (a.views || 0))
                          .slice(0, 10);
                        return (
                          <div className="topics">
                            {sortedTopics.map((topic, topicIndex) => {
                              const reelUrl = getTopicReelUrl(topic);
                              const itemKey = `${sheet.slug}-${topicIndex}`;
                              const currentMode = playerMode[itemKey] || (topic.video_url ? 'video' : 'iframe');
                              return (
                                <article className="topic reel-card" key={topicIndex}>
                                  <div className="topic-top">
                                    <div className="reel-meta-left">
                                      <span className="topic-num">#{topicIndex + 1}</span>
                                      {topic.author_handle && (
                                        <span className="reel-author">@{topic.author_handle}</span>
                                      )}
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
                                    {currentMode === 'video' && topic.video_url ? (
                                      <video
                                        src={topic.video_url}
                                        controls
                                        playsInline
                                        preload="metadata"
                                        className="reel-video-player"
                                        onError={() => {
                                          if (reelUrl) {
                                            setPlayerMode((prev) => ({ ...prev, [itemKey]: 'iframe' }));
                                          }
                                        }}
                                      />
                                    ) : reelUrl ? (
                                      <iframe
                                        src={`https://www.facebook.com/plugins/video.php?href=${encodeURIComponent(reelUrl)}&show_text=0&width=280`}
                                        title={topic.title || `Reel ${topicIndex + 1}`}
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
                                      <div className="analysis-item">
                                        <strong>🎙️ Transcript nội dung:</strong>
                                        <p className="transcript-text">
                                          {topic.transcript && topic.transcript.trim()
                                            ? topic.transcript
                                            : 'Không có lời thoại (video dạng nhạc nền / hình ảnh).'}
                                        </p>
                                      </div>
                                      {topic.why_viral && (
                                        <div className="analysis-item">
                                          <strong>🔥 Vì sao viral:</strong>
                                          <p>{topic.why_viral}</p>
                                        </div>
                                      )}
                                      {topic.hook && (
                                        <div className="analysis-item">
                                          <strong>🎣 Hook mở đầu (3s):</strong>
                                          <p className="hook-quote">“{topic.hook}”</p>
                                        </div>
                                      )}
                                      {topic.angle && (
                                        <div className="analysis-item">
                                          <strong>📐 Góc tiếp cận:</strong>
                                          <p>{topic.angle}</p>
                                        </div>
                                      )}
                                      {topic.outline && topic.outline.length > 0 && (
                                        <div className="analysis-item">
                                          <strong>📋 Dàn ý triển khai:</strong>
                                          <ol className="analysis-outline">
                                            {topic.outline.map((step, i) => (
                                              <li key={i}>{step}</li>
                                            ))}
                                          </ol>
                                        </div>
                                      )}
                                    </div>
                                  </details>

                                  <div className="reel-card-foot">
                                    <div className="reel-card-foot-left">
                                      {reelUrl && (
                                        <a
                                          href={reelUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="reel-ext-link"
                                        >
                                          Facebook ↗
                                        </a>
                                      )}
                                    </div>
                                    <button
                                      type="button"
                                      className={`copy-topic-btn ${copiedKey === `${sheet.slug}-${topicIndex}` ? 'copied' : ''}`}
                                      onClick={() => handleCopyTopic(topic, sheet.name, `${sheet.slug}-${topicIndex}`)}
                                      title="Sao chép kịch bản và mở tab Tạo Video"
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
                              );
                            })}
                          </div>
                        );
                      })()}
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
                onClick={() => run(runnable, 'Tất cả chủ đề')}
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

      {showTour && authReady && <Tour steps={TOUR_STEPS} onTab={(t) => switchTab(t as Tab)} onClose={closeTour} />}

      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />

      {activePaymentPack && (
        <div className="payment-backdrop" onClick={() => setActivePaymentPack(null)}>
          <div className="payment-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="payment-sheet-head">
              <div className="payment-sheet-title">
                <span style={{ fontSize: 20 }}>🛒</span>
                <h3>Xác nhận giao dịch In-App (Mock)</h3>
              </div>
              <button
                type="button"
                className="payment-close-btn"
                aria-label="Đóng"
                onClick={() => setActivePaymentPack(null)}
              >
                ✕
              </button>
            </div>

            <p className="muted" style={{ fontSize: 13, margin: '0 0 10px' }}>
              Mô phỏng thanh toán in-app để nạp gói creator vào Thư viện tài khoản.
            </p>

            <div className="payment-receipt-box">
              <div className="payment-receipt-row">
                <span className="muted">Tài khoản</span>
                <strong>{user ? user.displayName || user.email || user.uid : 'Khách'}</strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">Gói creator</span>
                <strong>{activePaymentPack.name}</strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">Số lượng kênh</span>
                <strong>
                  {activePaymentPack.countLabel ||
                    (activePaymentPack.count ? `${formatNumber(activePaymentPack.count)} creator Facebook` : 'Bảo trì hàng tháng')}
                </strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">Phương thức</span>
                <span>In-App Mock Purchase</span>
              </div>
              <div className="payment-receipt-row total">
                <span>Tổng thanh toán</span>
                <span style={{ color: 'var(--green)', fontWeight: 800 }}>{activePaymentPack.price}</span>
              </div>
            </div>

            <div className="payment-sheet-buttons">
              <button
                type="button"
                className="ghost"
                onClick={() => setActivePaymentPack(null)}
                disabled={claimingPack === activePaymentPack.id}
              >
                Huỷ
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => handleConfirmMockPayment(activePaymentPack)}
                disabled={claimingPack === activePaymentPack.id}
              >
                {claimingPack === activePaymentPack.id ? 'Đang nạp kênh…' : 'Xác nhận nạp gói (0$)'}
              </button>
            </div>
          </div>
        </div>
      )}
    </IonPage>
  );
};

export default Home;
