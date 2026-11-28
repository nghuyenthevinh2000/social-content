import { IonIcon, IonToast } from '@ionic/react';
import { bookmarkOutline, downloadOutline, trashOutline } from 'ionicons/icons';
import { useEffect, useRef, useState } from 'react';

import { apiJson } from '../api';
import type { User } from '../firebase';
import { type LocaleMessages, useLocale } from '../locales';
import {
  canRenderVideoOnClient,
  type EditPlan,
  probeAndExtractKeyframes,
  renderVideoEditPlan,
} from '../videoClientRender';
import { deleteJobBlob, loadJobBlob, saveJobBlob } from '../videoEditDraft';

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
  job_type?: 'generate' | 'edit' | 'edit_plan';
  reference_video_url?: string | null;
  template_id?: string | null;
  produced_template?: Record<string, any> | null;
};

export type VideoTemplate = {
  id: string;
  slug: string;
  name: string;
  source: 'builtin' | 'user';
  author_id: string | null;
  is_owner: boolean;
  visibility: 'public' | 'private';
  config: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

export type VideoMode = 'edit' | 'generate' | 'history';

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
  editTemplateId?: string | null;
  onEditTemplateIdChange?: (id: string | null) => void;
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
  const isEdit = job.job_type === 'edit' || job.job_type === 'edit_plan';
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
  editTemplateId: controlledEditTemplateId,
  onEditTemplateIdChange,
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
  const [internalSelectedTemplateId, setInternalSelectedTemplateId] = useState<string | null>(null);
  const selectedTemplateId =
    controlledEditTemplateId !== undefined ? controlledEditTemplateId : internalSelectedTemplateId;
  const setSelectedTemplateId = (id: string | null) => {
    setInternalSelectedTemplateId(id);
    onEditTemplateIdChange?.(id);
  };
  const [templates, setTemplates] = useState<VideoTemplate[]>([]);
  const [saveTemplateJobId, setSaveTemplateJobId] = useState<string | null>(null);
  const [saveTemplateName, setSaveTemplateName] = useState('');
  const [saveTemplateVisibility, setSaveTemplateVisibility] = useState<'public' | 'private'>('public');
  const [savingTemplate, setSavingTemplate] = useState(false);
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
  const [localRenderedUrls, setLocalRenderedUrls] = useState<Record<string, string>>({});
  const [clientRenderPct, setClientRenderPct] = useState<Record<string, number>>({});
  const [clientRenderErrors, setClientRenderErrors] = useState<Record<string, string>>({});
  const renderingJobIdsRef = useRef<Set<string>>(new Set());

  const profileMediaList = mediaList.filter((m) => m.kind === 'profile');
  const contextMediaList = mediaList.filter((m) => m.kind === 'context');
  const selectedProfile = profileMediaList.find((m) => m.id === selectedProfileId) || null;
  const canAfford = costMicro > 0 ? balance >= costMicro : true;
  const canGenerate = canAfford && !!selectedProfile && !!prompt.trim();

  const completedJobs = jobs.filter((j) => j.status === 'completed' && j.video_path);
  const selectedHistoryJob = completedJobs.find((j) => j.id === selectedHistoryJobId) || null;
  const editSourceUrl = localVideoUrl || (selectedHistoryJob ? videoFileUrl(selectedHistoryJob) : null);
  const editSourceName = localVideoFile?.name || selectedHistoryJob?.prompt || null;
  const canApplyEdit = Boolean(editSourceUrl && (editPrompt.trim() || selectedTemplateId));

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

  const fetchTemplates = async () => {
    try {
      const res = await apiJson<{ ok: boolean; templates?: VideoTemplate[] }>('/api/videos/templates');
      if (res.ok && Array.isArray(res.templates)) {
        setTemplates(res.templates);
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
    fetchTemplates();
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

  useEffect(() => {
    const planJobs = jobs.filter(
      (j) =>
        j.job_type === 'edit_plan' &&
        j.status === 'completed' &&
        !j.video_path?.endsWith('.mp4') &&
        !localRenderedUrls[j.id] &&
        !clientRenderErrors[j.id] &&
        !renderingJobIdsRef.current.has(j.id),
    );
    if (planJobs.length === 0) return;

    for (const j of planJobs) {
      renderingJobIdsRef.current.add(j.id);
      void (async () => {
        try {
          let outBlob = await loadJobBlob(`plan_out_${j.id}`);
          if (!outBlob) {
            const srcBlob = await loadJobBlob(`plan_src_${j.id}`);
            if (!srcBlob) {
              setClientRenderErrors((prev) => ({
                ...prev,
                [j.id]: 'Source video not found on this device.',
              }));
              return;
            }
            setClientRenderPct((prev) => ({ ...prev, [j.id]: 0 }));
            const planRes = await apiJson<{ ok: boolean; plan?: EditPlan }>(
              `/api/videos/${encodeURIComponent(j.id)}/plan`,
            );
            if (!planRes.ok || !planRes.plan) {
              throw new Error('Missing edit plan');
            }
            const srcFile =
              srcBlob instanceof File ? srcBlob : new File([srcBlob], `source-${j.id}.mp4`, { type: 'video/mp4' });
            outBlob = await renderVideoEditPlan(srcFile, planRes.plan, (pct) => {
              setClientRenderPct((prev) => ({ ...prev, [j.id]: pct }));
            });
          }

          setLocalRenderedUrls((prev) => ({ ...prev, [j.id]: URL.createObjectURL(outBlob!) }));
          try {
            const upRes = await apiJson<{ ok: boolean; job?: VideoJob }>(
              `/api/videos/${encodeURIComponent(j.id)}/file`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'video/mp4' },
                body: outBlob,
              },
            );
            if (upRes.ok && upRes.job) {
              setJobs((prev) => prev.map((item) => (item.id === j.id ? upRes.job! : item)));
              await deleteJobBlob(`plan_src_${j.id}`);
              await deleteJobBlob(`plan_out_${j.id}`);
            } else {
              await saveJobBlob(`plan_out_${j.id}`, outBlob);
            }
          } catch {
            await saveJobBlob(`plan_out_${j.id}`, outBlob);
          }
        } catch (err: any) {
          setClientRenderErrors((prev) => ({
            ...prev,
            [j.id]: err?.message || 'Client render failed',
          }));
        } finally {
          setClientRenderPct((prev) => {
            const next = { ...prev };
            delete next[j.id];
            return next;
          });
          renderingJobIdsRef.current.delete(j.id);
        }
      })();
    }
  }, [jobs, localRenderedUrls, clientRenderErrors]);

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
        setMode('history');
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
    if (!editSourceUrl || (!editPrompt.trim() && !selectedTemplateId)) return;
    try {
      setStarting(true);
      setNotice(null);
      const refUrl = editReferenceUrl.trim();
      const tplId = selectedTemplateId || undefined;
      let res: { ok: boolean; job?: VideoJob } | null = null;
      if (localVideoFile) {
        let usedClientPlan = false;
        if (await canRenderVideoOnClient()) {
          try {
            const { probe, keyframes_b64, audio_b64 } = await probeAndExtractKeyframes(localVideoFile);
            res = await apiJson<{ ok: boolean; job?: VideoJob }>('/api/videos/edit-plan', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                prompt: editPrompt.trim(),
                probe,
                keyframes_b64,
                audio_b64: audio_b64 || undefined,
                audio_format: audio_b64 ? 'wav' : undefined,
                reference_video_url: refUrl || undefined,
                template_id: tplId,
              }),
            });
            if (res.ok && res.job) {
              await saveJobBlob(`plan_src_${res.job.id}`, localVideoFile);
            }
            usedClientPlan = true;
          } catch {
            usedClientPlan = false;
          }
        }
        if (!usedClientPlan) {
          const headers: Record<string, string> = {
            'Content-Type': localVideoFile.type || 'video/mp4',
            'X-Edit-Prompt': encodeURIComponent(editPrompt.trim()),
          };
          if (refUrl) {
            headers['X-Reference-Url'] = encodeURIComponent(refUrl);
          }
          if (tplId) {
            headers['X-Template-Id'] = encodeURIComponent(tplId);
          }
          res = await apiJson<{ ok: boolean; job?: VideoJob }>('/api/videos/edit', {
            method: 'POST',
            headers,
            body: localVideoFile,
          });
        }
      } else if (selectedHistoryJob) {
        res = await apiJson<{ ok: boolean; job?: VideoJob }>('/api/videos/edit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_job_id: selectedHistoryJob.id,
            prompt: editPrompt.trim(),
            reference_video_url: refUrl || undefined,
            template_id: tplId,
          }),
        });
      } else {
        return;
      }
      if (res?.ok) {
        clearEditSource();
        setEditPrompt('');
        setEditReferenceUrl('');
        setSelectedTemplateId(null);
        setNotice({ type: 'success', text: m.edit.createdNotice });
        if (res.job) {
          setJobs((prev) => [res.job!, ...prev.filter((j) => j.id !== res.job!.id)]);
          setExpandedIds((prev) => ({ ...prev, [res.job!.id]: true }));
        }
        setMode('history');
        fetchJobs();
      }
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.edit.createError });
    } finally {
      setStarting(false);
    }
  };

  const handleDeleteTemplate = async (tplId: string) => {
    try {
      await apiJson<{ ok: boolean }>(`/api/videos/templates/${encodeURIComponent(tplId)}/delete`, {
        method: 'POST',
      });
      setTemplates((prev) => prev.filter((item) => item.id !== tplId));
      if (selectedTemplateId === tplId) {
        setSelectedTemplateId(null);
      }
      setNotice({ type: 'success', text: m.edit.deletedTemplateNotice });
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.edit.deleteTemplateError });
    }
  };

  const handleSaveTemplate = async () => {
    if (!saveTemplateJobId || !saveTemplateName.trim()) return;
    try {
      setSavingTemplate(true);
      const res = await apiJson<{ ok: boolean; template?: VideoTemplate }>('/api/videos/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: saveTemplateJobId,
          name: saveTemplateName.trim(),
          visibility: saveTemplateVisibility,
        }),
      });
      if (res.ok) {
        setSaveTemplateJobId(null);
        setSaveTemplateName('');
        setSaveTemplateVisibility('public');
        setNotice({ type: 'success', text: m.edit.savedTemplateNotice });
        fetchTemplates();
      }
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || m.edit.saveTemplateError });
    } finally {
      setSavingTemplate(false);
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
      const existingUrl = localRenderedUrls[jobId];
      if (existingUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(existingUrl);
      }
      setLocalRenderedUrls((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
      void deleteJobBlob(`plan_src_${jobId}`);
      void deleteJobBlob(`plan_out_${jobId}`);
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
      <IonToast
        isOpen={!!notice}
        message={notice?.text}
        color={notice?.type === 'error' ? 'danger' : 'success'}
        duration={2500}
        position="top"
        onDidDismiss={() => setNotice(null)}
      />

      {/* Main Creation / Edit Form */}
      <section className="panel">
        <div className="video-mode-tabs" role="tablist">
          {(['edit', 'generate', 'history'] as VideoMode[]).map((id) => (
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

            {templates.length > 0 && (
              <div className="video-form-group">
                <div className="video-group-label">{m.edit.templateLabel}</div>
                <div className="template-picker-grid">
                  {templates.map((tpl) => {
                    const isSelected = selectedTemplateId === tpl.id;
                    const cfg = tpl.config || {};
                    const theme = cfg.theme || {};
                    const bgTop = theme.bgTop || '#1e293b';
                    const bgBot = theme.bgBot || '#0f172a';
                    const hookStyle = cfg.hook_card_style;
                    const stepStyle = cfg.step_anchor_style;
                    const ctaStyle = cfg.cta_style;
                    const subStyle = cfg.subtitle_style;
                    const hookBg = hookStyle?.bg_color || theme.red || '#b91c1c';
                    const hookText = hookStyle?.text_color || '#ffffff';
                    const stepText = stepStyle?.text_color || '#ffffff';
                    const stepStroke = stepStyle?.stroke_color || theme.cyan || '#0284c7';
                    const subColor = subStyle?.color || '#ffffff';
                    const subOutline = subStyle?.outline_color || '#000000';
                    const subHasBox = Boolean(subStyle && (subStyle.border_style === 3 || subStyle.bg_color));
                    const subSample = subStyle?.uppercase ? 'HELLO WORLD' : 'Hello World';
                    const ctaBg = ctaStyle?.bg_color || theme.card || '#ffffff';
                    const ctaText = ctaStyle?.text_color || theme.text || '#0f172a';
                    const ctaBorder = theme.cardBorder || stepStroke;
                    const grade = cfg.color_grade || {};
                    const anchorFilter = [
                      grade.contrast ? `contrast(${grade.contrast})` : '',
                      grade.saturation ? `saturate(${grade.saturation})` : '',
                      grade.brightness ? `brightness(${1 + Number(grade.brightness)})` : '',
                    ]
                      .filter(Boolean)
                      .join(' ');
                    const anchorProfile = selectedProfile || profileMediaList[0] || null;
                    return (
                      <div
                        key={tpl.id}
                        role="button"
                        tabIndex={0}
                        data-testid={`template-card-${tpl.id}`}
                        aria-pressed={isSelected}
                        className={`template-card ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedTemplateId(isSelected ? null : tpl.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedTemplateId(isSelected ? null : tpl.id);
                          }
                        }}
                      >
                        <div
                          className="template-swatch"
                          style={{ background: `linear-gradient(180deg, ${bgTop} 0%, ${bgBot} 100%)` }}
                        >
                          <div className="template-anchor" style={anchorFilter ? { filter: anchorFilter } : undefined}>
                            {anchorProfile ? (
                              <img className="template-anchor-img" src={mediaUrl(anchorProfile)} alt="" />
                            ) : (
                              <svg
                                className="template-anchor-svg"
                                viewBox="0 0 120 168"
                                aria-hidden="true"
                              >
                                <path
                                  d="M20 168 C22 132 38 118 60 118 C82 118 98 132 100 168 Z"
                                  fill="#334155"
                                />
                                <rect x="51" y="99" width="18" height="24" rx="8" fill="#e2a886" />
                                <path
                                  d="M35 66 C35 42 46 30 60 30 C74 30 85 42 85 66 C85 88 74 105 60 105 C46 105 35 88 35 66 Z"
                                  fill="#f1bfa0"
                                />
                                <path
                                  d="M34 62 C33 38 46 24 61 24 C76 24 87 38 86 62 C82 47 73 41 60 41 C47 41 38 47 34 62 Z"
                                  fill="#1e293b"
                                />
                                <circle cx="49" cy="67" r="2.6" fill="#1e293b" />
                                <circle cx="71" cy="67" r="2.6" fill="#1e293b" />
                                <path
                                  d="M52 84 Q60 90 68 84"
                                  fill="none"
                                  stroke="#b45349"
                                  strokeWidth="2.4"
                                  strokeLinecap="round"
                                />
                              </svg>
                            )}
                          </div>
                          <div className="template-overlays" aria-hidden="true">
                            {hookStyle && (
                              <span
                                className="template-overlay-hook"
                                style={{ background: hookBg, color: hookText }}
                              >
                                HOOK
                              </span>
                            )}
                            {stepStyle && (
                              <span
                                className="template-overlay-step"
                                style={{
                                  color: stepText,
                                  WebkitTextStroke: `2px ${stepStroke}`,
                                  textShadow: `0 1px 4px ${stepStroke}`,
                                }}
                              >
                                01 · STEP
                              </span>
                            )}
                            {subStyle ? (
                              <span
                                className={`template-overlay-sub ${subHasBox ? 'boxed' : ''}`}
                                style={{
                                  color: subColor,
                                  fontWeight: subStyle.bold === false ? 600 : 800,
                                  WebkitTextStroke: subHasBox ? undefined : `2px ${subOutline}`,
                                  textShadow: subHasBox ? undefined : `0 1px 4px ${subOutline}`,
                                  background: subHasBox ? subStyle.bg_color || 'rgba(0,0,0,0.72)' : undefined,
                                }}
                              >
                                {subSample}
                              </span>
                            ) : ctaStyle ? (
                              <span
                                className="template-overlay-cta"
                                style={{
                                  background: ctaBg,
                                  color: ctaText,
                                  borderColor: ctaBorder,
                                }}
                              >
                                CTA
                              </span>
                            ) : null}
                          </div>
                          {isSelected && <div className="context-check">✓</div>}
                          {tpl.is_owner && (
                            <button
                              type="button"
                              className="template-delete-btn"
                              aria-label={m.edit.deleteTemplateAria}
                              title={m.edit.deleteTemplateAria}
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleDeleteTemplate(tpl.id);
                              }}
                            >
                              <IonIcon icon={trashOutline} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                        <div className="template-card-meta">
                          <div className="template-card-name" title={tpl.name}>
                            {tpl.name}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <small className="muted">{m.edit.templateHint}</small>
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
        ) : mode === 'generate' ? (
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
        ) : (
          <>
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
                  const isPlanJob = j.job_type === 'edit_plan';
                  const localUrl = localRenderedUrls[j.id];
                  const renderPct = clientRenderPct[j.id];
                  const renderErr = clientRenderErrors[j.id];
                  const isServerMp4 = Boolean(j.video_path && (!isPlanJob || j.video_path.endsWith('.mp4')));
                  const playableUrl = localUrl || (isServerMp4 ? videoFileUrl(j) : null);
                  const downloadHref = isServerMp4 ? videoDownloadUrl(j) : localUrl || null;
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
                            {j.job_type === 'edit' || isPlanJob ? m.edit.jobBadge : m.aiJobBadge}
                          </span>
                          {!expanded && <span className="video-card-preview-prompt">{j.prompt}</span>}
                        </div>

                        <div className="video-card-head-right">
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

                          {j.status === 'completed' && j.produced_template && (
                            <button
                              type="button"
                              className="media-action-btn icon-action-btn"
                              aria-label={m.edit.saveTemplateBtn}
                              title={m.edit.saveTemplateBtn}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSaveTemplateJobId(j.id);
                                setSaveTemplateName('');
                                setSaveTemplateVisibility('public');
                              }}
                            >
                              <IonIcon icon={bookmarkOutline} aria-hidden="true" />
                            </button>
                          )}

                          {j.status === 'completed' && downloadHref && (
                            <a
                              href={downloadHref}
                              download={`video-${j.id}.mp4`}
                              className="media-action-btn icon-action-btn download-btn"
                              aria-label={m.downloadBtn}
                              title={m.downloadTitle}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <IonIcon icon={downloadOutline} aria-hidden="true" />
                            </a>
                          )}

                          {(j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled') && (
                            <button
                              type="button"
                              className="media-action-btn icon-action-btn"
                              aria-label={t.common.delete}
                              title={t.common.delete}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteJob(j.id);
                              }}
                            >
                              <IonIcon icon={trashOutline} aria-hidden="true" />
                            </button>
                          )}

                          <span
                            className="video-collapse-chevron"
                            aria-label={expanded ? m.collapseAria : m.expandAria}
                          >
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

                        {j.status === 'completed' && isPlanJob && renderPct !== undefined && !playableUrl && (
                          <div className="video-progress-wrap">
                            <div
                              className="bar running"
                              role="progressbar"
                              aria-valuenow={renderPct}
                              aria-valuemin={0}
                              aria-valuemax={100}
                            >
                              <span style={{ width: `${renderPct}%` }} />
                            </div>
                            <div className="video-progress-meta muted">
                              <span>{m.progress.editRender}</span>
                              <span>{renderPct}%</span>
                            </div>
                          </div>
                        )}

                        {j.status === 'completed' && isPlanJob && renderErr && (
                          <div className="video-error-text">
                            {m.errorPrefix} {renderErr}
                          </div>
                        )}

                        {j.status === 'completed' && playableUrl && (
                          <div className="video-player-box">
                            <video controls playsInline className="video-player" src={playableUrl} />
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

      {/* Save Template Modal */}
      {saveTemplateJobId && (
        <div className="modal-overlay">
          <div className="confirm-dialog">
            <h3>{m.edit.saveTemplateTitle}</h3>
            <div className="video-form-group">
              <label className="video-group-label" htmlFor="save-template-name">
                {m.edit.saveTemplateNameLabel}
              </label>
              <input
                id="save-template-name"
                type="text"
                className="template-modal-input"
                maxLength={80}
                placeholder={m.edit.saveTemplateNamePlaceholder}
                value={saveTemplateName}
                onChange={(e) => setSaveTemplateName(e.target.value)}
              />
            </div>
            <div className="video-form-group">
              <label className="video-group-label" htmlFor="save-template-visibility">
                {m.edit.saveTemplateVisibilityLabel}
              </label>
              <select
                id="save-template-visibility"
                className="template-modal-input"
                value={saveTemplateVisibility}
                onChange={(e) => setSaveTemplateVisibility(e.target.value === 'private' ? 'private' : 'public')}
              >
                <option value="public">{m.edit.saveTemplatePublic}</option>
                <option value="private">{m.edit.saveTemplatePrivate}</option>
              </select>
            </div>
            <div className="dialog-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setSaveTemplateJobId(null)}
                disabled={savingTemplate}
              >
                {t.common.cancel}
              </button>
              <button
                type="button"
                className="btn-confirm"
                onClick={handleSaveTemplate}
                disabled={savingTemplate || !saveTemplateName.trim()}
              >
                {m.edit.saveTemplateConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
