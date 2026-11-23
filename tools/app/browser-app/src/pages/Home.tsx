import { IonContent, IonFooter, IonHeader, IonIcon, IonPage, IonToast } from '@ionic/react';
import { analyticsOutline, libraryOutline, personCircleOutline, refreshOutline, videocamOutline } from 'ionicons/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { copyToClipboard, formatNumber, formatTime, formatTopicForAI, TERMINAL } from '../analysis/format';
import type { Job, JobKind, JobSummary, Topic } from '../analysis/types';
import { apiFetch, apiJson } from '../api';
import { setAssistantMode, setBrandAssistantUser } from '../brandAssistantStore';
import { BRAND_PROFILE_KEY, cacheBrandProfile } from '../brandProfile';
import { AnalyzerTab } from '../components/AnalyzerTab';
import { AuthModal } from '../components/AuthModal';
import { BrandPanel } from '../components/BrandPanel';
import { MediaPanel } from '../components/MediaPanel';
import { Tour, type TourStep } from '../components/Tour';
import { VideoTab } from '../components/VideoTab';
import { CREATOR_PACKS, type CreatorPack } from '../data/creatorPacks';
import {
  auth,
  onAuthStateChanged,
  signOut,
  type User,
} from '../firebase';
import { getMessages, useLocale, type LocaleMessages } from '../locales';
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
  topic?: string;
  created_at: string;
};
type Tab = 'library' | 'analyzer' | 'video' | 'profile';

const TAB_ICONS: Record<Tab, string> = {
  library: libraryOutline,
  analyzer: analyticsOutline,
  video: videocamOutline,
  profile: personCircleOutline,
};

const DEFAULT_TOPIC = 'sở thích cá nhân';
const isDefaultTopic = (t: TopicItem) => t.name.toLowerCase() === DEFAULT_TOPIC;
const TOUR_KEY = 'aibrand-tour-done';
const TOUR_DEMO_ID = '__tour_demo__';
const TOUR_DEMO_TOPIC_SLUG = '__tour_demo_topic__';

function usePersistedCollapsed(key: string) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(key) === '1';
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      if (collapsed) localStorage.setItem(key, '1');
      else localStorage.removeItem(key);
    } catch {
      // ignore storage errors
    }
  }, [key, collapsed]);
  return [collapsed, setCollapsed] as const;
}

function buildTourDemoTopic(m: LocaleMessages['tour']): TopicItem {
  return {
    name: m.demoTitle,
    slug: TOUR_DEMO_TOPIC_SLUG,
    targets: [{ name: m.demoChannelName, url: 'https://www.facebook.com/example' }],
  };
}

function buildTourDemoJob(m: LocaleMessages['tour']): Job {
  return {
    id: TOUR_DEMO_ID,
    job_kind: 'profile',
    status: 'completed',
    filename: m.demoTitle,
    created_at: new Date().toISOString(),
    current_sheet: null,
    sheets: [
      {
        name: m.demoTitle,
        slug: 'huong-dan',
        status: 'completed',
        targets: 1,
        reels: 12,
        pool_distribution: { pool_3: 3, pool_2: 5, pool_1: 4 },
        topics: [
          {
            title: m.demoTopicTitle,
            hook: m.demoTopicHook,
            angle: m.demoTopicAngle,
            why_viral: m.demoTopicWhyViral,
            outline: m.demoTopicOutline,
            format: 'Short talking-head',
            source_urls: [],
            generated_by: 'sample',
            views: 125000,
            velocity_per_hour: 4200,
            current_pool: 3,
            author_handle: '@creator_mau',
            transcript: m.demoTopicTranscript,
            prompt: m.demoTopicPrompt,
          },
        ],
        error: null,
      },
    ],
    logs: [],
  };
}

