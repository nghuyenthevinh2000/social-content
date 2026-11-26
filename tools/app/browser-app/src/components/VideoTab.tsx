import { useEffect, useRef, useState } from 'react';

import { apiJson } from '../api';
import type { User } from '../firebase';
import { type LocaleMessages, useLocale } from '../locales';

import { mediaUrl, type MediaItem } from './MediaPanel';
import './VideoTab.css';

export type VideoJob = {
  id: string;
  user_id: string;
  prompt: string;
  profile_media_id: string;
  context_media_ids: string[];
  cost: number;
  cost_usd: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  video_path: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  job_type?: 'generate' | 'edit';
  reference_video_url?: string | null;
};

export type VideoMode = 'edit' | 'generate';

type VideoTabProps = {
  user: User | null;
  onOpenAuth: () => void;
  onGoToProfile?: () => void;
  mode?: VideoMode;
  onModeChange?: (mode: VideoMode) => void;
  prompt?: string;
  onPromptChange?: (value: string) => void;
  editPrompt?: string;
  onEditPromptChange?: (value: string) => void;
  editReferenceUrl?: string;
  onEditReferenceUrlChange?: (value: string) => void;
  editSourceFile?: File | null;
  onEditSourceFileChange?: (file: File | null) => void;
  editHistoryJobId?: string | null;
  onEditHistoryJobIdChange?: (id: string | null) => void;
  duration?: number;
  onDurationChange?: (value: number) => void;
};

export const DEFAULT_VIDEO_DURATION = Number(import.meta.env.VITE_VIDEO_GENERATION_DURATION) || 15;

export function videoFileUrl(job: VideoJob): string {
  const uidParam = job.user_id ? `?uid=${encodeURIComponent(job.user_id)}` : '';
  return `/api/videos/${encodeURIComponent(job.id)}/file${uidParam}`;
}

export function videoDownloadUrl(job: VideoJob): string {
  const base = videoFileUrl(job);
  return `${base}${base.includes('?') ? '&' : '?'}download=1`;
}

