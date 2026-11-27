import {
  detectSpeechSegments,
  detectVisualCuts,
  encodeMonoWavBase64,
  mixToMonoPcm,
  type SpeechSegment,
  summarizeDecomposition,
  type VideoDecomposeResult,
} from './analysis/videoDecompose';

export type ClientVideoProbe = {
  width: number;
  height: number;
  duration: number;
  fps: number;
  has_audio: boolean;
  speech_segments?: SpeechSegment[];
  cuts?: number[];
};

export type EditEffect = {
  type: string;
  [key: string]: any;
};

export type EditPlan = {
  width?: number;
  height?: number;
  fps?: number;
  loudnorm?: boolean;
  effects: EditEffect[];
};

export async function canRenderVideoOnClient(): Promise<boolean> {
  if (typeof VideoDecoder !== 'function' || typeof VideoEncoder !== 'function') {
    return false;
  }
  try {
    const res = await VideoEncoder.isConfigSupported({
      codec: 'avc1.42001f',
      width: 720,
      height: 1280,
      bitrate: 3_000_000,
      framerate: 24,
    });
    return Boolean(res?.supported);
  } catch {
    return false;
  }
}

export async function extractMonoAudioAndDecompose(
  file: File,
  maxDurationSec = 180,
): Promise<{ audio_b64: string | null; speech_segments: SpeechSegment[] }> {
  const AudioCtx =
    typeof AudioContext !== 'undefined'
      ? AudioContext
      : (globalThis as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return { audio_b64: null, speech_segments: [] };
  const ctx = new AudioCtx({ sampleRate: 16000 });
  try {
    const arr = await file.arrayBuffer();
    const decoded = await ctx.decodeAudioData(arr);
    const mono = mixToMonoPcm(decoded, maxDurationSec);
    if (mono.length === 0) return { audio_b64: null, speech_segments: [] };
    return {
      audio_b64: encodeMonoWavBase64(mono, decoded.sampleRate),
      speech_segments: detectSpeechSegments(mono, decoded.sampleRate),
    };
  } catch {
    return { audio_b64: null, speech_segments: [] };
  } finally {
    await ctx.close().catch(() => {});
  }
}

export async function probeAndExtractKeyframes(file: File): Promise<{
  probe: ClientVideoProbe;
  keyframes_b64: string[];
  audio_b64: string | null;
  decomposition: VideoDecomposeResult;
}> {
  const url = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.muted = true;
  video.playsInline = true;
  video.preload = 'auto';
  video.src = url;

  try {
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error('Failed to load video metadata'));
    });

    const width = video.videoWidth || 720;
    const height = video.videoHeight || 1280;
    const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 1;

    const maxW = 540;
    const scale = width > maxW ? maxW / width : 1;
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(2, Math.round(width * scale));
    canvas.height = Math.max(2, Math.round(height * scale));
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas 2D unavailable');

    const keyframes_b64: string[] = [];
    const sampledFrames: Array<{ time: number; data: Uint8ClampedArray }> = [];
    for (const frac of [0.15, 0.5, 0.85]) {
      const target = Math.max(0, Math.min(duration - 0.05, duration * frac));
      await new Promise<void>((resolve) => {
        const onSeeked = () => {
          video.removeEventListener('seeked', onSeeked);
          resolve();
        };
        video.addEventListener('seeked', onSeeked);
        video.currentTime = target;
      });
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      sampledFrames.push({
        time: target,
        data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
      });
      const dataUrl = canvas.toDataURL('image/jpeg', 0.72);
      const b64 = dataUrl.split(',')[1];
      if (b64) keyframes_b64.push(b64);
    }

    const { audio_b64, speech_segments } = await extractMonoAudioAndDecompose(file);
    const cuts = detectVisualCuts(sampledFrames);
    const decomposition = summarizeDecomposition(duration, speech_segments, cuts);
    return {
      probe: {
        width,
        height,
        duration: Number(duration.toFixed(2)),
        fps: 30,
        has_audio: audio_b64 !== null,
        speech_segments,
        cuts,
      },
      keyframes_b64,
      audio_b64,
      decomposition,
    };
  } finally {
    video.src = '';
    URL.revokeObjectURL(url);
  }
}

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}

