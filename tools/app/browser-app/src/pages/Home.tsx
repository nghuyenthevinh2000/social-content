import { IonContent, IonFooter, IonHeader, IonPage } from '@ionic/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { apiFetch } from '../api';
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
  target_list?: { name: string; url: string }[];
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

export type TargetItem = {
  name: string;
  url: string;
};

export type TopicItem = {
  name: string;
  slug: string;
  targets: TargetItem[];
};

const DEFAULT_TOPICS: TopicItem[] = [
  {
    name: 'Mẹ chồng - nàng dâu',
    slug: 'me-chong-nang-dau',
    targets: [
      { name: 'Mẹ chồng vào bếp', url: 'https://www.facebook.com/100084795256037' },
      { name: 'Nàng dâu kể chuyện', url: 'https://www.facebook.com/Nangdaukechuyen' },
      { name: 'Mẹ dạy mẹo hay', url: 'https://www.facebook.com/Medaymeohay' },
    ],
  },
  {
    name: 'Thực phẩm bẩn',
    slug: 'thuc-pham-ban',
    targets: [{ name: 'Đơn giản thôi', url: 'https://www.facebook.com/dongianthoi.ok' }],
  },
  {
    name: 'Vợ chồng',
    slug: 'vo-chong',
    targets: [{ name: 'Gia trưởng lo cho em', url: 'https://www.facebook.com/Giatruonglochoem' }],
  },
  {
    name: 'Cỏ cây sức khoẻ',
    slug: 'co-cay-suc-khoe',
    targets: [{ name: 'Sống khoẻ mỗi ngày', url: 'https://www.facebook.com/100084795256037' }],
  },
];

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

const STATUS_LABEL: Record<Job['status'], string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  completed: 'Hoàn tất',
  failed: 'Có lỗi',
  cancelled: 'Đã dừng',
};

const formatNumber = (value: number) => new Intl.NumberFormat('vi-VN').format(value);

function slugify(name: string): string {
  return (
    name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || `topic-${Date.now()}`
  );
}

function reportClientLog(message: string, stack?: string, source = 'client') {
  apiFetch('/api/logs/client', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, stack, source }),
  }).catch(() => {});
}

