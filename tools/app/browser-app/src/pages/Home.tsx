import { IonContent, IonFooter, IonHeader, IonIcon, IonPage } from '@ionic/react';
import { analyticsOutline, libraryOutline, personCircleOutline, videocamOutline } from 'ionicons/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { JobResult } from '../analysis/JobResult';
import {
  cleanTopicTitle,
  copyToClipboard,
  formatNumber,
  formatTime,
  formatTopicForAI,
  STATUS_LABEL,
  TERMINAL,
} from '../analysis/format';
import type { Job, JobKind, JobSummary, Topic } from '../analysis/types';
import { apiFetch, apiJson } from '../api';
import { AuthModal } from '../components/AuthModal';
import { MediaPanel } from '../components/MediaPanel';
import { Tour, type TourStep } from '../components/Tour';
import { VideoTab } from '../components/VideoTab';
import { CREATOR_PACKS, type CreatorPack } from '../data/creatorPacks';
import { auth, FacebookAuthProvider, linkWithPopup, onAuthStateChanged, signOut, type User } from '../firebase';
import './Home.css';

export type TargetItem = { name: string; url: string };
export type TopicItem = { name: string; slug: string; targets: TargetItem[] };
export type SavedReel = {
  id: string;
  reel_url: string;
  original_url?: string;
  platform: string;
  share_type: string;
  sender_name?: string;
  message_text?: string;
  created_at: string;
};
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
  {
    tab: 'library',
    target: '.tabbar-btn:nth-child(1)',
    title: 'Thư viện',
    text: 'Nơi lưu các chủ đề và kênh creator bạn muốn theo dõi.',
  },
  {
    tab: 'library',
    target: '#import',
    title: 'Nhập dữ liệu',
    text: 'Chọn file Excel hoặc dán link Google Sheet — mỗi sheet thành một chủ đề.',
  },
  {
    tab: 'library',
    target: '.topic-accordion',
    title: 'Chủ đề mặc định',
    text: 'Mở chủ đề để thêm/xoá kênh, hoặc bấm ▶ Chạy để phân tích riêng chủ đề này.',
  },
  {
    tab: 'library',
    target: '.new-topic',
    title: 'Tạo chủ đề mới',
    text: 'Nhập tên chủ đề và (tuỳ chọn) link kênh đầu tiên.',
  },
  {
    tab: 'library',
    target: '.topics-panel .primary',
    title: 'Chạy tất cả',
    text: 'Phân tích mọi chủ đề trong thư viện cùng lúc.',
  },
  {
    tab: 'analyzer',
    target: '.tabbar-btn:nth-child(2)',
    title: 'Phân tích',
    text: 'Xem tiến độ, lịch sử và kết quả ý tưởng viral. Dùng "Copy cho AI" để lấy kịch bản.',
  },
  {
    tab: 'video',
    target: '.tabbar-btn:nth-child(3)',
    title: 'Tạo Video AI',
    text: 'Tạo video ngắn 10 giây với khuôn mặt mẫu và giọng đọc tiếng Việt tự nhiên.',
  },
  {
    tab: 'profile',
    target: '.tabbar-btn:nth-child(4)',
    title: 'Hồ sơ',
    text: 'Đăng nhập/đăng xuất, nạp gói creator và quản lý ảnh mẫu khuôn mặt.',
  },
];