function formatElapsed(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${String(rem).padStart(2, '0')}s`;
}

function estimateVideoProgress(
  job: VideoJob,
  nowMs: number,
  progressMsg: LocaleMessages['video']['progress'],
): { pct: number; elapsedSec: number; label: string } {
  const startIso = job.started_at || job.created_at;
  const startMs = startIso ? Date.parse(startIso) : nowMs;
  const elapsedSec = Number.isFinite(startMs) ? Math.max(0, Math.floor((nowMs - startMs) / 1000)) : 0;
  if (job.status === 'pending') {
    return { pct: 8, elapsedSec, label: progressMsg.queued };
  }
  const isEdit = job.job_type === 'edit';
  const tau = isEdit ? 120 : 60;
  const pct = Math.min(95, Math.max(10, Math.round(10 + 85 * (1 - Math.exp(-elapsedSec / tau)))));
  let label = progressMsg.generating;
  if (isEdit) {
    if (elapsedSec < 45) label = progressMsg.editDecompose;
    else if (elapsedSec < 150) label = progressMsg.editApply;
    else label = progressMsg.editRender;
  }
  return { pct, elapsedSec, label };
}

export function VideoTab({
  user,
  onOpenAuth,
  onGoToProfile,
  mode: controlledMode,
  onModeChange,
  prompt: controlledPrompt,
  onPromptChange,
  editPrompt: controlledEditPrompt,
  onEditPromptChange,
  editReferenceUrl: controlledEditReferenceUrl,
  onEditReferenceUrlChange,
  editSourceFile: controlledEditSourceFile,
  onEditSourceFileChange,
  editHistoryJobId: controlledEditHistoryJobId,
  onEditHistoryJobIdChange,
  duration: controlledDuration,
  onDurationChange,
}: VideoTabProps) {
  const { locale, t } = useLocale();
  const m = t.video;
  const dateLocale = locale === 'en' ? 'en-US' : 'vi-VN';
  const [internalMode, setInternalMode] = useState<VideoMode>('edit');
  const mode = controlledMode ?? internalMode;
  const setMode = (next: VideoMode) => {
    setInternalMode(next);
    onModeChange?.(next);
  };
  const editFileInputRef = useRef<HTMLInputElement>(null);
  const [internalLocalVideoFile, setInternalLocalVideoFile] = useState<File | null>(null);
  const localVideoFile = controlledEditSourceFile !== undefined ? controlledEditSourceFile : internalLocalVideoFile;
  const setLocalVideoFile = (file: File | null) => {
    setInternalLocalVideoFile(file);
    onEditSourceFileChange?.(file);
  };
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);
  const [internalSelectedHistoryJobId, setInternalSelectedHistoryJobId] = useState<string | null>(null);
  const selectedHistoryJobId =
    controlledEditHistoryJobId !== undefined ? controlledEditHistoryJobId : internalSelectedHistoryJobId;
  const setSelectedHistoryJobId = (id: string | null) => {
    setInternalSelectedHistoryJobId(id);
    onEditHistoryJobIdChange?.(id);
  };
  const [internalEditPrompt, setInternalEditPrompt] = useState('');
  const editPrompt = controlledEditPrompt !== undefined ? controlledEditPrompt : internalEditPrompt;
  const setEditPrompt = (val: string) => {
    setInternalEditPrompt(val);
    onEditPromptChange?.(val);
  };
  const [internalEditReferenceUrl, setInternalEditReferenceUrl] = useState('');
  const editReferenceUrl =
    controlledEditReferenceUrl !== undefined ? controlledEditReferenceUrl : internalEditReferenceUrl;
  const setEditReferenceUrl = (val: string) => {
    setInternalEditReferenceUrl(val);
    onEditReferenceUrlChange?.(val);
  };
  const [internalPrompt, setInternalPrompt] = useState('');
  const prompt = controlledPrompt !== undefined ? controlledPrompt : internalPrompt;
  const setPrompt = (val: string) => {
    setInternalPrompt(val);
    onPromptChange?.(val);
  };
  const [internalDuration, setInternalDuration] = useState<number>(DEFAULT_VIDEO_DURATION);
  const duration = controlledDuration !== undefined ? controlledDuration : internalDuration;
  const setDuration = (val: number) => {
    setInternalDuration(val);
    onDurationChange?.(val);
  };
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [selectedContextIds, setSelectedContextIds] = useState<string[]>([]);
  const [balance, setBalance] = useState<number>(0);
  const [ratePerSecMicro, setRatePerSecMicro] = useState<number>(0);
  const [costMicro, setCostMicro] = useState<number>(0);
  const [costUsd, setCostUsd] = useState<number>(0);
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [starting, setStarting] = useState(false);
  const [notice, setNotice] = useState<{ type: 'error' | 'success'; text: string } | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [nowMs, setNowMs] = useState<number>(() => Date.now());

  const profileMediaList = mediaList.filter((m) => m.kind === 'profile');
  const contextMediaList = mediaList.filter((m) => m.kind === 'context');
  const selectedProfile = profileMediaList.find((m) => m.id === selectedProfileId) || null;
  const canAfford = costMicro > 0 ? balance >= costMicro : true;
  const canGenerate = canAfford && !!selectedProfile && !!prompt.trim();

  const completedJobs = jobs.filter((j) => j.status === 'completed' && j.video_path);
  const selectedHistoryJob = completedJobs.find((j) => j.id === selectedHistoryJobId) || null;
  const editSourceUrl = localVideoUrl || (selectedHistoryJob ? videoFileUrl(selectedHistoryJob) : null);
  const editSourceName = localVideoFile?.name || selectedHistoryJob?.prompt || null;
  const canApplyEdit = Boolean(editSourceUrl && editPrompt.trim());

  useEffect(() => {
    if (!localVideoFile || typeof URL.createObjectURL !== 'function') {
      setLocalVideoUrl(null);
      return;
    }
    const url = URL.createObjectURL(localVideoFile);
    setLocalVideoUrl(url);
    return () => {
      if (typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(url);
      }
    };
  }, [localVideoFile]);

  const clearEditSource = () => {
    setLocalVideoFile(null);
    setSelectedHistoryJobId(null);
  };

  const isJobExpanded = (job: VideoJob): boolean => {
    if (expandedIds[job.id] !== undefined) {
      return expandedIds[job.id];
    }
    return job.status === 'pending' || job.status === 'running';
  };

  const toggleJobExpanded = (jobId: string, currentExpanded: boolean) => {
    setExpandedIds((prev) => ({
      ...prev,
      [jobId]: !currentExpanded,
    }));
  };

  const hasAnyExpanded = jobs.some((j) => isJobExpanded(j));
  const toggleAllExpanded = () => {
    const nextState = !hasAnyExpanded;
    const nextMap: Record<string, boolean> = {};
    jobs.forEach((j) => {
      nextMap[j.id] = nextState;
    });
    setExpandedIds(nextMap);
  };

  const fetchMedia = async () => {
    try {
      const res = await apiJson<{ ok: boolean; media: MediaItem[] }>('/api/media');
      if (res.ok && res.media) {
        setMediaList(res.media);
        const profs = res.media.filter((m) => m.kind === 'profile');
        setSelectedProfileId((prev) => {
          if (prev && profs.some((p) => p.id === prev)) return prev;
          return profs[0]?.id ?? null;
        });
        const ctxIds = new Set(res.media.filter((m) => m.kind === 'context').map((m) => m.id));
        setSelectedContextIds((prev) => prev.filter((id) => ctxIds.has(id)));
      }
    } catch {
      // ignore
    }
  };

  const fetchCreditsAndEstimate = async () => {
    try {
      const est = await apiJson<{
        ok: boolean;
        cost_micro?: number;
        cost_usd?: number;
        rate_per_sec_micro?: number;
        balance?: number;
      }>('/api/videos/estimate', {
        method: 'POST',
      });
      if (est.ok && typeof est.balance === 'number') {
        setBalance(est.balance);
        if (typeof est.cost_micro === 'number') setCostMicro(est.cost_micro);
        if (typeof est.cost_usd === 'number') setCostUsd(est.cost_usd);
        if (typeof est.rate_per_sec_micro === 'number') setRatePerSecMicro(est.rate_per_sec_micro);
        return;
      }
    } catch {
      // fallback to /api/credits
    }
    try {
      const res = await apiJson<{ ok: boolean; balance: number; rate_per_sec_micro?: number }>('/api/credits');
      if (res.ok && typeof res.balance === 'number') {
        setBalance(res.balance);
        if (typeof res.rate_per_sec_micro === 'number') {
          setRatePerSecMicro(res.rate_per_sec_micro);
          const computedCost = duration * res.rate_per_sec_micro;
          setCostMicro(computedCost);
          setCostUsd(Number((computedCost / 1000000).toFixed(2)));
        }
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    if (ratePerSecMicro > 0) {
      const computedCost = duration * ratePerSecMicro;
      setCostMicro(computedCost);
      setCostUsd(Number((computedCost / 1000000).toFixed(2)));
    }
  }, [duration, ratePerSecMicro]);

  const fetchJobs = async () => {
    try {
      const res = await apiJson<{ ok: boolean; jobs: VideoJob[] }>('/api/videos');
      if (res.ok && res.jobs) {
        setJobs(res.jobs);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    if (!user) return;
    fetchMedia();
    fetchCreditsAndEstimate();
    fetchJobs();
  }, [user]);

  // Polling for active jobs
  useEffect(() => {
    if (!user) return;
    const hasActive = jobs.some((j) => j.status === 'pending' || j.status === 'running');
    if (!hasActive) return;

    const timer = setInterval(() => {
      fetchJobs();
      fetchCreditsAndEstimate();
    }, 3000);
    return () => clearInterval(timer);
  }, [user, jobs]);

  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === 'pending' || j.status === 'running');
    if (!hasActive) return;
    const tick = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(tick);
  }, [jobs]);

  const handleStartGeneration = async () => {
    if (!selectedProfile) {
      setNotice({ type: 'error', text: m.needProfileNotice });
      return;
    }
    if (!prompt.trim()) {
      setNotice({ type: 'error', text: m.needPromptNotice });
      return;
    }
    try {
      setStarting(true);
      setNotice(null);
      const res = await apiJson<{ ok: boolean; job: VideoJob }>('/api/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          profile_media_id: selectedProfile.id,
          context_media_ids: selectedContextIds,
          duration,
        }),
      });
      if (res.ok) {
        setShowConfirm(false);
        setPrompt('');
        setSelectedContextIds([]);
        setNotice({ type: 'success', text: m.createdNotice(duration) });
        if (res.job) {
          setJobs((prev) => [res.job, ...prev.filter((j) => j.id !== res.job.id)]);
          setExpandedIds((prev) => ({ ...prev, [res.job.id]: true }));
        }
        fetchJobs();
        fetchCreditsAndEstimate();
      }
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.createError });
    } finally {
      setStarting(false);
    }
  };

  const handleStartEdit = async () => {
    if (!editSourceUrl || !editPrompt.trim()) return;
    try {
      setStarting(true);
      setNotice(null);
      const refUrl = editReferenceUrl.trim();
      let res: { ok: boolean; job?: VideoJob };
      if (localVideoFile) {
        const headers: Record<string, string> = {
          'Content-Type': localVideoFile.type || 'video/mp4',
          'X-Edit-Prompt': encodeURIComponent(editPrompt.trim()),
        };
        if (refUrl) {
          headers['X-Reference-Url'] = encodeURIComponent(refUrl);
        }
        res = await apiJson<{ ok: boolean; job?: VideoJob }>('/api/videos/edit', {
          method: 'POST',
          headers,
          body: localVideoFile,
        });
      } else if (selectedHistoryJob) {
        res = await apiJson<{ ok: boolean; job?: VideoJob }>('/api/videos/edit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_job_id: selectedHistoryJob.id,
            prompt: editPrompt.trim(),
            reference_video_url: refUrl || undefined,
          }),
        });
      } else {
        return;
      }
      if (res.ok) {
        clearEditSource();
        setEditPrompt('');
        setEditReferenceUrl('');
        setNotice({ type: 'success', text: m.edit.createdNotice });
        if (res.job) {
          setJobs((prev) => [res.job!, ...prev.filter((j) => j.id !== res.job!.id)]);
          setExpandedIds((prev) => ({ ...prev, [res.job!.id]: true }));
        }
        fetchJobs();
      }
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.edit.createError });
    } finally {
      setStarting(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      await apiJson(`/api/videos/${jobId}/cancel`, { method: 'POST' });
      fetchJobs();
      fetchCreditsAndEstimate();
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.cancelError });
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
      await apiJson(`/api/videos/${jobId}/delete`, { method: 'POST' });
      fetchJobs();
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.deleteError });
      fetchJobs();
    }
  };

  if (!user) {
    return (
      <section className="panel">
        <div className="empty">
          <span className="gate-icon">🔒</span>
          <h2>{t.authGate.title}</h2>
          <p className="muted">{m.authSubtitle}</p>
          <button type="button" className="primary auth-gate-btn" onClick={onOpenAuth}>
            {t.authGate.button}
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="video-tab">
      {notice && <div className={`notice ${notice.type} video-notice-box`}>{notice.text}</div>}

      {/* Main Creation / Edit Form */}
      <section className="panel">
        <div className="video-mode-tabs" role="tablist">
          {(['edit', 'generate'] as VideoMode[]).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={mode === id}
              className={`video-mode-btn ${mode === id ? 'active' : ''}`}
              onClick={() => {
                setMode(id);
                setNotice(null);
              }}
            >
              {m.modes[id]}
            </button>
          ))}
        </div>

        {mode === 'edit' ? (
          <>
            <div className="video-header-row">
              <h2 className="video-section-heading">{m.edit.heading}</h2>
            </div>

            <div className="video-form-group">
              <div className="video-group-label">{m.edit.sourceLabel}</div>
              {editSourceUrl ? (
                <div className="video-edit-preview">
                  <div className="video-edit-source-bar">
                    <span className="video-edit-source-name">{editSourceName}</span>
                    <button type="button" className="media-action-btn" onClick={clearEditSource}>
                      {m.edit.clearSource}
                    </button>
                  </div>
                  <video controls playsInline className="video-player" src={editSourceUrl} />
                </div>
              ) : (
                <>
                  <button type="button" className="picker" onClick={() => editFileInputRef.current?.click()}>
                    <input
                      ref={editFileInputRef}
                      type="file"
                      accept="video/*"
                      hidden
                      onChange={(e) => {
                        const file = e.target.files?.[0] ?? null;
                        e.target.value = '';
                        if (file) {
                          setLocalVideoFile(file);
                          setSelectedHistoryJobId(null);
                          setNotice(null);
                        }
                      }}
                    />
                    <span className="picker-icon">⇪</span>
                    <span>
                      <strong>{m.edit.chooseFile}</strong>
                      <small className="muted">{m.edit.fileHint}</small>
                    </span>
                  </button>

                  {completedJobs.length > 0 && (
                    <div className="video-edit-history">
                      <small className="muted">{m.edit.orFromHistory}</small>
                      <div className="video-edit-history-list">
                        {completedJobs.map((j) => (
                          <button
                            key={j.id}
                            type="button"
                            className="video-edit-history-chip"
                            onClick={() => {
                              setLocalVideoFile(null);
                              setSelectedHistoryJobId(j.id);
                              setNotice(null);
                            }}
                          >
                            {j.prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {editReferenceUrl.trim() && (
              <div className="video-edit-ref-bar">
                <span className="muted">{m.edit.referenceLabel}</span>
                <a href={editReferenceUrl} target="_blank" rel="noreferrer" className="video-edit-ref-link">
                  {editReferenceUrl}
                </a>
                <button type="button" className="media-action-btn" onClick={() => setEditReferenceUrl('')}>
                  {m.edit.clearReference}
                </button>
              </div>
            )}

            <div className="video-form-group">
              <div className="video-group-label">{m.edit.promptLabel}</div>
              <textarea
                className="prompt-textarea video-edit-textarea"
                placeholder={m.edit.promptPlaceholder}
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
              />
            </div>

            <button type="button" className="primary" disabled={!canApplyEdit || starting} onClick={handleStartEdit}>
              {starting ? m.edit.submittingBtn : m.edit.applyBtn}
            </button>
          </>
        ) : (
          <>
            <div className="video-header-row">
              <h2 className="video-section-heading">{m.heading}</h2>
              {onGoToProfile && (
                <button type="button" className="media-action-btn" onClick={onGoToProfile}>
                  {m.goToProfile}
                </button>
              )}
            </div>

            {/* 1. Profile Image Picker (Select from Profile tab uploads only) */}
            <div className="video-form-group">
              <div className="video-group-label">{m.step1Label}</div>
              {profileMediaList.length > 0 ? (
                <div className="context-picker-grid context-picker-aligned">
                  {profileMediaList.map((mItem) => {
                    const isSelected = selectedProfileId === mItem.id;
                    return (
                      <div
                        key={mItem.id}
                        data-testid={`profile-select-${mItem.id}`}
                        className={`context-thumb-selectable ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedProfileId(isSelected ? null : mItem.id)}
                      >
                        <img src={mediaUrl(mItem)} alt="Profile" />
                        {isSelected && <div className="context-check">✓</div>}
                      </div>
                    );
                  })}
                  <span className="video-step-desc">{selectedProfile ? m.profileSelected : m.profileSelectHint}</span>
                </div>
              ) : (
                <div className="video-alert-row">
                  <span className="video-alert-warn">{m.noProfileWarn}</span>
                </div>
              )}
            </div>

            {/* 2. Context Images Selector (Select from Profile tab uploads only) */}
            <div className="video-form-group">
              <div className="video-group-label">
                {m.step2Label(selectedContextIds.length, contextMediaList.length)}
              </div>
              {contextMediaList.length > 0 ? (
                <div className="context-picker-grid">
                  {contextMediaList.map((mItem) => {
                    const isSelected = selectedContextIds.includes(mItem.id);
                    return (
                      <div
                        key={mItem.id}
                        data-testid={`context-select-${mItem.id}`}
                        className={`context-thumb-selectable ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedContextIds((prev) =>
                            isSelected ? prev.filter((id) => id !== mItem.id) : [...prev, mItem.id],
                          );
                        }}
                      >
                        <img src={mediaUrl(mItem)} alt="Context" />
                        {isSelected && <div className="context-check">✓</div>}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <small className="muted video-duration-hint">{m.noContextHint}</small>
              )}
            </div>

            {/* 3. Prompt Input */}
            <div className="video-form-group">
              <div className="video-group-label">{m.step3Label(duration)}</div>
              <textarea
                className="prompt-textarea"
                placeholder={m.promptPlaceholder}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>

            {/* Cost Estimation */}
            <div className="cost-card cost-card-spaced">
              <div>
                <div>
                  {m.durationLabel} <strong>{m.durationValue(duration)}</strong> (360p)
                </div>
              </div>
            </div>

            {!canAfford && <div className="video-error-box">{m.insufficientBalance(costUsd.toFixed(2))}</div>}

            <button
              type="button"
              className="primary"
              disabled={!canGenerate || starting}
              onClick={() => setShowConfirm(true)}
            >
              {starting ? m.submittingBtn : m.generateBtn(costUsd.toFixed(2))}
            </button>
          </>
        )}
      </section>

      {/* Confirm Modal */}
      {showConfirm && (
        <div className="modal-overlay">
          <div className="confirm-dialog">
            <h3>{m.confirmTitle}</h3>
            <p className="muted dialog-subtext">{m.confirmDesc(costUsd.toFixed(2), duration)}</p>

            <div className="confirm-details">
              <div className="confirm-row">
                <span>{m.durationLabel}</span>
                <strong>{m.durationValue(duration)} (360p)</strong>
              </div>
              <div className="confirm-row">
                <span>{m.confirmContextImages}</span>
                <strong>{m.confirmContextCount(selectedContextIds.length)}</strong>
              </div>
              <div className="confirm-row">
                <span>{m.confirmCost}</span>
                <strong>${costUsd.toFixed(2)}</strong>
              </div>
              <div className="confirm-row">
                <span>{m.confirmBalance}</span>
                <span>${(balance / 1000000).toFixed(2)}</span>
              </div>
              <div className="confirm-row confirm-row-total">
                <span>{m.confirmRemaining}</span>
                <strong>${((balance - costMicro) / 1000000).toFixed(2)}</strong>
              </div>
            </div>

            <div className="dialog-actions">
              <button type="button" className="btn-secondary" onClick={() => setShowConfirm(false)} disabled={starting}>
                {t.common.cancel}
              </button>
              <button type="button" className="btn-confirm" onClick={handleStartGeneration} disabled={starting}>
                {starting ? m.submittingBtn : m.confirmBtn}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Video Generation History */}
      <section className="panel">
        <div className="video-header-row">
          <h2 className="video-section-heading">{m.historyHeading(jobs.length)}</h2>
          {jobs.length > 0 && (
            <button type="button" className="media-action-btn" onClick={toggleAllExpanded}>
              {hasAnyExpanded ? m.collapseAll : m.expandAll}
            </button>
          )}
        </div>

        {jobs.length === 0 ? (
          <p className="muted history-empty-text">{m.historyEmpty}</p>
        ) : (
          <div className="video-history-list">
            {jobs.map((j) => {
              const expanded = isJobExpanded(j);
              return (
                <div key={j.id} className={`video-card ${expanded ? 'expanded' : 'collapsed'}`}>
                  <div
                    className="video-card-head"
                    onClick={() => toggleJobExpanded(j.id, expanded)}
                    title={expanded ? m.cardCollapseTitle : m.cardExpandTitle}
                  >
                    <div className="video-card-head-left">
                      <span className={`status-chip ${j.status}`}>{m.status[j.status]}</span>
                      <span className="duration-tag">
                        {j.job_type === 'edit'
                          ? m.edit.jobBadge
                          : `${ratePerSecMicro > 0 ? Math.round(j.cost / ratePerSecMicro) : duration}${t.common.secondsShort}`}
                      </span>
                      {!expanded && <span className="video-card-preview-prompt">{j.prompt}</span>}
                    </div>

                    <div className="video-card-head-right">
                      <span className="video-card-time">
                        {j.created_at
                          ? new Date(j.created_at).toLocaleTimeString(dateLocale, {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : ''}
                      </span>

                      {j.status === 'pending' && (
                        <button
                          type="button"
                          className="media-action-btn danger"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCancelJob(j.id);
                          }}
                        >
                          {m.cancelAndRefund}
                        </button>
                      )}

                      {j.status === 'completed' && j.video_path && (
                        <a
                          href={videoDownloadUrl(j)}
                          download={`video-${j.id}.mp4`}
                          className="media-action-btn download-btn"
                          title={m.downloadTitle}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {m.downloadBtn}
                        </a>
                      )}

                      {(j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') && (
                        <button
                          type="button"
                          className="media-action-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteJob(j.id);
                          }}
                        >
                          {t.common.delete}
                        </button>
                      )}

                      <span className="video-collapse-chevron" aria-label={expanded ? m.collapseAria : m.expandAria}>
                        {expanded ? '▲' : '▼'}
                      </span>
                    </div>
                  </div>

                  <div className="video-card-body" style={{ display: expanded ? 'flex' : 'none' }}>
                    {(j.status === 'pending' || j.status === 'running') &&
                      (() => {
                        const prog = estimateVideoProgress(j, nowMs, m.progress);
                        return (
                          <div className="video-progress-wrap">
                            <div
                              className="bar running"
                              role="progressbar"
                              aria-valuenow={prog.pct}
                              aria-valuemin={0}
                              aria-valuemax={100}
                            >
                              <span style={{ width: `${prog.pct}%` }} />
                            </div>
                            <div className="video-progress-meta muted">
                              <span>{prog.label}</span>
                              <span>
                                {prog.pct}% · {formatElapsed(prog.elapsedSec)}
                              </span>
                            </div>
                          </div>
                        );
                      })()}

                    <div className="video-prompt-box">
                      <div className="video-prompt-label">
                        <strong>{m.promptBoxLabel}</strong>
                        <button
                          type="button"
                          className="copy-prompt-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard?.writeText(j.prompt);
                            setNotice({ type: 'success', text: m.copiedPromptNotice });
                          }}
                        >
                          {t.common.copy}
                        </button>
                      </div>
                      <div className="video-prompt-text">{j.prompt}</div>
                    </div>

                    {j.status === 'completed' && j.video_path && (
                      <div className="video-player-box">
                        <video controls playsInline className="video-player" src={videoFileUrl(j)} />
                      </div>
                    )}

                    {j.status === 'failed' && (
                      <div className="video-error-text">
                        {m.errorPrefix} {j.error || m.defaultJobError}
                        <div className="video-success-msg">
                          {m.refundedNotice(j.cost_usd ? `${j.cost_usd}` : `${(j.cost / 1000000).toFixed(2)}`)}
                        </div>
                      </div>
                    )}

                    <div className="video-card-footer">
                      <span>
                        {m.jobIdPrefix} {j.id}
                      </span>
                      <span>{j.created_at ? new Date(j.created_at).toLocaleString(dateLocale) : ''}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