function buildTourDemoSummary(m: LocaleMessages['tour'], createdAt: string): JobSummary {
  return {
    id: TOUR_DEMO_ID,
    job_kind: 'profile',
    status: 'completed',
    filename: m.demoTitle,
    created_at: createdAt,
    finished_at: createdAt,
    current_sheet: null,
    total_sheets: 1,
    completed_sheets: 1,
    total_topics: 1,
  };
}

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
  const { locale, toggleLocale, t } = useLocale();
  const location = useLocation();
  const query = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const initialJobId = query.get('job_id') || localStorage.getItem('aibrand-active-job-id');
  const [tab, setTab] = useState<Tab>(
    query.get('tab') === 'profile'
      ? 'profile'
      : query.get('tab') === 'video'
        ? 'video'
        : query.get('tab') === 'library'
          ? 'library'
          : 'analyzer',
  );

  // Library (backend is the source of truth)
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [search, setSearch] = useState('');
  const [keyword, setKeyword] = useState('');
  const [sheetUrl, setSheetUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [inlineUrls, setInlineUrls] = useState<Record<string, string>>({});
  const [newTopic, setNewTopic] = useState({ name: '', url: '' });
  const [newReelTopic, setNewReelTopic] = useState('reels từ facebook');
  const [newReelUrl, setNewReelUrl] = useState('');
  const [inlineReelUrls, setInlineReelUrls] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  // Analyzer
  const isTranscribe = false;
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const [history, setHistory] = useState<JobSummary[]>([]);
  const [syncing, setSyncing] = useState(false);
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
  // Seen-flag is per account: tour always shows unless the user marks "Đã rõ hướng dẫn" in Profile.
  const [tourDismissed, setTourDismissed] = useState(false);
  const [tourHistoryView, setTourHistoryView] = useState(false);
  const [, setTourSync] = useState(0);
  const [videoBalance, setVideoBalance] = useState<number | null>(null);

  const tourDemoTopic = useMemo(() => buildTourDemoTopic(t.tour), [t.tour]);
  const tourDemoJob = useMemo(() => buildTourDemoJob(t.tour), [t.tour]);
  const tourDemoSummary = useMemo(
    () => buildTourDemoSummary(t.tour, tourDemoJob.created_at!),
    [t.tour, tourDemoJob.created_at],
  );

  const tourKey = user ? `${TOUR_KEY}-${user.uid}` : '';
  const tourDone = Boolean(tourKey && localStorage.getItem(tourKey));
  const showTour = !!user && !tourDismissed && !tourDone;
  const visibleHistory = showTour ? [tourDemoSummary, ...history] : history;
  const tourSteps = useMemo<TourStep[]>(() => {
    const s = t.tour.steps;
    const showChat = () => {
      setTourHistoryView(false);
      setAssistantMode('brand_setup');
      setJobId(null);
      setJob(null);
    };
    const showHistoryList = () => {
      setTourHistoryView(true);
      setJobId(null);
      setJob(null);
    };
    const showDemoResult = () => {
      setTourHistoryView(true);
      setJobId(TOUR_DEMO_ID);
      setJob(tourDemoJob);
    };
    return [
      {
        tab: 'analyzer',
        target: '.tabbar-btn:nth-child(1)',
        title: s.analyzerTitle,
        text: s.analyzerText,
        onEnter: showChat,
      },
      {
        tab: 'analyzer',
        target: '#brand-assistant .brand-mode-tabs',
        title: s.brandModesTitle,
        text: s.brandModesText,
        onEnter: showChat,
      },
      {
        tab: 'analyzer',
        target: '#brand-assistant .brand-chat-form',
        title: s.brandChatTitle,
        text: s.brandChatText,
        onEnter: showChat,
      },
      {
        tab: 'analyzer',
        target: '#results-analysis .history-list .history-card:first-child',
        title: s.demoHistoryTitle,
        text: s.demoHistoryText,
        onEnter: showHistoryList,
      },
      {
        tab: 'analyzer',
        target: '.reel-analysis-details',
        title: s.transcriptTitle,
        text: s.transcriptText,
        onEnter: showDemoResult,
      },
      {
        tab: 'analyzer',
        target: '.copy-topic-btn',
        title: s.copyPromptTitle,
        text: s.copyPromptText,
        onEnter: showDemoResult,
      },
      {
        tab: 'library',
        target: '.tabbar-btn:nth-child(2)',
        title: s.libraryTitle,
        text: s.libraryText,
        onEnter: showChat,
      },
      {
        tab: 'library',
        target: '.new-topic',
        title: s.newTopicTitle,
        text: s.newTopicText,
      },
      {
        tab: 'library',
        target: '.topic-accordion:first-of-type',
        title: s.topicAccordionTitle,
        text: s.topicAccordionText,
      },
      {
        tab: 'library',
        target: '.saved-reels-panel',
        title: s.savedReelsTitle,
        text: s.savedReelsText,
      },
      {
        tab: 'video',
        target: '.tabbar-btn:nth-child(3)',
        title: s.videoTitle,
        text: s.videoText,
      },
      {
        tab: 'video',
        target: '.video-tab > section.panel',
        tipTarget: '.video-tab .prompt-textarea',
        title: s.videoFormTitle,
        text: s.videoFormText,
      },
      {
        tab: 'profile',
        target: '.tabbar-btn:nth-child(4)',
        title: s.profileTitle,
        text: s.profileText,
      },
      {
        tab: 'profile',
        target: 'section.panel.profile',
        title: s.accountTitle,
        text: s.accountText,
      },
      {
        tab: 'profile',
        target: '#brand-profile',
        title: s.brandProfileTitle,
        text: s.brandProfileText,
        onEnter: () => setBrandCollapsed(false),
      },
      {
        tab: 'profile',
        target: '.media-section .profile-card .profile-info',
        title: s.avatarTitle,
        text: s.avatarText,
        onEnter: () => setMediaCollapsed(false),
      },
      {
        tab: 'profile',
        target: '.creator-store',
        title: s.storeTitle,
        text: s.storeText,
      },
    ];
  }, [t.tour.steps, tourDemoJob]);
  const closeTour = () => {
    setTourDismissed(true);
    setTourHistoryView(false);
    if (jobId === TOUR_DEMO_ID) selectJob(null);
  };
  const toggleTourDone = () => {
    if (!tourKey) return;
    if (tourDone) {
      localStorage.removeItem(tourKey);
      setTourDismissed(false);
    } else {
      localStorage.setItem(tourKey, '1');
    }
    setTourSync((v) => v + 1);
  };

  useEffect(() => {
    setBrandAssistantUser(user?.uid ?? null);
  }, [user?.uid]);

  useEffect(() => {
    if (!user || tab !== 'profile') return;
    let cancelled = false;
    apiJson<{ ok: boolean; balance: number }>('/api/credits')
      .then((res) => {
        if (!cancelled && res.ok && typeof res.balance === 'number') setVideoBalance(res.balance);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [user, tab]);

  // In-App Payment Mock
  const [activePaymentPack, setActivePaymentPack] = useState<CreatorPack | null>(null);
  const [claimingPack, setClaimingPack] = useState<string | null>(null);

  // Collapsible Topics & Saved Reels (dm_service feature)
  const [topicsCollapsed, setTopicsCollapsed] = useState(false);
  const [brandCollapsed, setBrandCollapsed] = usePersistedCollapsed('aibrand-profile-brand-collapsed');
  const [mediaCollapsed, setMediaCollapsed] = usePersistedCollapsed('aibrand-profile-media-collapsed');
  const [savedReels, setSavedReels] = useState<SavedReel[]>([]);
  const [savedReelsCollapsed, setSavedReelsCollapsed] = useState(false);
  const [fbName, setFbName] = useState<string | null | undefined>(undefined);
  const [linkCode, setLinkCode] = useState<{ command: string; page_id: string } | null>(null);
  const [generatingLinkCode, setGeneratingLinkCode] = useState(false);

  function resetUserSessionState() {
    setTourDismissed(false);
    setVideoBalance(null);
    setTopics([]);
    setTopicsCollapsed(false);
    setSavedReels([]);
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
    localStorage.removeItem(BRAND_PROFILE_KEY);
    cacheBrandProfile(null);
    setBrandAssistantUser(null);
  }

  const fetchSavedReels = async () => {
    if (!user) return;
    try {
      const [reelsRes, statusRes] = await Promise.all([
        apiJson<{ ok: boolean; reels: SavedReel[] }>('/api/saved-reels'),
        apiJson<{ ok: boolean; linked: boolean; fb_name?: string }>('/api/facebook/status').catch(() => null),
      ]);
      setSavedReels(reelsRes.reels || []);
      if (statusRes) {
        setFbName(statusRes.linked ? statusRes.fb_name || 'Messenger' : null);
        if (statusRes.linked) setLinkCode(null);
      }
    } catch (err) {
      console.error('Failed to load saved reels:', err);
    }
  };

  const handleGenerateLinkCode = async () => {
    setGeneratingLinkCode(true);
    try {
      const res = await apiJson<{ ok: boolean; command: string; page_id: string }>('/api/facebook/link-code', {
        method: 'POST',
      });
      setLinkCode({ command: res.command, page_id: res.page_id });
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err) });
    } finally {
      setGeneratingLinkCode(false);
    }
  };

  const handleDeleteSavedReel = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(t.library.deleteReelConfirm)) return;
    try {
      await apiJson('/api/saved-reels/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      setSavedReels((prev) => prev.filter((r) => r.id !== id));
      setNotice({ type: 'success', text: t.library.deletedReelNotice });
    } catch (err) {
      setNotice({ type: 'error', text: errorText(err) });
    }
  };

  const handleDeleteSavedReelTopic = async (topicName: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t.library.deleteReelTopicConfirm(topicName))) return;
    try {
      await apiJson('/api/saved-reels/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topicName }),
      });
      setSavedReels((prev) => prev.filter((r) => ((r.topic || '').trim() || 'reels từ facebook') !== topicName));
      setNotice({ type: 'success', text: t.library.deletedReelTopicNotice(topicName) });
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
    if (id === TOUR_DEMO_ID) {
      setJob(tourDemoJob);
      window.history.replaceState(null, '', `?tab=${tab}`);
      return;
    }
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
    try {
      const data = await apiJson<{ ok: boolean; jobs: JobSummary[] }>('/api/jobs');
      const jobs = data.jobs || [];
      setHistory(jobs);
      return jobs;
    } catch {
      return [];
    }
  }

  async function syncAll() {
    if (!user || syncing) return;
    setSyncing(true);
    try {
      const reloadTopics = apiJson<{ topics?: TopicItem[] }>('/api/sources/topics')
        .then(async (data) => {
          let list = data.topics || [];
          if (!list.some(isDefaultTopic)) list = (await postTopic(DEFAULT_TOPIC)).topics || list;
          setTopics(list);
        })
        .catch(() => {});
      const reloadActiveJob =
        jobId && jobId !== TOUR_DEMO_ID
          ? apiJson<{ ok: boolean; job: Job }>(`/api/jobs/${jobId}`)
              .then((data) => setJob(data.job))
              .catch(() => {})
          : Promise.resolve();
      await Promise.all([reloadTopics, fetchHistory(), fetchSavedReels(), reloadActiveJob]);
    } finally {
      setSyncing(false);
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
      alert(t.analyzer.deleteErrorAlert(errorText(err)));
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
        if (!ignore) setNotice({ type: 'error', text: getMessages().library.loadError(errorText(err)) });
      });

    apiJson<{ ok: boolean; jobs: JobSummary[] }>('/api/jobs')
      .then((data) => {
        if (ignore) return;
        const jobs = data.jobs || [];
        setHistory(jobs);
        const activeRunning = jobs.find((j) => !TERMINAL.has(j.status));
        const storedId = query.get('job_id') || localStorage.getItem('aibrand-active-job-id');
        const targetId = storedId || activeRunning?.id;
        if (targetId && !showTour) {
          selectJob(targetId);
        }
      })
      .catch(() => {});

    apiJson<{ ok: boolean; reels: SavedReel[] }>('/api/saved-reels')
      .then((data) => {
        if (!ignore) setSavedReels(data.reels || []);
      })
      .catch(() => {});

    apiJson<{ ok: boolean; linked: boolean; fb_name?: string }>('/api/facebook/status')
      .then((data) => {
        if (!ignore) {
          setFbName(data.linked ? data.fb_name || 'Messenger' : null);
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
    if (jobId === TOUR_DEMO_ID) {
      setJob(tourDemoJob);
      return;
    }
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

  const visibleTopics = useMemo(
    () => (showTour ? [tourDemoTopic, ...topics] : topics),
    [showTour, tourDemoTopic, topics],
  );
  const filteredTopics = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return visibleTopics;
    return visibleTopics.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.targets.some((tg) => tg.name.toLowerCase().includes(q) || tg.url.toLowerCase().includes(q)),
    );
  }, [visibleTopics, search]);

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
      t.library.importSuccess,
    ).then((ok) => ok && isUrl && setSheetUrl(''));
  }

  async function addChannel(topic: string, url: string) {
    if (!user) {
      setShowAuthModal(true);
      return false;
    }
    return postJson('/api/sources/topics', { topic, url }, t.library.addChannelSuccess(topic));
  }

  async function handleAddCreator(creator: { name: string; url: string; platform?: string }) {
    if (!user) {
      setShowAuthModal(true);
      return;
    }
    const topicName = job?.filename || t.library.savedChannelsTopic;
    await postJson(
      '/api/sources/topics',
      { topic: topicName, url: creator.url, channel_name: creator.name },
      t.library.addCreatorSuccess(creator.name, topicName),
    );
  }

  async function saveReelToTopic(
    reelUrl: string,
    topicName: string,
    extra?: { platform?: string; title?: string; sender_name?: string },
  ) {
    if (!user) {
      setShowAuthModal(true);
      return false;
    }
    const url = reelUrl.trim();
    if (!url) return false;
    const resolvedTopic = topicName.trim() || 'reels từ facebook';
    await apiJson('/api/saved-reels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reel_url: url,
        topic: resolvedTopic,
        ...(extra || {}),
      }),
    });
    setNotice({ type: 'success', text: t.library.savedReelNotice(resolvedTopic) });
    fetchSavedReels();
    return true;
  }

  async function handleSaveVideo(topic: Topic) {
    const reelUrl = topic.reel_url || topic.source_urls?.[0] || '';
    if (!reelUrl) return;
    await saveReelToTopic(reelUrl, job?.filename || 'reels từ facebook', {
      platform: topic.platform || 'facebook',
      title: topic.title,
      sender_name: topic.author_name || topic.author_handle || topic.title,
    });
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
          <div className="topbar-actions">
            {user && (
              <button
                type="button"
                className="topbar-reload-btn"
                onClick={() => void syncAll()}
                disabled={syncing}
                aria-label={t.common.refresh}
                title={t.common.refresh}
              >
                <IonIcon icon={refreshOutline} className={syncing ? 'spin' : undefined} aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              className="lang-toggle-btn"
              onClick={toggleLocale}
              aria-label={t.profile.switchLanguage}
              title={t.profile.switchLanguage}
            >
              <span aria-hidden="true">{locale === 'vi' ? '🇻🇳' : '🇺🇸'}</span>
              <span>{locale === 'vi' ? 'VI' : 'EN'}</span>
            </button>
          </div>
        </div>
      </IonHeader>

      <IonContent>
        <div className="ab-page">
          {!authReady ? (
            <div className="empty">
              <p className="muted">{t.authGate.checking}</p>
            </div>
          ) : !user ? (
            <section className="panel" id={tab === 'analyzer' ? 'results' : undefined}>
              <div className="empty">
                <span className="gate-icon">🔒</span>
                <h2>{t.authGate.title}</h2>
                <p className="muted">{t.authGate.subtitles[tab] ?? t.authGate.defaultSubtitle}</p>
                <button type="button" className="primary auth-gate-btn" onClick={() => setShowAuthModal(true)}>
                  {t.authGate.button}
                </button>
              </div>
            </section>
          ) : tab === 'profile' ? (
            <>
              <section className="panel profile">
                <div className="profile-head">
                  <span className="avatar">{(user.email || user.uid)[0].toUpperCase()}</span>
                  <div className="sheet-title">
                    <strong>{user.displayName || user.email || t.profile.defaultUser}</strong>
                  </div>
                </div>
                <dl className="details">
                  <dt>{t.profile.email}</dt>
                  <dd>{user.email ? <code>{user.email}</code> : '—'}</dd>
                  <dt>{t.profile.facebook}</dt>
                  <dd>
                    {fbName === undefined ? (
                      '—'
                    ) : fbName ? (
                      <span className="badge completed">✓ {fbName}</span>
                    ) : (
                      <button
                        type="button"
                        className="link-fb-btn"
                        onClick={handleGenerateLinkCode}
                        disabled={generatingLinkCode}
                      >
                        {generatingLinkCode ? t.library.linkMessengerLoading : t.library.linkMessengerBtn}
                      </button>
                    )}
                  </dd>
                  {videoBalance !== null && (
                    <>
                      <dt>{t.profile.videoBalance}</dt>
                      <dd>
                        <code>${(videoBalance / 1000000).toFixed(2)}</code>
                      </dd>
                    </>
                  )}
                </dl>
                <button
                  type="button"
                  className={`${tourDone ? 'primary' : 'ghost'} profile-btn`}
                  aria-pressed={tourDone}
                  onClick={toggleTourDone}
                >
                  {tourDone ? t.profile.tourDoneChecked : t.profile.tourDoneUnchecked}
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
                  {t.profile.signOut}
                </button>
              </section>

              <section className="panel" id="brand-profile">
                <div
                  className="panel-head collapsible-head"
                  role="button"
                  tabIndex={0}
                  aria-expanded={!brandCollapsed}
                  onClick={() => setBrandCollapsed((v) => !v)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setBrandCollapsed((v) => !v);
                    }
                  }}
                >
                  <div>
                    <h2>{t.profile.brandTitle}</h2>
                    <p className="muted profile-media-desc">{t.profile.brandDesc}</p>
                  </div>
                  <span className={`store-toggle-icon ${!brandCollapsed ? 'open' : ''}`} aria-hidden="true" />
                </div>
                {!brandCollapsed && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <BrandPanel />
                  </div>
                )}
              </section>

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
                    <h2>{t.profile.mediaTitle}</h2>
                    <p className="muted profile-media-desc">{t.profile.mediaDesc}</p>
                  </div>
                  <span className={`store-toggle-icon ${!mediaCollapsed ? 'open' : ''}`} aria-hidden="true" />
                </div>
                {!mediaCollapsed && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <MediaPanel />
                  </div>
                )}
              </section>

              <details className="panel creator-store">
                <summary className="store-summary">
                  <div className="store-header-wrap">
                    <div>
                      <h2>{t.profile.storeTitle}</h2>
                      <p className="muted count">{t.profile.storeDesc}</p>
                    </div>
                    <span className="store-toggle-icon" aria-hidden="true" />
                  </div>
                </summary>

                <div className="pack-list">
                  {CREATOR_PACKS.map((pack) => {
                    const isOwned = topics.some((tItem) => tItem.name.toLowerCase() === pack.name.toLowerCase());
                    const packLoc = t.creatorPacks[pack.id];
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

                        <p className="pack-card-desc">{packLoc?.description ?? pack.description}</p>

                        <div className="pack-card-bottom">
                          <button
                            type="button"
                            className={`pack-action-btn ${pack.disabled ? 'disabled' : isOwned ? 'owned' : 'primary'}`}
                            disabled={pack.disabled || busy || claimingPack === pack.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!pack.disabled) handleSelectPack(pack);
                            }}
                          >
                            {pack.disabled
                              ? t.profile.packDisabled(pack.price)
                              : claimingPack === pack.id
                                ? t.profile.packClaiming
                                : isOwned
                                  ? t.profile.packOwned
                                  : t.profile.packGet(pack.price)}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </details>

              <details className="panel creator-store">
                <summary className="store-summary">
                  <div className="store-header-wrap">
                    <div>
                      <h2>{t.profile.contributorsTitle}</h2>
                      <p className="muted count">{t.profile.contributorsDesc}</p>
                    </div>
                    <span className="store-toggle-icon" aria-hidden="true" />
                  </div>
                </summary>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-5)' }}>
                  <li>Christine Erispe</li>
                </ul>
              </details>
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
            <>
              <section className="panel" id="import">
                <h2>{t.library.importTitle}</h2>
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
                    <strong>{busy ? t.common.processing : t.library.chooseExcel}</strong>
                    <small className="muted">{t.library.excelHint}</small>
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
                    placeholder={t.library.sheetPlaceholder}
                    aria-label={t.library.sheetAria}
                    value={sheetUrl}
                    onChange={(e) => setSheetUrl(e.target.value)}
                  />
                  <button type="submit" className="ghost" disabled={busy || !sheetUrl.trim()}>
                    {t.library.importBtn}
                  </button>
                </form>
              </section>

              <section className="panel topics-panel">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => run(runnable, t.library.allTopicsFilename)}
                  disabled={blocked || runnable.length === 0}
                  style={{ width: '100%', marginBottom: 'var(--space-3)' }}
                >
                  {running ? t.library.runningBtn : t.library.runAllBtn(runnable.length)}
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
                    <h2>{t.library.topicsTitle}</h2>
                    <span className="muted count">{t.library.topicsCount(topics.length, totalChannels)}</span>
                  </div>
                  <span className={`store-toggle-icon ${!topicsCollapsed ? 'open' : ''}`} aria-hidden="true" />
                </div>

                {!topicsCollapsed && (
                  <>
                    <input
                      type="search"
                      className="text-input search-input"
                      placeholder={t.library.searchPlaceholder}
                      aria-label={t.library.searchAria}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />

                    {filteredTopics.length === 0 ? (
                      <p className="muted empty">{topics.length ? t.library.noSearchMatch : t.library.emptyLibrary}</p>
                    ) : (
                      filteredTopics.map((topic) => {
                        const isDemoTopic = topic.slug === TOUR_DEMO_TOPIC_SLUG;
                        return (
                          <details key={topic.slug} className="topic-accordion" open={isDemoTopic ? true : undefined}>
                            <summary>
                              <span className="sheet-title">
                                <strong>{topic.name}</strong>
                                <small className="muted">{t.library.channelCount(topic.targets.length)}</small>
                              </span>
                              <button
                                type="button"
                                className="topic-run-btn"
                                aria-label={t.library.runTopicAria(topic.name)}
                                title={t.library.runTopicTitle}
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  if (!isDemoTopic) run([topic], topic.name);
                                }}
                                disabled={blocked || topic.targets.length === 0 || isDemoTopic}
                              >
                                ▶
                              </button>
                              {!isDemoTopic && (
                                <button
                                  type="button"
                                  className="channel-del-btn"
                                  aria-label={t.library.deleteTopicAria(topic.name)}
                                  title={t.library.deleteTopicTitle}
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    postJson('/api/sources/topics/delete', { slug: topic.slug });
                                  }}
                                >
                                  ✕
                                </button>
                              )}
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
                                  {!isDemoTopic && (
                                    <button
                                      type="button"
                                      className="channel-del-btn"
                                      aria-label={t.library.deleteChannelAria(target.name)}
                                      onClick={() =>
                                        postJson('/api/sources/profiles/delete', { slug: topic.slug, url: target.url })
                                      }
                                    >
                                      ✕
                                    </button>
                                  )}
                                </div>
                              ))}

                              <form
                                className="row"
                                onSubmit={async (e) => {
                                  e.preventDefault();
                                  if (isDemoTopic) return;
                                  const url = (inlineUrls[topic.slug] || '').trim();
                                  if (url && (await addChannel(topic.name, url)))
                                    setInlineUrls((prev) => ({ ...prev, [topic.slug]: '' }));
                                }}
                              >
                                <input
                                  type="url"
                                  className="text-input small"
                                  placeholder={t.library.addChannelPlaceholder}
                                  aria-label={t.library.addChannelAria(topic.name)}
                                  value={inlineUrls[topic.slug] || ''}
                                  onChange={(e) => setInlineUrls((prev) => ({ ...prev, [topic.slug]: e.target.value }))}
                                />
                                <button
                                  type="submit"
                                  className="ghost small"
                                  disabled={busy || isDemoTopic || !(inlineUrls[topic.slug] || '').trim()}
                                >
                                  {t.library.addChannelBtn}
                                </button>
                              </form>

                              {!isDemoTopic && !isDefaultTopic(topic) && (
                                <button
                                  type="button"
                                  className="btn-text-danger"
                                  onClick={() =>
                                    window.confirm(t.library.deleteTopicConfirm(topic.name)) &&
                                    postJson('/api/sources/topics/delete', { slug: topic.slug })
                                  }
                                >
                                  {t.library.deleteTopicTitle}
                                </button>
                              )}
                            </div>
                          </details>
                        );
                      })
                    )}

                    <form className="new-topic" onSubmit={createTopic}>
                      <input
                        type="text"
                        className="text-input small"
                        placeholder={t.library.newTopicPlaceholder}
                        aria-label={t.library.newTopicAria}
                        value={newTopic.name}
                        onChange={(e) => setNewTopic((v) => ({ ...v, name: e.target.value }))}
                      />
                      <input
                        type="url"
                        className="text-input small"
                        placeholder={t.library.firstChannelPlaceholder}
                        aria-label={t.library.firstChannelAria}
                        value={newTopic.url}
                        onChange={(e) => setNewTopic((v) => ({ ...v, url: e.target.value }))}
                      />
                      <button type="submit" className="ghost small" disabled={busy || !newTopic.name.trim()}>
                        {t.library.createTopicBtn}
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
                    <h2>{t.library.savedReelsTitle}</h2>
                    <span className="muted count">{t.library.reelCount(savedReels.length)}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <span className={`store-toggle-icon ${!savedReelsCollapsed ? 'open' : ''}`} aria-hidden="true" />
                  </div>
                </div>

                {!savedReelsCollapsed && (
                  <div className="saved-reels-body" style={{ marginTop: 'var(--space-3)' }}>
                    {(() => {
                      const grouped = savedReels.reduce<Record<string, SavedReel[]>>((acc, r) => {
                        const key = (r.topic || '').trim() || 'reels từ facebook';
                        (acc[key] = acc[key] || []).push(r);
                        return acc;
                      }, {});
                      const topicEntries = Object.entries(grouped);
                      return (
                        <>
                          {topicEntries.length === 0 ? (
                            <div className="empty" style={{ padding: 'var(--space-3) 0 0' }}>
                              <p className="muted" style={{ fontSize: 'var(--text-xs)', margin: 0 }}>
                                {t.library.noSavedReels}
                              </p>
                            </div>
                          ) : (
                            topicEntries.map(([topicName, reels]) => (
                              <details key={topicName} className="sheet" style={{ marginBottom: 'var(--space-2)' }}>
                                <summary>
                                  <span className="sheet-title">
                                    <strong>{topicName}</strong>
                                    <small className="muted">{t.library.reelCount(reels.length)}</small>
                                  </span>
                                  <button
                                    type="button"
                                    className="channel-del-btn"
                                    aria-label={t.library.deleteTopicAria(topicName)}
                                    title={t.library.deleteReelTopicTitle}
                                    onClick={(e) => handleDeleteSavedReelTopic(topicName, e)}
                                  >
                                    ✕
                                  </button>
                                </summary>
                                <div className="saved-reels-list" style={{ marginTop: 'var(--space-2)' }}>
                                  {reels.map((reel) => (
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
                                          aria-label={t.library.runReelLabel}
                                          title={t.library.runReelLabel}
                                        >
                                          ▶
                                        </button>
                                        <button
                                          type="button"
                                          className="channel-del-btn"
                                          aria-label={t.library.deleteReelAria}
                                          onClick={(e) => handleDeleteSavedReel(reel.id, e)}
                                          title={t.library.deleteReelTitle}
                                        >
                                          ✕
                                        </button>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                <form
                                  className="inline-add"
                                  style={{ marginTop: 'var(--space-2)' }}
                                  onSubmit={async (e) => {
                                    e.preventDefault();
                                    const val = (inlineReelUrls[topicName] || '').trim();
                                    if (!val) return;
                                    const ok = await saveReelToTopic(val, topicName);
                                    if (ok) setInlineReelUrls((prev) => ({ ...prev, [topicName]: '' }));
                                  }}
                                >
                                  <input
                                    type="url"
                                    className="text-input small"
                                    placeholder={t.library.addReelToTopicPlaceholder(topicName)}
                                    aria-label={t.library.addReelToTopicAria(topicName)}
                                    value={inlineReelUrls[topicName] || ''}
                                    onChange={(e) =>
                                      setInlineReelUrls((prev) => ({ ...prev, [topicName]: e.target.value }))
                                    }
                                  />
                                  <button
                                    type="submit"
                                    className="ghost small"
                                    disabled={busy || !(inlineReelUrls[topicName] || '').trim()}
                                  >
                                    {t.library.addChannelBtn}
                                  </button>
                                </form>
                              </details>
                            ))
                          )}
                          <form
                            className="new-topic"
                            style={{ marginTop: 'var(--space-2)' }}
                            onSubmit={async (e) => {
                              e.preventDefault();
                              const ok = await saveReelToTopic(newReelUrl, newReelTopic);
                              if (ok) setNewReelUrl('');
                            }}
                          >
                            <input
                              type="text"
                              className="text-input small"
                              placeholder={t.library.newReelTopicPlaceholder}
                              aria-label={t.library.newReelTopicAria}
                              value={newReelTopic}
                              onChange={(e) => setNewReelTopic(e.target.value)}
                            />
                            <input
                              type="url"
                              className="text-input small"
                              placeholder={t.library.newReelUrlPlaceholder}
                              aria-label={t.library.newReelUrlAria}
                              value={newReelUrl}
                              onChange={(e) => setNewReelUrl(e.target.value)}
                            />
                            <button type="submit" className="ghost small" disabled={busy || !newReelUrl.trim()}>
                              {t.library.saveReelBtn}
                            </button>
                          </form>
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            </>
          ) : (
            <AnalyzerTab
              keyword={keyword}
              onKeywordChange={setKeyword}
              onSearchKeyword={(kw) => run([{ name: kw, slug: kw, targets: [{ name: kw, url: kw }] }], kw, 'keyword')}
              onSearchKeywords={(kws) => {
                const list = kws.map((k) => k.trim()).filter(Boolean);
                if (!list.length) return;
                const label = list[0];
                run([{ name: label, slug: label, targets: list.map((k) => ({ name: k, url: k })) }], label, 'keyword');
              }}
              blocked={blocked}
              error={error}
              starting={starting}
              jobId={jobId}
              job={job}
              visibleHistory={visibleHistory}
              onSelectJob={selectJob}
              onDeleteJob={deleteJob}
              tourDemoId={TOUR_DEMO_ID}
              copiedKey={copiedKey}
              onCopyTopic={handleCopyTopic}
              onAddCreator={handleAddCreator}
              onSaveVideo={handleSaveVideo}
              onGoToLibrary={() => switchTab('library')}
              forceHistoryView={showTour && tourHistoryView}
            />
          )}
        </div>
      </IonContent>

      <IonToast
        isOpen={!!notice}
        message={notice?.text}
        color={notice?.type === 'error' ? 'danger' : 'success'}
        duration={2500}
        position="top"
        onDidDismiss={() => setNotice(null)}
      />

      <IonFooter className="ion-no-border">
        {running && (
          <div className="actionbar">
            <button className="ghost danger" type="button" onClick={cancel}>
              {t.library.stopBtn}
            </button>
          </div>
        )}
        <nav className="tabbar" role="tablist">
          {(['analyzer', 'library', 'video', 'profile'] as Tab[]).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`tabbar-btn ${tab === id ? 'active' : ''}`}
              onClick={() => switchTab(id)}
            >
              <span className="tabbar-icon">
                <IonIcon icon={TAB_ICONS[id]} aria-hidden="true" />
                {id === 'analyzer' && hasActiveJob && <span className="live-dot" aria-label={t.tabs.runningAria} />}
                {id === 'profile' && user && <span className="live-dot online" aria-label={t.tabs.loggedInAria} />}
              </span>
              {t.tabs[id]}
            </button>
          ))}
        </nav>
      </IonFooter>

      {showTour && authReady && <Tour steps={tourSteps} onTab={(tb) => switchTab(tb as Tab)} onClose={closeTour} />}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />

      {linkCode && (
        <div className="payment-backdrop" onClick={() => setLinkCode(null)}>
          <div
            className="payment-sheet"
            role="dialog"
            aria-label={t.library.messengerDialogLabel}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="payment-sheet-head">
              <div className="payment-sheet-title">
                <span className="payment-cart-icon">💬</span>
                <h3>{t.library.messengerDialogLabel}</h3>
              </div>
              <button
                type="button"
                className="payment-close-btn"
                aria-label={t.common.close}
                onClick={() => setLinkCode(null)}
              >
                ✕
              </button>
            </div>

            <p className="muted payment-subtext">{t.library.messengerStepDesc(linkCode.command)}</p>

            <div className="payment-sheet-buttons">
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  navigator.clipboard?.writeText(linkCode.command);
                  setNotice({ type: 'success', text: t.library.copiedCommand(linkCode.command) });
                }}
              >
                {t.library.copyCommand(linkCode.command)}
              </button>
              <a
                href={`https://m.me/${linkCode.page_id}?text=${encodeURIComponent(linkCode.command)}`}
                target="_blank"
                rel="noreferrer"
                className="primary"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textDecoration: 'none',
                }}
              >
                {t.library.openMessenger}
              </a>
            </div>
          </div>
        </div>
      )}

      {activePaymentPack && (
        <div className="payment-backdrop" onClick={() => setActivePaymentPack(null)}>
          <div className="payment-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="payment-sheet-head">
              <div className="payment-sheet-title">
                <span className="payment-cart-icon">🛒</span>
                <h3>{t.payment.title}</h3>
              </div>
              <button
                type="button"
                className="payment-close-btn"
                aria-label={t.common.close}
                onClick={() => setActivePaymentPack(null)}
              >
                ✕
              </button>
            </div>

            <p className="muted payment-subtext">{t.payment.subtitle}</p>

            <div className="payment-receipt-box">
              <div className="payment-receipt-row">
                <span className="muted">{t.payment.account}</span>
                <strong>{user ? user.displayName || user.email || user.uid : t.payment.guest}</strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">{t.payment.pack}</span>
                <strong>{activePaymentPack.name}</strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">{t.payment.channelCount}</span>
                <strong>
                  {t.creatorPacks[activePaymentPack.id]?.countLabel ||
                    activePaymentPack.countLabel ||
                    (activePaymentPack.count
                      ? t.payment.creatorFacebook(formatNumber(activePaymentPack.count))
                      : t.payment.monthlyMaintenance)}
                </strong>
              </div>
              <div className="payment-receipt-row">
                <span className="muted">{t.payment.method}</span>
                <span>{t.payment.methodValue}</span>
              </div>
              <div className="payment-receipt-row total">
                <span>{t.payment.total}</span>
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
                {t.common.cancel}
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => handleConfirmMockPayment(activePaymentPack)}
                disabled={claimingPack === activePaymentPack.id}
              >
                {claimingPack === activePaymentPack.id ? t.payment.claiming : t.payment.confirmBtn}
              </button>
            </div>
          </div>
        </div>
      )}
    </IonPage>
  );
};

export default Home;