function hexToRgba(hex: string, alpha255 = 255): string {
  const clean = (hex || '#FFFFFF').replace('#', '');
  const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
  const num = parseInt(full.slice(0, 6), 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  const a = Math.max(0, Math.min(1, alpha255 / 255));
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

export function drawEffectsOnCanvas(
  ctx: CanvasRenderingContext2D,
  source: CanvasImageSource,
  srcW: number,
  srcH: number,
  outW: number,
  outH: number,
  timeSec: number,
  effects: EditEffect[],
): void {
  ctx.save();
  ctx.clearRect(0, 0, outW, outH);

  let zoomScale = 1;
  let yFocus = 0.5;
  let filterStr = 'none';

  for (const eff of effects) {
    if (eff.type === 'color_grade') {
      const c = Number(eff.contrast ?? 1);
      const s = Number(eff.saturation ?? 1);
      const b = 1 + Number(eff.brightness ?? 0);
      filterStr = `contrast(${c}) saturate(${s}) brightness(${b})`;
    } else if (eff.type === 'punch_zoom') {
      const windows: any[] = Array.isArray(eff.windows)
        ? eff.windows
        : eff.start !== undefined && eff.end !== undefined
          ? [eff]
          : [];
      for (const w of windows) {
        if (timeSec >= Number(w.start) && timeSec <= Number(w.end)) {
          zoomScale = Math.max(zoomScale, Number(w.scale ?? 1.05));
          if (w.y_focus !== undefined) yFocus = Number(w.y_focus);
        }
      }
    }
  }

  ctx.filter = filterStr;
  const baseScale = Math.max(outW / Math.max(1, srcW), outH / Math.max(1, srcH)) * zoomScale;
  const drawW = srcW * baseScale;
  const drawH = srcH * baseScale;
  const dx = (outW - drawW) / 2;
  const dy = (outH - drawH) * yFocus;
  ctx.drawImage(source, dx, dy, drawW, drawH);
  ctx.filter = 'none';

  for (const eff of effects) {
    if (eff.type === 'transition') {
      const dur = Math.max(0.01, Number(eff.duration ?? 0.2));
      const start = Number(eff.start ?? eff.time ?? 0);
      if (timeSec >= start && timeSec <= start + dur) {
        const t = (timeSec - start) / dur;
        let alpha = 0;
        if (eff.kind === 'fade_in') alpha = 1 - t;
        else if (eff.kind === 'fade_out') alpha = t;
        else if (eff.kind === 'flash') alpha = Math.sin(t * Math.PI) * 0.85;
        if (alpha > 0) {
          ctx.fillStyle = eff.color === 'white' ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha})`;
          ctx.fillRect(0, 0, outW, outH);
        }
      }
    } else if (eff.type === 'text_box' || eff.type === 'card' || eff.type === 'hook_card') {
      const start = Number(eff.start ?? 0);
      const end = Number(eff.end ?? 9999);
      if (timeSec < start || timeSec > end) continue;
      const fadeIn = Number(eff.fade_in ?? 0.1);
      const fadeOut = Number(eff.fade_out ?? 0.1);
      let alpha = 1;
      if (fadeIn > 0 && timeSec - start < fadeIn) alpha = (timeSec - start) / fadeIn;
      else if (fadeOut > 0 && end - timeSec < fadeOut) alpha = (end - timeSec) / fadeOut;

      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      const boxW = Number(eff.width ?? 320);
      const boxH = Number(eff.height ?? 140);
      const x = Number(eff.x ?? (outW - boxW) / 2);
      const y = Number(eff.y ?? 140);
      const radius = Number(eff.radius ?? 16);
      const pad = Number(eff.pad ?? 14);
      const fontSize = Number(eff.font_size ?? 28);

      if (eff.shadow) {
        ctx.shadowColor = 'rgba(0,0,0,0.28)';
        ctx.shadowBlur = 14;
        ctx.shadowOffsetY = 4;
      }
      ctx.fillStyle = hexToRgba(eff.bg_color || '#FFFFFF', Number(eff.bg_alpha ?? 245));
      drawRoundedRect(ctx, x, y, boxW, boxH, radius);
      ctx.fill();
      ctx.shadowColor = 'transparent';

      if (eff.accent_bar_color) {
        ctx.fillStyle = eff.accent_bar_color;
        drawRoundedRect(ctx, x, y, 6, boxH, 3);
        ctx.fill();
      }

      ctx.fillStyle = eff.text_color || '#1C2026';
      ctx.textBaseline = 'top';
      let curY = y + pad;

      if (eff.variant === 'table' && Array.isArray(eff.rows)) {
        const headers: string[] = Array.isArray(eff.headers) ? eff.headers : [];
        const allRows: string[][] = headers.length ? [headers, ...eff.rows] : eff.rows;
        const colCount = Math.max(1, allRows[0]?.length || 2);
        const colW = (boxW - pad * 2) / colCount;
        const rowH = Math.max(22, Math.floor((boxH - pad * 2) / Math.max(1, allRows.length)));
        const tblFont = Math.min(fontSize, 18);
        ctx.textAlign = 'left';
        allRows.forEach((row, rIdx) => {
          const isHeader = headers.length > 0 && rIdx === 0;
          ctx.font = `${isHeader ? 800 : 600} ${tblFont}px system-ui, -apple-system, "Segoe UI", sans-serif`;
          if (isHeader) {
            ctx.fillStyle = 'rgba(122, 0, 245, 0.10)';
            ctx.fillRect(x + pad, curY, boxW - pad * 2, rowH - 2);
            ctx.fillStyle = '#7A00F5';
          } else {
            ctx.fillStyle = eff.text_color || '#1C2026';
          }
          for (let cIdx = 0; cIdx < colCount; cIdx++) {
            ctx.fillText(String(row[cIdx] ?? ''), x + pad + cIdx * colW + 4, curY + 3, colW - 8);
          }
          curY += rowH;
        });
      } else {
        if (eff.tag) {
          ctx.font = `700 14px system-ui, -apple-system, "Segoe UI", sans-serif`;
          ctx.textAlign = 'left';
          ctx.fillStyle = '#7A00F5';
          ctx.fillText(String(eff.tag), x + pad, curY, boxW - pad * 2);
          curY += 20;
        }
        ctx.fillStyle = eff.text_color || '#1C2026';
        ctx.font = `700 ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
        ctx.textAlign = eff.align === 'left' ? 'left' : eff.align === 'right' ? 'right' : 'center';
        const textX = eff.align === 'left' ? x + pad : eff.align === 'right' ? x + boxW - pad : x + boxW / 2;

        const rawLines: any[] = Array.isArray(eff.lines)
          ? eff.lines
          : [eff.title, ...(Array.isArray(eff.body) ? eff.body : [])].filter(Boolean);
        const lineGap = Number(eff.line_gap ?? 8);
        for (const item of rawLines) {
          const lineText = typeof item === 'object' && item !== null ? String(item.text ?? '') : String(item);
          const isHighlight = typeof item === 'object' && item !== null && Boolean(item.highlight);
          if (isHighlight) {
            ctx.fillStyle = 'rgba(255, 224, 102, 0.35)';
            ctx.fillRect(x + pad, curY - 2, boxW - pad * 2, fontSize + 4);
            ctx.fillStyle = eff.text_color || '#1C2026';
          }
          ctx.fillText(lineText, textX, curY, boxW - pad * 2);
          curY += fontSize + lineGap;
        }
      }
      ctx.restore();
    } else if (eff.type === 'subtitles' && Array.isArray(eff.items)) {
      const active = eff.items.find(
        (it: any) => timeSec >= Number(it.start) && timeSec <= Number(it.end),
      );
      if (!active?.text) continue;
      const style = eff.style || {};
      const fontSize = Number(eff.font_size ?? style.font_size ?? 44);
      const marginV = Number(eff.margin_v ?? style.margin_v ?? 180);
      const uppercase = eff.uppercase ?? style.uppercase ?? false;
      const outlineColor = eff.outline_color || style.outline_color || '#000000';
      const fillColor = eff.color || style.color || '#FFFFFF';
      const text = uppercase ? String(active.text).toUpperCase() : String(active.text);

      ctx.save();
      ctx.font = `800 ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.lineJoin = 'round';
      ctx.lineWidth = Number(eff.outline_width ?? 8);
      ctx.strokeStyle = outlineColor;
      ctx.strokeText(text, outW / 2, outH - marginV, outW - 80);
      ctx.fillStyle = fillColor;
      ctx.fillText(text, outW / 2, outH - marginV, outW - 80);
      ctx.restore();
    }
  }

  ctx.restore();
}

type SfxEvent = { time: number; sound: string; volume: number };

function collectSfxEvents(effects: EditEffect[]): SfxEvent[] {
  const events: SfxEvent[] = [];
  for (const eff of effects) {
    if (eff.type !== 'sfx') continue;
    if (Array.isArray(eff.events)) {
      for (const ev of eff.events) {
        if (ev && ev.time !== undefined) {
          events.push({
            time: Number(ev.time),
            sound: String(ev.sound || 'pop').toLowerCase(),
            volume: Number(ev.volume ?? 0.22),
          });
        }
      }
    } else if (eff.time !== undefined) {
      events.push({
        time: Number(eff.time),
        sound: String(eff.sound || 'pop').toLowerCase(),
        volume: Number(eff.volume ?? 0.22),
      });
    }
  }
  return events;
}

function synthSfxSample(sound: string, relSec: number): number {
  if (relSec < 0) return 0;
  if (sound === 'ding') {
    if (relSec > 0.35) return 0;
    const env = Math.exp(-relSec * 12);
    return Math.sin(2 * Math.PI * 1046.5 * relSec) * env * 0.7 + Math.sin(2 * Math.PI * 1568 * relSec) * env * 0.3;
  }
  if (sound === 'whoosh') {
    if (relSec > 0.25) return 0;
    const env = Math.sin((relSec / 0.25) * Math.PI);
    const freq = 180 + 420 * (relSec / 0.25);
    return Math.sin(2 * Math.PI * freq * relSec) * env * 0.5;
  }
  // default: pop
  if (relSec > 0.12) return 0;
  const env = Math.exp(-relSec * 32);
  const freq = 420 - 220 * (relSec / 0.12);
  return Math.sin(2 * Math.PI * freq * relSec) * env;
}

export async function renderVideoEditPlan(
  sourceFile: File,
  plan: EditPlan,
  onProgress?: (pct: number) => void,
): Promise<Blob> {
  const {
    Input,
    ALL_FORMATS,
    BlobSource,
    Output,
    Mp4OutputFormat,
    BufferTarget,
    Conversion,
    AudioSample,
  } = await import('mediabunny');

  const outW = plan.width || 720;
  const outH = plan.height || 1280;
  const fps = plan.fps || 24;
  const effects = Array.isArray(plan.effects) ? plan.effects : [];
  const sfxEvents = collectSfxEvents(effects);

  const canvas = document.createElement('canvas');
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas 2D context unavailable');

  let wakeLock: { release: () => Promise<void> } | null = null;
  try {
    const nav = navigator as Navigator & {
      wakeLock?: { request: (type: 'screen') => Promise<{ release: () => Promise<void> }> };
    };
    wakeLock = (await nav.wakeLock?.request('screen')) ?? null;
  } catch {
    wakeLock = null;
  }

  const input = new Input({
    formats: ALL_FORMATS,
    source: new BlobSource(sourceFile),
  });
  const target = new BufferTarget();
  const output = new Output({
    format: new Mp4OutputFormat(),
    target,
  });

  try {
    const conversion = await Conversion.init({
      input,
      output,
      video: {
        frameRate: fps,
        codec: 'avc',
        forceTranscode: true,
        processedWidth: outW,
        processedHeight: outH,
        process: (sample) => {
          const vf = sample.toVideoFrame();
          try {
            drawEffectsOnCanvas(
              ctx,
              vf,
              vf.displayWidth,
              vf.displayHeight,
              outW,
              outH,
              sample.timestamp,
              effects,
            );
          } finally {
            vf.close();
          }
          return canvas;
        },
      },
      ...(sfxEvents.length > 0
        ? {
            audio: {
              forceTranscode: true,
              process: (sample) => {
                const startSec = sample.timestamp;
                const endSec = startSec + sample.duration;
                const active = sfxEvents.filter((ev) => endSec >= ev.time && startSec <= ev.time + 0.4);
                if (active.length === 0) return sample;
                const buf = sample.toAudioBuffer();
                const sr = buf.sampleRate;
                for (let ch = 0; ch < buf.numberOfChannels; ch++) {
                  const data = buf.getChannelData(ch);
                  for (let i = 0; i < data.length; i++) {
                    const t = startSec + i / sr;
                    let mix = data[i];
                    for (const ev of active) {
                      mix += synthSfxSample(ev.sound, t - ev.time) * ev.volume;
                    }
                    data[i] = Math.max(-1, Math.min(1, mix));
                  }
                }
                return AudioSample.fromAudioBuffer(buf, sample.timestamp);
              },
            },
          }
        : {}),
    });
    if (!conversion.isValid) {
      throw new Error('Client video conversion config is not supported on this device');
    }
    conversion.onProgress = (progress: number) => {
      onProgress?.(Math.min(100, Math.max(0, Math.round(progress * 100))));
    };
    await conversion.execute();
    if (!target.buffer) {
      throw new Error('Empty MP4 output buffer');
    }
    return new Blob([target.buffer], { type: 'video/mp4' });
  } finally {
    await wakeLock?.release().catch(() => {});
  }
}
