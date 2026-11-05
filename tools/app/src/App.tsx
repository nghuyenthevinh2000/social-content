import { useEffect, useMemo, useRef, useState } from "react";
import { apiBase, apiFetch, IS_TAURI, openExternal } from "./api";
import "./App.css";

type Agent = {
  id: string;
  label: string;
  available: boolean;
  note?: string;
  login_hint?: string;
};

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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agent, setAgent] = useState("agy");
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
  const [agentsTick, setAgentsTick] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

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
    const check = async (attempt = 0) => {
      try {
        const res = await apiFetch("/api/health");
        const data = (await res.json()) as { desktop?: boolean };
        if (!cancelled) setDesktop(Boolean(data.desktop) && !IS_TAURI);
      } catch {
        if (!cancelled && attempt < 120) {
          timer = window.setTimeout(() => check(attempt + 1), 500);
        }
      }
    };
    check();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    const load = async (attempt = 0) => {
      try {
        const res = await apiFetch("/api/agents");
        const data = (await res.json()) as { agents: Agent[] };
        if (cancelled) return;
        setAgents(data.agents || []);
        const preferred =
          data.agents?.find((item) => item.id === "agy" && item.available) ||
          data.agents?.find((item) => item.available);
        if (preferred) setAgent(preferred.id);
      } catch {
        if (!cancelled && attempt < 120) {
          timer = window.setTimeout(() => load(attempt + 1), 500);
        } else if (!cancelled) {
          setError(
            "Không kết nối được backend. Nếu dùng bản app, hãy mở lại “AIBrand”; nếu chạy dev, chạy python3 tools/app/server.py.",
          );
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [agentsTick]);

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
        agent,
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

  return (
    <div className="page">
      <header className="hero">
        <div className="brand">
          <span className="brand-mark">AB</span>
          <span>AIBrand</span>
        </div>
        <h1>Spy đối thủ → 3 chủ đề viral mỗi sheet</h1>
        <p className="lede">
          Upload file Excel, hệ thống chạy toàn bộ pipeline 48h cho từng sheet rồi để harness
          agent bạn chọn (qua ACP) chốt 3 chủ đề đáng làm nhất.
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

          <h2>2. Harness agent (ACP)</h2>
          <div className="agents">
            {agents.map((item) => (
              <label
                key={item.id}
                className={`agent-card ${agent === item.id ? "selected" : ""} ${item.available ? "" : "disabled"}`}
              >
                <input
                  type="radio"
                  name="agent"
                  value={item.id}
                  checked={agent === item.id}
                  disabled={!item.available}
                  onChange={() => setAgent(item.id)}
                />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.available ? item.note : "Chưa cài trên máy"}</small>
                </span>
                <span className={`dot ${item.available ? "on" : ""}`} />
              </label>
            ))}
          </div>
          <div className="agent-actions">
            <button className="ghost" type="button" onClick={() => setAgentsTick((value) => value + 1)}>
              Làm mới danh sách
            </button>
            <span className="muted">Cài harness xong thì bấm làm mới.</span>
          </div>
          <p className="hint">
            Agent chỉ nhận dữ liệu reel và trả JSON 3 chủ đề. Nếu harness chưa đăng nhập, app tự
            dùng gợi ý dự phòng từ số liệu.
          </p>

          <h2>3. Tuỳ chọn chạy</h2>
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