const Home: React.FC = () => {
  const location = useLocation();
  const queryJobId = useMemo(() => new URLSearchParams(location.search).get('job_id'), [location.search]);
  const queryTab = useMemo(() => new URLSearchParams(location.search).get('tab'), [location.search]);

  // Tab navigation
  const [activeTab, setActiveTab] = useState<'analysis' | 'sources'>(queryTab === 'sources' ? 'sources' : 'analysis');

  useEffect(() => {
    if (queryTab === 'sources' || queryTab === 'analysis') {
      setActiveTab(queryTab);
    }
  }, [queryTab]);

  // Analysis tab state
  const [file, setFile] = useState<File | null>(null);
  const [sheetUrl, setSheetUrl] = useState('');
  const [maxVideos, setMaxVideos] = useState(5);
  const [media, setMedia] = useState(true);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(queryJobId);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const sourceFileInputRef = useRef<HTMLInputElement>(null);
  const contentRef = useRef<HTMLIonContentElement>(null);

  // Data Sources tab state
  const [topics, setTopics] = useState<TopicItem[]>(() => {
    try {
      const raw = localStorage.getItem('aibrand-topics-v1');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return DEFAULT_TOPICS;
  });

  const [directUrl, setDirectUrl] = useState('');
  const [directName, setDirectName] = useState('');
  const [selectedTopic, setSelectedTopic] = useState<string>(topics[0]?.name || '__new__');
  const [newTopicName, setNewTopicName] = useState('');
  const [sourceSearch, setSourceSearch] = useState('');
  const [sourceMessage, setSourceMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [importingSources, setImportingSources] = useState(false);
  const [sourceSheetUrl, setSourceSheetUrl] = useState('');
  const [inlineUrls, setInlineUrls] = useState<Record<string, string>>({});

  // Sync topics to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('aibrand-topics-v1', JSON.stringify(topics));
    } catch {}
  }, [topics]);

  // Fetch topics from backend social profile store on mount
  useEffect(() => {
    apiFetch('/api/sources/topics')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.topics) && data.topics.length > 0) {
          setTopics(data.topics);
        }
      })
      .catch(() => {});
  }, []);

  // Sync new topics from parsed job sheets if present
  useEffect(() => {
    if (job?.sheets) {
      const newItems: TopicItem[] = [];
      for (const s of job.sheets) {
        if (s.target_list && s.target_list.length > 0) {
          newItems.push({
            name: s.name,
            slug: s.slug,
            targets: s.target_list,
          });
        }
      }
      if (newItems.length > 0) {
        setTopics((prev) => {
          const map = new Map(prev.map((t) => [t.name.toLowerCase(), t]));
          for (const item of newItems) {
            if (!map.has(item.name.toLowerCase())) {
              map.set(item.name.toLowerCase(), item);
            }
          }
          return Array.from(map.values());
        });
      }
    }
  }, [job?.sheets]);

  useEffect(() => {
    if (queryJobId) setJobId(queryJobId);
  }, [queryJobId]);

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
        const res = await apiFetch(`/api/jobs/${jobId}`);
        if (!res.ok) return;
        const data: Job = await res.json();
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

  useEffect(() => {
    if (job) {
      contentRef.current?.scrollToBottom(500);
    }
  }, [Boolean(job)]);

  const totalChannels = useMemo(() => {
    return topics.reduce((acc, t) => acc + t.targets.length, 0);
  }, [topics]);

  const filteredTopics = useMemo(() => {
    const query = sourceSearch.trim().toLowerCase();
    if (!query) return topics;
    return topics.filter(
      (t) =>
        t.name.toLowerCase().includes(query) ||
        t.targets.some((tg) => tg.name.toLowerCase().includes(query) || tg.url.toLowerCase().includes(query)),
    );
  }, [topics, sourceSearch]);

  async function start() {
    const trimmedUrl = sheetUrl.trim();
    if (!file && !trimmedUrl) {
      setError('Chọn file Excel hoặc dán link Google Sheet trước.');
      return;
    }
    setError(null);
    setStarting(true);
    setJob(null);
    try {
      const params = new URLSearchParams({ max_videos: String(maxVideos), media: media ? '1' : '0' });
      const body = file ? file : new Blob([trimmedUrl], { type: 'text/plain' });
      const filename = file ? file.name : 'google_sheet.xlsx';
      const res = await apiFetch(`/api/jobs?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': file?.type || 'application/octet-stream',
          'X-Filename': encodeURIComponent(filename),
        },
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Không tạo được job');
      setJob(data);
      setJobId(data.id);
      window.history.replaceState(null, '', `?job_id=${data.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      reportClientLog(message, err instanceof Error ? err.stack : undefined, 'start-job');
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (jobId) await apiFetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
  }

  // Run analysis for a single topic from the Data Sources library
  async function runTopic(topic: TopicItem) {
    if (topic.targets.length === 0) {
      setError(`Chủ đề "${topic.name}" chưa có kênh nào để phân tích.`);
      setActiveTab('analysis');
      return;
    }
    setError(null);
    setStarting(true);
    setJob(null);
    setActiveTab('analysis');
    try {
      const params = new URLSearchParams({ max_videos: String(maxVideos), media: media ? '1' : '0' });
      const payload = {
        sheets: [
          {
            name: topic.name,
            targets: topic.targets,
          },
        ],
      };
      const body = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      const res = await apiFetch(`/api/jobs?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Filename': encodeURIComponent(`${topic.slug}.json`),
        },
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Không tạo được job');
      setJob(data);
      setJobId(data.id);
      window.history.replaceState(null, '', `?job_id=${data.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      reportClientLog(message, err instanceof Error ? err.stack : undefined, 'start-single-topic');
    } finally {
      setStarting(false);
    }
  }

  // Run analysis for ALL topics in the library
  async function runAllTopics() {
    const validTopics = topics.filter((t) => t.targets.length > 0);
    if (validTopics.length === 0) {
      setError('Chưa có chủ đề nào chứa kênh đối thủ để chạy phân tích.');
      setActiveTab('analysis');
      return;
    }
    setError(null);
    setStarting(true);
    setJob(null);
    setActiveTab('analysis');
    try {
      const params = new URLSearchParams({ max_videos: String(maxVideos), media: media ? '1' : '0' });
      const payload = {
        sheets: validTopics.map((t) => ({
          name: t.name,
          targets: t.targets,
        })),
      };
      const body = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      const res = await apiFetch(`/api/jobs?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Filename': encodeURIComponent('all_topics.json'),
        },
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Không tạo được job');
      setJob(data);
      setJobId(data.id);
      window.history.replaceState(null, '', `?job_id=${data.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      reportClientLog(message, err instanceof Error ? err.stack : undefined, 'start-all-topics');
    } finally {
      setStarting(false);
    }
  }

  // Add direct social link + topic assignment
  async function handleAddDirectChannel(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const trimmedUrl = directUrl.trim();
    if (!trimmedUrl) {
      setSourceMessage({ type: 'error', text: 'Vui lòng nhập link tài khoản / page / video đối thủ.' });
      return;
    }
    let targetTopicName = selectedTopic.trim();
    if (selectedTopic === '__new__') {
      targetTopicName = newTopicName.trim();
      if (!targetTopicName) {
        setSourceMessage({ type: 'error', text: 'Vui lòng nhập tên cho chủ đề mới.' });
        return;
      }
    }

    const channelName = directName.trim() || trimmedUrl.replace(/^https?:\/\/(www\.)?/, '').slice(0, 30);

    try {
      const res = await apiFetch('/api/sources/topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: targetTopicName,
          url: trimmedUrl,
          channel_name: channelName,
        }),
      });
      const data = await res.json();
      if (data && Array.isArray(data.topics)) {
        setTopics(data.topics);
      }
    } catch {
      setTopics((prev) => {
        const existingIndex = prev.findIndex((t) => t.name.toLowerCase() === targetTopicName.toLowerCase());
        if (existingIndex >= 0) {
          const updated = [...prev];
          const current = updated[existingIndex];
          const exists = current.targets.some((tg) => tg.url === trimmedUrl);
          if (!exists) {
            updated[existingIndex] = {
              ...current,
              targets: [...current.targets, { name: channelName, url: trimmedUrl }],
            };
          }
          return updated;
        } else {
          return [
            ...prev,
            {
              name: targetTopicName,
              slug: slugify(targetTopicName),
              targets: [{ name: channelName, url: trimmedUrl }],
            },
          ];
        }
      });
    }

    setDirectUrl('');
    setDirectName('');
    if (selectedTopic === '__new__') {
      setSelectedTopic(targetTopicName);
      setNewTopicName('');
    }
    setSourceMessage({
      type: 'success',
      text: `Đã thêm kênh "${channelName}" vào chủ đề "${targetTopicName}".`,
    });
    setTimeout(() => setSourceMessage(null), 3500);
  }

  // Import sources via File or Google Sheet URL
  async function handleImportSources(source: File | string) {
    setImportingSources(true);
    setSourceMessage(null);
    try {
      const body = typeof source === 'string' ? new Blob([source], { type: 'text/plain' }) : source;
      const filename = typeof source === 'string' ? 'sheet_import.xlsx' : source.name;
      const res = await apiFetch('/api/sources/parse', {
        method: 'POST',
        headers: {
          'Content-Type': typeof source === 'string' ? 'text/plain' : source.type || 'application/octet-stream',
          'X-Filename': encodeURIComponent(filename),
        },
        body,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Không nạp được nguồn');
      if (!data.sheets || data.sheets.length === 0) {
        throw new Error('Không tìm thấy sheet hoặc kênh Facebook nào trong file.');
      }

      let addedChannels = 0;
      setTopics((prev) => {
        const map = new Map<string, TopicItem>(
          prev.map((t) => [t.name.toLowerCase(), { ...t, targets: [...t.targets] }]),
        );
        for (const sheet of data.sheets) {
          const key = sheet.name.toLowerCase();
          const existing = map.get(key);
          if (existing) {
            for (const target of sheet.targets) {
              if (!existing.targets.some((t) => t.url === target.url)) {
                existing.targets.push(target);
                addedChannels++;
              }
            }
          } else {
            map.set(key, {
              name: sheet.name,
              slug: sheet.slug,
              targets: sheet.targets,
            });
            addedChannels += sheet.targets.length;
          }
        }
        return Array.from(map.values());
      });

      setSourceMessage({
        type: 'success',
        text: `Đã nạp thành công ${data.sheets.length} chủ đề và ${addedChannels} kênh mới.`,
      });
      setSourceSheetUrl('');
      setTimeout(() => setSourceMessage(null), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSourceMessage({ type: 'error', text: msg });
    } finally {
      setImportingSources(false);
    }
  }

  // Delete channel from a topic
  function handleDeleteChannel(topicSlug: string, channelUrl: string) {
    apiFetch('/api/sources/profiles/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: topicSlug, url: channelUrl }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.topics)) setTopics(data.topics);
      })
      .catch(() => {});

    setTopics((prev) =>
      prev.map((t) => {
        if (t.slug !== topicSlug) return t;
        return {
          ...t,
          targets: t.targets.filter((tg) => tg.url !== channelUrl),
        };
      }),
    );
  }

  // Delete an entire topic
  function handleDeleteTopic(topicSlug: string) {
    if (window.confirm('Bạn có chắc muốn xoá chủ đề này cùng toàn bộ kênh đã lưu?')) {
      apiFetch('/api/sources/topics/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug: topicSlug }),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && Array.isArray(data.topics)) setTopics(data.topics);
        })
        .catch(() => {});

      setTopics((prev) => prev.filter((t) => t.slug !== topicSlug));
    }
  }

  // Add inline channel directly inside an accordion
  function handleInlineAddChannel(topicSlug: string) {
    const rawUrl = (inlineUrls[topicSlug] || '').trim();
    if (!rawUrl) return;
    const targetTopic = topics.find((t) => t.slug === topicSlug);
    const topicName = targetTopic ? targetTopic.name : topicSlug;
    const name = rawUrl.replace(/^https?:\/\/(www\.)?/, '').slice(0, 30);

    apiFetch('/api/sources/topics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topicName, url: rawUrl, channel_name: name }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.topics)) setTopics(data.topics);
      })
      .catch(() => {});

    setTopics((prev) =>
      prev.map((t) => {
        if (t.slug !== topicSlug) return t;
        if (t.targets.some((tg) => tg.url === rawUrl)) return t;
        return {
          ...t,
          targets: [...t.targets, { name, url: rawUrl }],
        };
      }),
    );
    setInlineUrls((prev) => ({ ...prev, [topicSlug]: '' }));
  }

  return (
    <IonPage className="ab">
      <IonHeader className="ion-no-border">
        <div className="topbar">
          <span className="brand">
            <span className="brand-mark">AB</span>AIBrand
          </span>
          <div className="tab-nav">
            <button
              type="button"
              className={`tab-nav-btn ${activeTab === 'analysis' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('analysis');
                window.history.replaceState(null, '', '?tab=analysis');
              }}
            >
              Phân tích
            </button>
            <button
              type="button"
              className={`tab-nav-btn ${activeTab === 'sources' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('sources');
                window.history.replaceState(null, '', '?tab=sources');
              }}
            >
              Nguồn dữ liệu
              <span className="tab-count-badge">{topics.length}</span>
            </button>
          </div>
        </div>
      </IonHeader>

      <IonContent ref={contentRef}>
        <div className="ab-page">
          {activeTab === 'analysis' ? (
            <>
              <header className="hero">
                <h1>Spy đối thủ → 3 chủ đề viral mỗi sheet</h1>
                <p className="muted">Quét video đối thủ 48h và đề xuất 3 chủ đề viral mỗi sheet.</p>
              </header>

              <section className="panel">
                <h2>1. Nguồn dữ liệu</h2>
                <button className="picker" type="button" onClick={() => inputRef.current?.click()}>
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".xlsx,.xlsm,.xls,.gsheet,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.google-apps.spreadsheet"
                    hidden
                    onChange={(event) => {
                      const picked = event.target.files?.[0] ?? null;
                      setFile(picked);
                      if (picked) setSheetUrl('');
                    }}
                  />
                  <span className="picker-icon">⇪</span>
                  <span>
                    <strong>{file ? file.name : 'Chọn file Excel'}</strong>
                    <small className="muted">
                      {file ? `${Math.round(file.size / 1024)} KB · Đổi file` : 'Định dạng .xlsx / .xlsm · tối đa 25MB'}
                    </small>
                  </span>
                </button>

                <div className="url-input-wrap">
                  <span className="url-divider">hoặc dán link Google Sheet</span>
                  <input
                    type="url"
                    className="text-input"
                    placeholder="https://docs.google.com/spreadsheets/d/..."
                    value={sheetUrl}
                    onChange={(e) => {
                      setSheetUrl(e.target.value);
                      if (e.target.value.trim()) setFile(null);
                    }}
                  />
                  <small className="muted">
                    Lưu ý: Mở Google Sheet → <strong>Chia sẻ</strong> → chọn{' '}
                    <strong>Bất kỳ ai có đường liên kết</strong> (quyền Xem).
                  </small>
                </div>

                {topics.length > 0 && (
                  <div className="library-quick-banner">
                    <span>
                      Hoặc chạy từ kho cá nhân (<strong>{topics.length} chủ đề</strong>)
                    </span>
                    <button
                      type="button"
                      className="ghost mini-run-btn"
                      onClick={runAllTopics}
                      disabled={starting || running}
                    >
                      ▶ Chạy kho
                    </button>
                  </div>
                )}

                <h2>2. Tuỳ chọn chạy</h2>
                <div className="option">
                  <span>
                    Video tối đa / sheet
                    <small className="muted">0 = không giới hạn</small>
                  </span>
                  <span className="stepper">
                    <button type="button" aria-label="Giảm" onClick={() => setMaxVideos((v) => Math.max(0, v - 1))}>
                      −
                    </button>
                    <input
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={500}
                      value={maxVideos}
                      aria-label="Video tối đa / sheet"
                      onChange={(event) => setMaxVideos(Math.min(500, Math.max(0, Number(event.target.value))))}
                    />
                    <button type="button" aria-label="Tăng" onClick={() => setMaxVideos((v) => Math.min(500, v + 1))}>
                      +
                    </button>
                  </span>
                </div>
                <label className="option">
                  <span>
                    Tải video + transcribe
                    <small className="muted">chậm hơn</small>
                  </span>
                  <input
                    type="checkbox"
                    className="switch"
                    checked={media}
                    onChange={(e) => setMedia(e.target.checked)}
                  />
                </label>
                {error && <div className="alert">{error}</div>}
              </section>

              <section className="panel" id="results">
                <div className="results-head">
                  <div>
                    <h2>Kết quả</h2>
                    <p className="muted">
                      {job
                        ? `${job.filename} · ${progress.done}/${progress.total} sheet · ${STATUS_LABEL[job.status]}`
                        : 'Chưa có job nào. Kết quả sẽ xuất hiện theo từng sheet.'}
                    </p>
                  </div>
                  {job && (
                    <a className="ghost" href={`/api/jobs/${job.id}/export`}>
                      Tải JSON
                    </a>
                  )}
                </div>

                {job && (
                  <>
                    <div className="bar">
                      <span style={{ width: `${progress.pct}%` }} />
                    </div>
                    <div className="progress-meta muted">
                      <span>{progress.pct}%</span>
                      <span>{job.current_sheet ? `Đang xử lý: ${job.current_sheet}` : 'Sẵn sàng'}</span>
                    </div>

                    {job.sheets.map((sheet, index) => (
                      <details key={sheet.slug} className="sheet" open={sheet.status === 'running' ? true : undefined}>
                        <summary>
                          <span className="sheet-index">{String(index + 1).padStart(2, '0')}</span>
                          <span className="sheet-title">
                            <strong>{sheet.name}</strong>
                            <small className="muted">
                              {sheet.targets} kênh · {formatNumber(sheet.reels)} reel
                              {sheet.error ? ' · có lỗi' : ''}
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
                        {sheet.error && <div className="alert">{sheet.error}</div>}
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
            </>
          ) : (
            <>
              {/* SOURCES TAB */}
              <header className="hero">
                <h1>Kho nguồn dữ liệu cá nhân</h1>
                <p className="muted">
                  Quản lý chủ đề và danh sách tài khoản / kênh đối thủ. Thêm qua file Excel, Google Drive hoặc dán link
                  trực tiếp.
                </p>
                <div className="stats-pill">
                  <strong>{topics.length}</strong> chủ đề · <strong>{totalChannels}</strong> kênh đối thủ
                </div>
              </header>

              {/* SECTION: ADD SOURCES */}
              <section className="panel">
                <h2>1. Thêm nguồn dữ liệu</h2>

                {/* Sub-block A: File / Drive Import */}
                <div className="source-block">
                  <h3 className="block-title">A. Nạp từ Excel hoặc Google Drive</h3>
                  <button
                    className="picker"
                    type="button"
                    onClick={() => sourceFileInputRef.current?.click()}
                    disabled={importingSources}
                  >
                    <input
                      ref={sourceFileInputRef}
                      type="file"
                      accept=".xlsx,.xlsm,.xls,.gsheet,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.google-apps.spreadsheet"
                      hidden
                      onChange={(event) => {
                        const picked = event.target.files?.[0];
                        if (picked) handleImportSources(picked);
                      }}
                    />
                    <span className="picker-icon">⇪</span>
                    <span>
                      <strong>{importingSources ? 'Đang đọc dữ liệu...' : 'Chọn file Excel (.xlsx / .xlsm)'}</strong>
                      <small className="muted">Tự động bóc tách từng sheet thành các chủ đề</small>
                    </span>
                  </button>

                  <div className="url-input-wrap">
                    <span className="url-divider">hoặc nạp từ Google Sheet</span>
                    <div className="url-row">
                      <input
                        type="url"
                        className="text-input"
                        placeholder="https://docs.google.com/spreadsheets/d/..."
                        value={sourceSheetUrl}
                        onChange={(e) => setSourceSheetUrl(e.target.value)}
                      />
                      <button
                        type="button"
                        className="ghost run-btn-mini"
                        disabled={importingSources || !sourceSheetUrl.trim()}
                        onClick={() => handleImportSources(sourceSheetUrl.trim())}
                      >
                        Nạp link
                      </button>
                    </div>
                  </div>
                </div>

                <div className="divider-h" />

                {/* Sub-block B: Direct Link + Topic Selection */}
                <div className="source-block">
                  <h3 className="block-title">B. Thêm kênh trực tiếp & gắn chủ đề</h3>
                  <form onSubmit={handleAddDirectChannel} className="direct-add-form">
                    <div className="form-group">
                      <label className="form-label">Link tài khoản / page / video đối thủ:</label>
                      <input
                        type="url"
                        className="text-input"
                        placeholder="https://www.facebook.com/page-name hoặc link video..."
                        value={directUrl}
                        onChange={(e) => setDirectUrl(e.target.value)}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Tên kênh gợi nhớ (tuỳ chọn):</label>
                      <input
                        type="text"
                        className="text-input"
                        placeholder="Ví dụ: Mẹ Chồng Vào Bếp, Kênh Review..."
                        value={directName}
                        onChange={(e) => setDirectName(e.target.value)}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Chọn chủ đề gắn vào:</label>
                      <select
                        className="text-input select-input"
                        value={selectedTopic}
                        onChange={(e) => setSelectedTopic(e.target.value)}
                      >
                        {topics.map((t) => (
                          <option key={t.slug} value={t.name}>
                            {t.name} ({t.targets.length} kênh)
                          </option>
                        ))}
                        <option value="__new__">+ Tạo chủ đề mới...</option>
                      </select>
                    </div>

                    {selectedTopic === '__new__' && (
                      <div className="form-group">
                        <label className="form-label">Tên chủ đề mới:</label>
                        <input
                          type="text"
                          className="text-input"
                          placeholder="Ví dụ: Đồ gia dụng thông minh, Bất động sản..."
                          value={newTopicName}
                          onChange={(e) => setNewTopicName(e.target.value)}
                        />
                      </div>
                    )}

                    <button type="submit" className="primary btn-add-channel">
                      + Lưu kênh vào chủ đề
                    </button>
                  </form>
                </div>

                {sourceMessage && (
                  <div className={`alert ${sourceMessage.type === 'error' ? 'alert-danger' : 'alert-success'}`}>
                    {sourceMessage.text}
                  </div>
                )}
              </section>

              {/* SECTION: TOPIC LIBRARY & ACCORDIONS */}
              <section className="panel">
                <div className="library-head">
                  <div>
                    <h2>2. Danh sách chủ đề ({topics.length})</h2>
                    <p className="muted">{totalChannels} kênh đối thủ được phân chia theo từng chủ đề.</p>
                  </div>
                </div>

                <div className="search-wrap">
                  <input
                    type="search"
                    className="text-input search-input"
                    placeholder="🔍 Tìm chủ đề hoặc tên kênh, link..."
                    value={sourceSearch}
                    onChange={(e) => setSourceSearch(e.target.value)}
                  />
                </div>

                {filteredTopics.length === 0 ? (
                  <p className="muted empty-msg">Không tìm thấy chủ đề hoặc kênh nào phù hợp.</p>
                ) : (
                  <div className="accordion-list">
                    {filteredTopics.map((topic, index) => (
                      <details key={topic.slug} className="topic-accordion" open={index === 0 ? true : undefined}>
                        <summary>
                          <span className="sheet-index">{String(index + 1).padStart(2, '0')}</span>
                          <span className="sheet-title">
                            <strong>{topic.name}</strong>
                            <small className="muted">{topic.targets.length} kênh đối thủ</small>
                          </span>
                          <button
                            type="button"
                            className="topic-run-btn"
                            title={`Chạy phân tích chủ đề ${topic.name}`}
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              runTopic(topic);
                            }}
                            disabled={starting || running}
                          >
                            ▶ Chạy
                          </button>
                        </summary>

                        <div className="accordion-body">
                          {topic.targets.length === 0 ? (
                            <p className="muted empty-sub">Chưa có kênh nào trong chủ đề này.</p>
                          ) : (
                            <div className="channel-list">
                              {topic.targets.map((target, tIdx) => (
                                <div key={tIdx} className="channel-card">
                                  <div className="channel-info">
                                    <span className="channel-name">{target.name}</span>
                                    <a
                                      href={target.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="channel-link"
                                      title={target.url}
                                    >
                                      {target.url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 36)} ↗
                                    </a>
                                  </div>
                                  <button
                                    type="button"
                                    className="channel-del-btn"
                                    title="Xoá kênh này"
                                    onClick={() => handleDeleteChannel(topic.slug, target.url)}
                                  >
                                    ✕
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Quick inline channel add */}
                          <div className="inline-add-row">
                            <input
                              type="url"
                              className="text-input inline-input"
                              placeholder="Dán link facebook đối thủ mới..."
                              value={inlineUrls[topic.slug] || ''}
                              onChange={(e) => setInlineUrls((prev) => ({ ...prev, [topic.slug]: e.target.value }))}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  handleInlineAddChannel(topic.slug);
                                }
                              }}
                            />
                            <button
                              type="button"
                              className="ghost mini-add-btn"
                              onClick={() => handleInlineAddChannel(topic.slug)}
                              disabled={!(inlineUrls[topic.slug] || '').trim()}
                            >
                              + Thêm
                            </button>
                          </div>

                          <div className="topic-actions-footer">
                            <button
                              type="button"
                              className="btn-text-danger"
                              onClick={() => handleDeleteTopic(topic.slug)}
                            >
                              Xoá chủ đề này
                            </button>
                          </div>
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </IonContent>

      <IonFooter className="ion-no-border">
        <div className="actionbar">
          {activeTab === 'analysis' ? (
            <>
              <button className="primary" type="button" onClick={start} disabled={starting || running}>
                {starting ? 'Đang tạo job...' : running ? 'Đang chạy...' : 'Chạy phân tích'}
              </button>
              {running && (
                <button className="ghost danger" type="button" onClick={cancel}>
                  Dừng
                </button>
              )}
            </>
          ) : (
            <>
              <button className="primary" type="button" onClick={runAllTopics} disabled={starting || running}>
                {starting
                  ? 'Đang tạo job...'
                  : running
                    ? 'Đang chạy...'
                    : `Chạy phân tích toàn bộ (${topics.length} chủ đề)`}
              </button>
              {running && (
                <button className="ghost danger" type="button" onClick={cancel}>
                  Dừng
                </button>
              )}
            </>
          )}
        </div>
      </IonFooter>
    </IonPage>
  );
};

export default Home;