const EXCEL_ACCEPT =
  '.xlsx,.xlsm,.xls,.gsheet,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.google-apps.spreadsheet';

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
  const isTranscribe = false;
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const [history, setHistory] = useState<JobSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
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

  // Collapsible Topics & Saved Reels (dm_service feature)
  const [topicsCollapsed, setTopicsCollapsed] = useState(false);
  const [mediaCollapsed, setMediaCollapsed] = useState(false);
  const [savedReels, setSavedReels] = useState<SavedReel[]>([]);
  const [loadingReels, setLoadingReels] = useState(false);
  const [savedReelsCollapsed, setSavedReelsCollapsed] = useState(false);

  function resetUserSessionState() {
    setTourDismissed(false);
    setTourReplay(false);
    setTopics([]);
    setTopicsCollapsed(false);
    setSavedReels([]);
    setLoadingReels(false);
    setSavedReelsCollapsed(false);
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

  const fetchSavedReels = async () => {
    if (!user) return;
    setLoadingReels(true);
    try {
      const res = await apiJson<{ ok: boolean; reels: SavedReel[] }>('/api/saved-reels');
      setSavedReels(res.reels || []);
    } catch (err) {
      console.error('Failed to load saved reels:', err);
    } finally {
      setLoadingReels(false);
    }
  };

  const handleDeleteSavedReel = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Xoá Reel này khỏi danh sách đã lưu?')) return;
    try {
      await apiJson('/api/saved-reels/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      setSavedReels((prev) => prev.filter((r) => r.id !== id));
      setNotice({ type: 'success', text: 'Đã xoá Reel khỏi danh sách.' });
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err) });
    }
  };

  const handleRunSavedReel = (reel: SavedReel) => {
    const item: TopicItem = {
      name: reel.reel_url,
      slug: `saved-reel-${reel.id}`,
      targets: [{ name: reel.message_text ? reel.message_text.slice(0, 40) : reel.reel_url, url: reel.reel_url }],
    };
    run([item], reel.reel_url, 'reel');
  };

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

    apiJson<{ ok: boolean; reels: SavedReel[] }>('/api/saved-reels')
      .then((data) => {
        if (!ignore) setSavedReels(data.reels || []);
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

  async function run(selected: TopicItem[], filename: string, kind: JobKind = 'profile') {
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    setError(null);
    setStarting(true);
    setJob(null);
    switchTab('analyzer');
    try {
      const params = new URLSearchParams({ job_kind: kind });
      if (isTranscribe) params.set('transcribe', '1');
      const endpoint = `/api/jobs?${params.toString()}`;
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
                          <dd>
                            <code>{facebookId}</code>
                          </dd>
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
                  <div
                    className="panel-head collapsible-head"
                    role="button"
                    tabIndex={0}
                    aria-expanded={!mediaCollapsed}
                    onClick={() => setMediaCollapsed((v) => !v)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setMediaCollapsed((v) => !v);
                      }
                    }}
                  >
                    <div>
                      <h2>Ảnh mẫu khuôn mặt & Bối cảnh</h2>
                      <p className="muted profile-media-desc">
                        Tải lên ảnh chân dung rõ mặt để AI giữ nhất quán khuôn mặt của bạn trong các video tạo ra.
                      </p>
                    </div>
                    <span className={`store-toggle-icon ${!mediaCollapsed ? 'open' : ''}`} aria-hidden="true" />
                  </div>
                  {!mediaCollapsed && (
                    <div style={{ marginTop: 'var(--space-3)' }}>
                      <MediaPanel />
                    </div>
                  )}
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
                      const isOwned = topics.some((t) => t.name.toLowerCase() === pack.name.toLowerCase());
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
                  {notice && <div className={`alert ${notice.type}`}>{notice.text}</div>}
                </section>

                <section className="panel topics-panel">
                  <button
                    className="primary"
                    type="button"
                    onClick={() => run(runnable, 'Tất cả chủ đề')}
                    disabled={blocked || runnable.length === 0}
                    style={{ marginBottom: 'var(--space-3)' }}
                  >
                    {running ? 'Đang chạy…' : `▶ Chạy tất cả (${runnable.length} chủ đề)`}
                  </button>

                  <div
                    className="panel-head collapsible-head"
                    role="button"
                    tabIndex={0}
                    onClick={() => setTopicsCollapsed((v) => !v)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setTopicsCollapsed((v) => !v);
                      }
                    }}
                  >
                    <div>
                      <h2>Chủ đề</h2>
                      <span className="muted count">
                        {topics.length} chủ đề · {totalChannels} kênh
                      </span>
                    </div>
                    <span className={`store-toggle-icon ${!topicsCollapsed ? 'open' : ''}`} aria-hidden="true" />
                  </div>

                  {!topicsCollapsed && (
                    <>
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
                    </>
                  )}
                </section>

                <div className="panel saved-reels-panel">
                  <div
                    className="panel-head collapsible-head"
                    role="button"
                    tabIndex={0}
                    onClick={() => setSavedReelsCollapsed((v) => !v)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSavedReelsCollapsed((v) => !v);
                      }
                    }}
                  >
                    <div>
                      <h2>Reel đã lưu</h2>
                      <span className="muted count">{savedReels.length} reel</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <button
                        type="button"
                        className="ghost small"
                        onClick={(e) => {
                          e.stopPropagation();
                          fetchSavedReels();
                        }}
                        disabled={loadingReels}
                        title="Làm mới danh sách Reel"
                      >
                        {loadingReels ? '…' : '↻'}
                      </button>
                      <span className={`store-toggle-icon ${!savedReelsCollapsed ? 'open' : ''}`} aria-hidden="true" />
                    </div>
                  </div>

                  {!savedReelsCollapsed && (
                    <div className="saved-reels-body" style={{ marginTop: 'var(--space-3)' }}>
                      {savedReels.length === 0 ? (
                        <div className="empty" style={{ padding: 'var(--space-3) 0 0' }}>
                          <p className="muted" style={{ fontSize: 'var(--text-xs)', margin: 0 }}>
                            Chưa có Reel nào được lưu.
                          </p>
                        </div>
                      ) : (
                        <div className="saved-reels-list" style={{ marginTop: 'var(--space-2)' }}>
                          {savedReels.map((reel) => (
                            <div key={reel.id} className="channel-card saved-reel-card">
                              <div className="channel-info">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span className="reel-platform-tag">{reel.platform || 'reel'}</span>
                                  <span className="muted" style={{ fontSize: '11px' }}>
                                    {formatTime(reel.created_at)}
                                  </span>
                                </div>
                                <a
                                  href={reel.reel_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="channel-link"
                                  title={reel.reel_url}
                                >
                                  {shortUrl(reel.reel_url)} ↗
                                </a>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <button
                                  type="button"
                                  className="ghost small"
                                  style={{ padding: '4px 8px', fontSize: '12px' }}
                                  onClick={() => handleRunSavedReel(reel)}
                                  disabled={blocked}
                                  title="Phân tích Reel này"
                                >
                                  ▶ Phân tích
                                </button>
                                <button
                                  type="button"
                                  className="channel-del-btn"
                                  aria-label="Xoá Reel này"
                                  onClick={(e) => handleDeleteSavedReel(reel.id, e)}
                                  title="Xoá Reel"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
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
                <JobResult
                  job={job}
                  historyCount={history.length}
                  copiedKey={copiedKey}
                  onBack={() => selectJob(null)}
                  onCopyTopic={handleCopyTopic}
                />
              )}
            </section>
          )}
        </div>
      </IonContent>

      <IonFooter className="ion-no-border">
        {running && (
          <div className="actionbar">
            <button className="ghost danger" type="button" onClick={cancel}>
              Dừng
            </button>
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
                <span className="payment-cart-icon">🛒</span>
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

            <p className="muted payment-subtext">
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
                    (activePaymentPack.count
                      ? `${formatNumber(activePaymentPack.count)} creator Facebook`
                      : 'Bảo trì hàng tháng')}
                </strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">Phương thức</span>
                <span>In-App Mock Purchase</span>
              </div>
              <div className="payment-receipt-row total">
                <span>Tổng thanh toán</span>
                <span className="payment-price-tag">{activePaymentPack.price}</span>
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
