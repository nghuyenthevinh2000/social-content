import { useEffect, useState } from 'react';
import { apiJson } from '../api';
import type { User } from '../firebase';
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
};

type VideoTabProps = {
  user: User | null;
  onOpenAuth: () => void;
  onGoToProfile?: () => void;
  prompt?: string;
  onPromptChange?: (value: string) => void;
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

export function VideoTab({
  user,
  onOpenAuth,
  onGoToProfile,
  prompt: controlledPrompt,
  onPromptChange,
  duration: controlledDuration,
  onDurationChange,
}: VideoTabProps) {
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

  const profileMediaList = mediaList.filter((m) => m.kind === 'profile');
  const contextMediaList = mediaList.filter((m) => m.kind === 'context');
  const selectedProfile = profileMediaList.find((m) => m.id === selectedProfileId) || null;
  const canAfford = costMicro > 0 ? balance >= costMicro : true;
  const canGenerate = canAfford && !!selectedProfile && !!prompt.trim();

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

  const handleStartGeneration = async () => {
    if (!selectedProfile) {
      setNotice({ type: 'error', text: 'Vui lòng chọn ảnh chân dung mẫu (tải lên ở tab Hồ sơ).' });
      return;
    }
    if (!prompt.trim()) {
      setNotice({ type: 'error', text: 'Vui lòng nhập lời thoại / nội dung cho video.' });
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
        setNotice({ type: 'success', text: `Đã gửi yêu cầu tạo video (${duration}s)! Hệ thống đang xử lý.` });
        if (res.job) {
          setJobs((prev) => [res.job, ...prev.filter((j) => j.id !== res.job.id)]);
          setExpandedIds((prev) => ({ ...prev, [res.job.id]: true }));
        }
        fetchJobs();
        fetchCreditsAndEstimate();
      }
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || 'Không thể tạo video.' });
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
      setNotice({ type: 'error', text: err?.message || 'Không thể huỷ job.' });
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
      await apiJson(`/api/videos/${jobId}/delete`, { method: 'POST' });
      fetchJobs();
    } catch (err: any) {
      setNotice({ type: 'error', text: err?.message || 'Không thể xoá job.' });
      fetchJobs();
    }
  };

  if (!user) {
    return (
      <section className="panel">
        <h2>Tạo Video AI ({duration}s)</h2>
        <div style={{ padding: '24px 0', textAlign: 'center' }}>
          <p className="muted" style={{ marginBottom: 16 }}>
            Vui lòng đăng nhập để tạo video ngắn bằng AI (Omni Flash).
          </p>
          <button type="button" className="primary" onClick={onOpenAuth}>
            Đăng nhập ngay
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="video-tab">
      {notice && (
        <div className={`notice ${notice.type}`} style={{ padding: 12, borderRadius: 10, marginBottom: 8 }}>
          {notice.text}
        </div>
      )}

      {/* Credit Status */}
      <div className="credits-badge-bar">
        <span>Số dư của bạn:</span>
        <div className="credits-badge">
          <span>💰</span>
          <span>
            ${(balance / 1000000).toFixed(2)} ({balance.toLocaleString()} credits)
          </span>
        </div>
      </div>

      {/* Main Creation Form */}
      <section className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Tạo video AI Cá Nhân</h2>
          {onGoToProfile && (
            <button type="button" className="media-action-btn" onClick={onGoToProfile}>
              Đi tới Hồ sơ
            </button>
          )}
        </div>

        {/* 1. Profile Image Picker (Select from Profile tab uploads only) */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)', marginBottom: 6 }}>
            1. Ảnh chân dung (Bắt buộc — chọn từ Hồ sơ)
          </div>
          {profileMediaList.length > 0 ? (
            <div className="context-picker-grid" style={{ alignItems: 'center' }}>
              {profileMediaList.map((m) => {
                const isSelected = selectedProfileId === m.id;
                return (
                  <div
                    key={m.id}
                    data-testid={`profile-select-${m.id}`}
                    className={`context-thumb-selectable ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedProfileId(isSelected ? null : m.id)}
                  >
                    <img src={mediaUrl(m)} alt="Profile" />
                    {isSelected && <div className="context-check">✓</div>}
                  </div>
                );
              })}
              <span style={{ fontSize: 13 }}>
                {selectedProfile ? 'Đã chọn ảnh đại diện mẫu' : 'Nhấn vào ảnh để chọn'}
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: '#c92a2a' }}>
                ⚠️ Chưa có ảnh chân dung mẫu. Vui lòng tải ảnh lên ở tab Hồ sơ.
              </span>
            </div>
          )}
        </div>

        {/* 2. Context Images Selector (Select from Profile tab uploads only) */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)', marginBottom: 6 }}>
            2. Ảnh bối cảnh / Sản phẩm (Tuỳ chọn — đã chọn {selectedContextIds.length}/{contextMediaList.length})
          </div>
          {contextMediaList.length > 0 ? (
            <div className="context-picker-grid">
              {contextMediaList.map((m) => {
                const isSelected = selectedContextIds.includes(m.id);
                return (
                  <div
                    key={m.id}
                    data-testid={`context-select-${m.id}`}
                    className={`context-thumb-selectable ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedContextIds((prev) =>
                        isSelected ? prev.filter((id) => id !== m.id) : [...prev, m.id],
                      );
                    }}
                  >
                    <img src={mediaUrl(m)} alt="Context" />
                    {isSelected && <div className="context-check">✓</div>}
                  </div>
                );
              })}
            </div>
          ) : (
            <small className="muted" style={{ display: 'block', fontSize: 12 }}>
              Chưa có ảnh bối cảnh (có thể thêm tại tab Hồ sơ).
            </small>
          )}
        </div>

        {/* 3. Prompt Input */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)', marginBottom: 6 }}>
            3. Lời thoại & Kịch bản tiếng Việt ({duration} giây)
          </div>
          <textarea
            className="prompt-textarea"
            placeholder="Nhập lời thoại hoặc nội dung bạn muốn nhân vật nói trong video (VD: Chia sẻ 3 bí quyết làm bánh mì giòn tan tại nhà...)"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        {/* Cost Estimation */}
        <div className="cost-card" style={{ marginBottom: 16 }}>
          <div>
            <div>
              Thời lượng: <strong>{duration} giây</strong> (360p)
            </div>
          </div>
        </div>

        {!canAfford && (
          <div style={{ color: '#c92a2a', fontSize: 13, marginBottom: 12 }}>
            ⚠️ Số dư không đủ (${costUsd.toFixed(2)}). Vui lòng nạp thêm credit để tạo video.
          </div>
        )}

        <button
          type="button"
          className="primary"
          disabled={!canGenerate || starting}
          onClick={() => setShowConfirm(true)}
        >
          {starting ? 'Đang gửi...' : `Tạo video ngay ($${costUsd.toFixed(2)})`}
        </button>
      </section>

      {/* Confirm Modal */}
      {showConfirm && (
        <div className="modal-overlay">
          <div className="confirm-dialog">
            <h3>Xác nhận tạo video AI</h3>
            <p className="muted" style={{ fontSize: 13, margin: 0 }}>
              Hệ thống sẽ giữ <strong>${costUsd.toFixed(2)}</strong> ({costMicro.toLocaleString()} credits) để tạo 1
              video ngắn {duration} giây. Nếu thất bại, toàn bộ credit sẽ được hoàn lại tự động.
            </p>

            <div className="confirm-details">
              <div className="confirm-row">
                <span>Thời lượng:</span>
                <strong>{duration} giây (360p)</strong>
              </div>
              <div className="confirm-row">
                <span>Ảnh bối cảnh kèm theo:</span>
                <strong>{selectedContextIds.length} ảnh</strong>
              </div>
              <div className="confirm-row">
                <span>Chi phí:</span>
                <strong>${costUsd.toFixed(2)}</strong>
              </div>
              <div className="confirm-row">
                <span>Số dư hiện tại:</span>
                <span>${(balance / 1000000).toFixed(2)}</span>
              </div>
              <div className="confirm-row" style={{ borderTop: '1px solid var(--line)', paddingTop: 4 }}>
                <span>Số dư sau khi trừ:</span>
                <strong>${((balance - costMicro) / 1000000).toFixed(2)}</strong>
              </div>
            </div>

            <div className="dialog-actions">
              <button type="button" className="btn-secondary" onClick={() => setShowConfirm(false)} disabled={starting}>
                Huỷ
              </button>
              <button type="button" className="btn-confirm" onClick={handleStartGeneration} disabled={starting}>
                {starting ? 'Đang xử lý...' : 'Xác nhận tạo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Video Generation History */}
      <section className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Lịch sử tạo video ({jobs.length})</h2>
          {jobs.length > 0 && (
            <button type="button" className="media-action-btn" onClick={toggleAllExpanded}>
              {hasAnyExpanded ? 'Thu gọn tất cả' : 'Mở rộng tất cả'}
            </button>
          )}
        </div>

        {jobs.length === 0 ? (
          <p className="muted" style={{ textAlign: 'center', padding: '16px 0', fontSize: 13 }}>
            Chưa có video nào. Nhập kịch bản ở trên để tạo video đầu tiên!
          </p>
        ) : (
          <div className="video-history-list">
            {jobs.map((j) => {
              const expanded = isJobExpanded(j);
              return (
                <div key={j.id} className={`video-card ${expanded ? 'expanded' : 'collapsed'}`}>
                  <div
                    className="video-card-head"
                    onClick={() => toggleJobExpanded(j.id, expanded)}
                    title={expanded ? 'Nhấn để thu gọn' : 'Nhấn để mở rộng chi tiết'}
                  >
                    <div className="video-card-head-left">
                      <span className={`status-chip ${j.status}`}>
                        {j.status === 'pending'
                          ? 'Đang chờ hàng đợi'
                          : j.status === 'running'
                            ? 'Đang xử lý...'
                            : j.status === 'completed'
                              ? 'Hoàn tất'
                              : j.status === 'failed'
                                ? 'Thất bại'
                                : 'Đã huỷ'}
                      </span>
                      <span className="duration-tag">{ratePerSecMicro > 0 ? Math.round(j.cost / ratePerSecMicro) : duration}s</span>
                      {!expanded && <span className="video-card-preview-prompt">{j.prompt}</span>}
                    </div>

                    <div className="video-card-head-right">
                      <span className="video-card-time">
                        {j.created_at
                          ? new Date(j.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
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
                          Huỷ & Hoàn tiền
                        </button>
                      )}

                      {j.status === 'completed' && j.video_path && (
                        <a
                          href={videoDownloadUrl(j)}
                          download={`video-${j.id}.mp4`}
                          className="media-action-btn download-btn"
                          title="Tải video về máy"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Tải về
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
                          Xoá
                        </button>
                      )}

                      <span className="video-collapse-chevron" aria-label={expanded ? 'Thu gọn' : 'Mở rộng'}>
                        {expanded ? '▲' : '▼'}
                      </span>
                    </div>
                  </div>

                  <div className="video-card-body" style={{ display: expanded ? 'flex' : 'none' }}>
                    <div className="video-prompt-box">
                      <div className="video-prompt-label">
                        <strong>Kịch bản & Lời thoại chi tiết:</strong>
                        <button
                          type="button"
                          className="copy-prompt-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard?.writeText(j.prompt);
                            setNotice({ type: 'success', text: 'Đã sao chép kịch bản!' });
                          }}
                        >
                          Sao chép
                        </button>
                      </div>
                      <div className="video-prompt-text">{j.prompt}</div>
                    </div>

                    {j.status === 'completed' && j.video_path && (
                      <div className="video-player-box">
                        <video controls playsInline className="video-player" src={videoFileUrl(j)} />
                        <div className="video-player-toolbar">
                          <a
                            href={videoDownloadUrl(j)}
                            download={`video-${j.id}.mp4`}
                            className="download-video-action"
                            title="Tải video định dạng .mp4 về máy"
                          >
                            ⬇ Tải video về máy (.mp4)
                          </a>
                        </div>
                      </div>
                    )}

                    {j.status === 'failed' && (
                      <div className="video-error-text">
                        Lỗi: {j.error || 'Có lỗi xảy ra khi tạo video.'}
                        <div style={{ color: '#2b8a3e', marginTop: 4 }}>
                          ✓ Đã hoàn lại {j.cost_usd ? `${j.cost_usd} USD` : `${(j.cost / 1000000).toFixed(2)} USD`} ({j.cost?.toLocaleString()} credits) vào số dư của bạn.
                        </div>
                      </div>
                    )}

                    <div className="video-card-footer">
                      <span>Mã job: {j.id}</span>
                      <span>{j.created_at ? new Date(j.created_at).toLocaleString('vi-VN') : ''}</span>
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
