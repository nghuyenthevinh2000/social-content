import { useEffect, useMemo, useRef, useState } from "react";
import { apiBase, apiFetch, IS_TAURI, openExternal } from "./api";
import "./App.css";

type Topic = {
  title: string;
  hook: string;
  angle: string;
  why_viral: string;
  outline: string[];
  format: string;
  source_urls: string[];
  generated_by: "agent" | "heuristic" | string;
};

type Sheet = {
  name: string;
  slug: string;
  status: "pending" | "running" | "completed" | "failed";
  targets: number;
  reels: number;
  pool_distribution: Record<string, number>;
  topics: Topic[];
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
};

type LogEntry = { at: string; sheet: string | null; message: string };

type Job = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  filename: string;
  agent: string;
  options: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
  current_sheet: string | null;
  sheets: Sheet[];
  logs: LogEntry[];
};

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

function statusLabel(status: Job["status"]) {
  return {
    queued: "Đang chờ",
    running: "Đang chạy",
    completed: "Hoàn tất",
    failed: "Có lỗi",
    cancelled: "Đã dừng",
  }[status];
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function topicSource(topic: Topic) {
  return topic.source_urls?.[0];
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [maxVideos, setMaxVideos] = useState(5);
  const [media, setMedia] = useState(true);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [desktop, setDesktop] = useState(false);
  const [apiRoot, setApiRoot] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Installer / System Setup state
  const [installerDone, setInstallerDone] = useState(false);
  const [installerStep, setInstallerStep] = useState(1);
  const [installerProgress, setInstallerProgress] = useState(12);
  const [installerStatusText, setInstallerStatusText] = useState("Đang kết nối backend...");
  const [installerError, setInstallerError] = useState<string | null>(null);
  const [installerDetails, setInstallerDetails] = useState({
    backend: false,
    ffmpeg: false,
    transcription: false,
    agent: null as string | null,
  });

  // Error reporting & logs modal
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportLogs, setReportLogs] = useState("");
  const [reportPath, setReportPath] = useState("");
  const [reportSys, setReportSys] = useState<any>({});
  const [userNote, setUserNote] = useState("");
  const [copied, setCopied] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);

  const reportClientLog = (message: string, stack?: string, source = "client") => {
    apiFetch("/api/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, stack, source }),
    }).catch(() => {});
  };

  useEffect(() => {
    const handleError = (e: ErrorEvent) => {
      reportClientLog(e.message, e.error?.stack || `${e.filename}:${e.lineno}`, "window.error");
    };
    const handleRejection = (e: PromiseRejectionEvent) => {
      reportClientLog(String(e.reason?.message || e.reason), e.reason?.stack, "unhandledrejection");
    };
    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);
    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
    };
  }, []);

  const openReportModal = async () => {
    setShowReportModal(true);
    setLoadingLogs(true);
    try {
      const res = await apiFetch("/api/logs");
      if (res.ok) {
        const data = await res.json();
        setReportLogs(data.logs || "");
        setReportPath(data.path || "");
        setReportSys(data);
      }
    } catch {
      // keep whatever was loaded
    } finally {
      setLoadingLogs(false);
    }
  };

  const sendEmailReport = (viaGmail = false) => {
    const recipient = "nghuyenthevinh@gmail.com";
    const subjectText = `[AIBrand Error Report] ${userNote ? userNote.slice(0, 40) : error || "Client Log Report"}`;
    const subject = encodeURIComponent(subjectText);
    const bodyText = [
      "Xin chào Vinh,",
      "",
      "Mô tả sự cố:",
      userNote || error || "Gặp sự cố khi chạy AIBrand.",
      "",
      "----------------------------------------",
      "THÔNG TIN HỆ THỐNG:",
      `App: AIBrand v0.1.0`,
      `Platform: ${reportSys.platform || navigator.userAgent}`,
      `OS: ${reportSys.os || "desktop"}`,
      `File log máy: ${reportPath || "unknown"}`,
      `Thời gian: ${new Date().toISOString()}`,
      "----------------------------------------",
      "NHẬT KÝ LỖI GẦN NHẤT (LOG):",
      reportLogs ? reportLogs.slice(-2500) : "(Chưa có log)",
    ].join("\n");
    const body = encodeURIComponent(bodyText);

    if (viaGmail) {
      const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${recipient}&su=${subject}&body=${body}`;
      openExternal(gmailUrl);
    } else {
      const mailtoUrl = `mailto:${recipient}?subject=${subject}&body=${body}`;
      openExternal(mailtoUrl);
    }
  };

  const copyFullLog = async () => {
    const full = [
      `=== AIBrand Error Report ===`,
      `Date: ${new Date().toISOString()}`,
      `Platform: ${reportSys.platform || navigator.userAgent}`,
      `Path: ${reportPath}`,
      `Note: ${userNote || error || "None"}`,
      `\n=== Logs ===\n`,
      reportLogs,
    ].join("\n");
    await navigator.clipboard.writeText(full);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const revealLogOnDisk = async () => {
    try {
      await apiFetch("/api/logs/reveal", { method: "POST" });
    } catch {
      alert(`Đường dẫn file log: ${reportPath}`);
    }
  };

  useEffect(() => {
    let cancelled = false;
    apiBase().then((base) => {
      if (!cancelled) setApiRoot(base);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    const runSetup = async () => {
      // Step 1: Connect to Core Backend (10 -> 35%)
      setInstallerStep(1);
      setInstallerStatusText("Đang kết nối tới Core Backend & Sidecar...");
      setInstallerProgress(15);

      let healthData: any = null;
      for (let attempt = 0; attempt < 60; attempt++) {
        if (cancelled) return;
        try {
          const res = await apiFetch("/api/health");
          if (res.ok) {
            healthData = await res.json();
            break;
          }
        } catch {
          // Backend is launching
        }
        await new Promise((r) => setTimeout(r, 400));
      }

      if (cancelled) return;
      if (!healthData) {
        setInstallerError(
          "Không thể kết nối tới Backend sau 25 giây. Vui lòng thử lại hoặc mở lại AIBrand.",
        );
        return;
      }

      if (healthData.desktop) setDesktop(Boolean(healthData.desktop) && !IS_TAURI);
      setInstallerDetails((prev) => ({ ...prev, backend: true }));
      setInstallerProgress(35);

      // Step 2: Check Media Tools / FFmpeg (35 -> 60%)
      setInstallerStep(2);
      setInstallerStatusText("Kiểm tra bộ xử lý Media & FFmpeg...");
      await new Promise((r) => setTimeout(r, 350));
      if (cancelled) return;

      const hasFfmpeg = Boolean(healthData.ffmpeg);
      setInstallerDetails((prev) => ({ ...prev, ffmpeg: hasFfmpeg }));
      setInstallerProgress(60);

      // Step 3: Check AI Transcription (60 -> 80%)
      setInstallerStep(3);
      setInstallerStatusText("Kiểm tra động cơ nhận diện giọng nói (Qwen3-ASR / Whisper)...");
      await new Promise((r) => setTimeout(r, 350));
      if (cancelled) return;

      const hasAIspeech = Boolean(
        healthData.transcription?.mlx ||
        healthData.transcription?.transformers ||
        healthData.transcription?.whisper,
      );
      setInstallerDetails((prev) => ({ ...prev, transcription: hasAIspeech }));
      setInstallerProgress(80);

      // Step 4: Harness configured on the backend (80 -> 100%)
      setInstallerStep(4);
      setInstallerStatusText("Kiểm tra AI Agent Harness của backend...");
      setInstallerDetails((prev) => ({ ...prev, agent: healthData.agent ?? null }));

      if (cancelled) return;
      setInstallerStep(5);
      setInstallerProgress(100);
      setInstallerStatusText("Thiết lập hệ thống hoàn tất! Đang vào bảng điều khiển...");

      timer = window.setTimeout(() => {
        if (!cancelled) setInstallerDone(true);
      }, 700);
    };

    runSetup();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
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
        if (TERMINAL.has(data.status)) {
          stopped = true;
        }
      } catch {
        // keep polling; the backend may be restarting
      }
    };
    tick();
    const timer = window.setInterval(() => {
      if (stopped) {
        window.clearInterval(timer);
        return;
      }
      tick();
    }, 1500);
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

  async function start() {
    if (!file) {
      setError("Chọn file Excel trước.");
      return;
    }
    setError(null);
    setStarting(true);
    setJob(null);
    try {
      const params = new URLSearchParams({
        max_videos: String(maxVideos),
        media: media ? "1" : "0",
      });
      const res = await apiFetch(`/api/jobs?${params.toString()}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "X-Filename": encodeURIComponent(file.name),
        },
        body: file,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Không tạo được job");
      setJob(data);
      setJobId(data.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (!jobId) return;
    await apiFetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  }

  async function quit() {
    if (!window.confirm("Thoát AIBrand? Các job đang chạy sẽ dừng.")) return;
    try {
      await apiFetch("/api/shutdown", { method: "POST" });
    } catch {
      // the server may already be gone
    }
    setError("Đã thoát AIBrand. Bạn có thể đóng tab này.");
  }

  if (!installerDone) {
    return (
      <div className="installer-overlay">
        <div className="installer-card">
          <div className="installer-header">
            <div className="brand-mark">AB</div>
            <h1>Thiết lập hệ thống AIBrand</h1>
            <p>Kiểm tra môi trường và các công cụ trên máy trước khi vào bảng điều khiển.</p>
          </div>

          <div className="installer-progress-section">
            <div className="installer-progress-bar-wrap">
              <div
                className="installer-progress-bar-fill"
                style={{ width: `${installerProgress}%` }}
              />
            </div>
            <div className="installer-progress-meta">
              <span>{installerStatusText}</span>
              <span className="installer-progress-pct">{installerProgress}%</span>
            </div>
          </div>

          <ul className="installer-checklist">
            <li className="installer-check-item">
              <div className="installer-check-label">
                <span className={`installer-icon-dot ${installerDetails.backend ? "done" : installerStep === 1 ? "running" : "waiting"}`}>
                  {installerDetails.backend ? "✓" : installerStep === 1 ? "…" : "1"}
                </span>
                <span>Core Backend & Sidecar API</span>
              </div>
              <span className={`installer-check-badge ${installerDetails.backend ? "done" : installerStep === 1 ? "running" : "waiting"}`}>
                {installerDetails.backend ? "Sẵn sàng" : installerStep === 1 ? "Đang kết nối..." : "Chờ"}
              </span>
            </li>

            <li className="installer-check-item">
              <div className="installer-check-label">
                <span className={`installer-icon-dot ${installerDetails.backend ? (installerDetails.ffmpeg ? "done" : "warn") : "waiting"}`}>
                  {installerDetails.backend ? (installerDetails.ffmpeg ? "✓" : "!") : "2"}
                </span>
                <span>Xử lý Media & FFmpeg</span>
              </div>
              <span className={`installer-check-badge ${installerDetails.backend ? (installerDetails.ffmpeg ? "done" : "warn") : "waiting"}`}>
                {installerDetails.backend ? (installerDetails.ffmpeg ? "Sẵn sàng" : "Direct Stream") : "Chờ"}
              </span>
            </li>

            <li className="installer-check-item">
              <div className="installer-check-label">
                <span className={`installer-icon-dot ${installerStep >= 3 ? (installerDetails.transcription ? "done" : "warn") : "waiting"}`}>
                  {installerStep >= 3 ? (installerDetails.transcription ? "✓" : "!") : "3"}
                </span>
                <span>Động cơ AI Speech-to-Text</span>
              </div>
              <span className={`installer-check-badge ${installerStep >= 3 ? (installerDetails.transcription ? "done" : "warn") : "waiting"}`}>
                {installerStep >= 3 ? (installerDetails.transcription ? "MLX / PyTorch" : "Chế độ Text") : "Chờ"}
              </span>
            </li>

            <li className="installer-check-item">
              <div className="installer-check-label">
                <span className={`installer-icon-dot ${installerStep >= 4 ? (installerDetails.agent ? "done" : "warn") : "waiting"}`}>
                  {installerStep >= 4 ? (installerDetails.agent ? "✓" : "ℹ") : "4"}
                </span>
                <span>AI Agent Harness (ACP)</span>
              </div>
              <span className={`installer-check-badge ${installerStep >= 4 ? (installerDetails.agent ? "done" : "warn") : "waiting"}`}>
                {installerStep >= 4 ? (installerDetails.agent ?? "Chưa cấu hình") : "Chờ"}
              </span>
            </li>
          </ul>

          {installerError ? (
            <div className="alert" style={{ marginTop: "12px" }}>
              <div>{installerError}</div>
              <div style={{ display: "flex", gap: "8px", marginTop: "10px" }}>
                <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>
                  Thử lại
                </button>
                <button type="button" className="btn-secondary" onClick={openReportModal}>
                  Xem log lỗi
                </button>
              </div>
            </div>
          ) : (
            <div className="installer-footer">
              {installerProgress === 100 && (
                <button
                  type="button"
                  className="primary"
                  style={{ width: "100%", padding: "12px", fontSize: "14px" }}
                  onClick={() => setInstallerDone(true)}
                >
                  Vào bảng điều khiển →
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="brand">
          <span className="brand-mark">AB</span>
          <span>AIBrand</span>
          <button
            type="button"
            className="system-status-btn"
            onClick={() => setInstallerDone(false)}
            title="Xem lại trạng thái hệ thống và kiểm tra công cụ"
          >
            <span className="system-status-indicator" />
            Hệ thống: Sẵn sàng
          </button>
        </div>
        <h1>Spy đối thủ → 3 chủ đề viral mỗi sheet</h1>
        <p className="lede">
          Upload file Excel, hệ thống chạy toàn bộ pipeline 48h cho từng sheet rồi để harness
          agent (qua ACP) chốt 3 chủ đề đáng làm nhất.
        </p>
      </header>

      <main className="layout">
        <section className="panel setup">
          <h2>1. Nguồn dữ liệu</h2>
          <button
            className="dropzone"
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const dropped = event.dataTransfer.files?.[0];
              if (dropped) setFile(dropped);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xlsm"
              hidden
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <span className="drop-icon">⇪</span>
            <strong>{file ? file.name : "Chọn hoặc kéo file Excel vào đây"}</strong>
            <span className="muted">
              {file ? `${Math.round(file.size / 1024)} KB` : "Định dạng .xlsx / .xlsm · tối đa 25MB"}
            </span>
          </button>

          <h2>2. Tuỳ chọn chạy</h2>
          <div className="options">
            <label>
              <span>Video tối đa / sheet</span>
              <input
                type="number"
                min={0}
                max={500}
                value={maxVideos}
                onChange={(event) => setMaxVideos(Math.max(0, Number(event.target.value)))}
              />
              <small>0 = không giới hạn</small>
            </label>
            <label className="check">
              <input type="checkbox" checked={media} onChange={(event) => setMedia(event.target.checked)} />
              <span>Tải video + transcribe (chậm hơn)</span>
            </label>
          </div>

          <button className="primary" type="button" onClick={start} disabled={starting || running}>
            {starting ? "Đang tạo job..." : running ? "Đang chạy..." : "Chạy phân tích"}
          </button>
          {error && (
            <div className="alert">
              <div>{error}</div>
              <button
                type="button"
                className="alert-link-btn"
                onClick={openReportModal}
              >
                Gửi log lỗi tới nghuyenthevinh@gmail.com ✉
              </button>
            </div>
          )}
        </section>

        <section className="panel results">
          <div className="results-head">
            <div>
              <h2>Kết quả</h2>
              <p className="muted">
                {job
                  ? `${job.filename} · ${progress.done}/${progress.total} sheet · ${statusLabel(job.status)}`
                  : "Chưa có job nào. Kết quả sẽ xuất hiện theo từng sheet."}
              </p>
            </div>
            {job && (
              <div className="head-actions">
                <a
                  className="ghost"
                  href={`${apiRoot}/api/jobs/${job.id}/export`}
                  onClick={(event) => {
                    if (IS_TAURI) {
                      event.preventDefault();
                      void openExternal(`${apiRoot}/api/jobs/${job.id}/export`);
                    }
                  }}
                >
                  Tải JSON
                </a>
                {running && (
                  <button className="ghost danger" type="button" onClick={cancel}>
                    Dừng
                  </button>
                )}
              </div>
            )}
          </div>

          {job && (
            <>
              <div className="progress">
                <div className="bar">
                  <span style={{ width: `${progress.pct}%` }} />
                </div>
                <div className="progress-meta">
                  <span>{progress.pct}%</span>
                  <span>{job.current_sheet ? `Đang xử lý: ${job.current_sheet}` : "Sẵn sàng"}</span>
                </div>
              </div>

              <div className="sheet-list">
                {job.sheets.map((sheet, index) => (
                  <details
                    key={sheet.slug}
                    className={`sheet ${sheet.status}`}
                    open={sheet.status === "running" ? true : undefined}
                  >
                    <summary>
                      <span className="sheet-index">{String(index + 1).padStart(2, "0")}</span>
                      <span className="sheet-title">
                        <strong>{sheet.name}</strong>
                        <small>
                          {sheet.targets} kênh · {formatNumber(sheet.reels)} reel
                          {sheet.error ? " · có lỗi" : ""}
                        </small>
                      </span>
                      <span className={`badge ${sheet.status}`}>{sheet.status}</span>
                    </summary>

                    <div className="sheet-body">
                      {Object.keys(sheet.pool_distribution || {}).length > 0 && (
                        <div className="pools">
                          {Object.entries(sheet.pool_distribution).map(([pool, count]) => (
                            <span key={pool} className="pool">
                              {pool.replace("pool_", "P")} · {count}
                            </span>
                          ))}
                        </div>
                      )}
                      {sheet.error && (
                        <div className="alert slim">
                          <div>{sheet.error}</div>
                          <button
                            type="button"
                            className="alert-link-btn"
                            onClick={openReportModal}
                          >
                            Báo cáo lỗi qua email ✉
                          </button>
                        </div>
                      )}
                      {sheet.status === "pending" && <p className="muted">Đang chờ tới lượt…</p>}
                      {sheet.status === "running" && <p className="muted">Đang crawl, phân pool và hỏi agent…</p>}
                      <div className="topic-grid">
                        {sheet.topics.map((topic, topicIndex) => (
                          <article className="topic" key={`${sheet.slug}-${topicIndex}`}>
                            <div className="topic-top">
                              <span className="topic-num">{topicIndex + 1}</span>
                              <span className={`source-tag ${topic.generated_by}`}>
                                {topic.generated_by === "agent" ? "agent" : "dự phòng"}
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
                              {topicSource(topic) && (
                                <a
                                  href={topicSource(topic)}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={(event) => {
                                    const url = topicSource(topic);
                                    if (IS_TAURI && url) {
                                      event.preventDefault();
                                      void openExternal(url);
                                    }
                                  }}
                                >
                                  Reel gốc ↗
                                </a>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  </details>
                ))}
              </div>

              <div className="logs">
                <button className="ghost" type="button" onClick={() => setShowLogs((value) => !value)}>
                  {showLogs ? "Ẩn log" : `Xem log (${job.logs.length})`}
                </button>
                {showLogs && (
                  <pre>
                    {job.logs
                      .slice(-120)
                      .map((entry) => `${entry.at.slice(11, 19)} ${entry.sheet ? `[${entry.sheet}] ` : ""}${entry.message}`)
                      .join("\n")}
                  </pre>
                )}
              </div>
            </>
          )}
        </section>
      </main>

      <footer>
        <span>
          Pipeline: Glasser 48h → 5 traffic pools → tải video/transcribe → ACP agent → 3 chủ đề.
          Dữ liệu và cache nằm trong{" "}
          <code>{IS_TAURI || desktop ? "~/Library/Application Support/AIBrand/runs" : "local/app-runs/"}</code>.
        </span>
        <div className="footer-actions">
          <button
            className="ghost"
            type="button"
            onClick={openReportModal}
          >
            Báo cáo lỗi (nghuyenthevinh@gmail.com)
          </button>
          {desktop && (
            <button className="ghost" type="button" onClick={quit}>
              Thoát ứng dụng
            </button>
          )}
        </div>
      </footer>

      {showReportModal && (
        <div className="modal-backdrop" onClick={() => setShowReportModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Báo cáo lỗi & Gửi nhật ký (Log)</h3>
              <button
                type="button"
                className="ghost"
                onClick={() => setShowReportModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="modal-info-row">
                <span className="modal-info-badge">Người nhận: <strong>nghuyenthevinh@gmail.com</strong></span>
                <span className="modal-info-badge">HĐH: {reportSys.platform || navigator.userAgent.slice(0, 30)}</span>
                {reportPath && <span className="modal-info-badge">File log: {reportPath}</span>}
              </div>
              <label>
                <span className="muted" style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                  Mô tả lỗi hoặc triệu chứng bạn gặp:
                </span>
                <textarea
                  className="modal-note-input"
                  placeholder="Ví dụ: Gặp lỗi khi xử lý sheet 2, agent không phản hồi..."
                  value={userNote}
                  onChange={(e) => setUserNote(e.target.value)}
                />
              </label>
              <div>
                <span className="muted" style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                  Nhật ký máy khách gần nhất (Log):
                </span>
                <pre className="modal-logs-box">
                  {loadingLogs ? "Đang tải log..." : reportLogs || "(Chưa có dữ liệu log ghi nhận)"}
                </pre>
              </div>
            </div>
            <div className="modal-footer">
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => sendEmailReport(false)}
                >
                  ✉ Gửi qua Email App
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => sendEmailReport(true)}
                >
                  Gửi qua Gmail Web
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={copyFullLog}
                >
                  {copied ? "✓ Đã copy log!" : "📋 Copy Log"}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={revealLogOnDisk}
                >
                  📁 Mở file Log
                </button>
              </div>
              <button
                type="button"
                className="ghost"
                onClick={() => setShowReportModal(false)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
