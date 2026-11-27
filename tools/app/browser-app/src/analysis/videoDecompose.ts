export type SpeechSegment = {
  start: number;
  end: number;
  energy: number;
};

export type VideoDecomposeResult = {
  speech_segments: SpeechSegment[];
  cuts: number[];
  speech_duration_sec: number;
  speaking_ratio: number;
};

export type TimedTranscriptSegment = {
  start: number;
  end: number;
  text: string;
};

/**
 * Encode mono Float32 PCM samples (-1..1) as a 16-bit PCM WAV base64 string.
 */
export function encodeMonoWavBase64(samples: Float32Array, sampleRate: number): string {
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, numSamples * 2, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/**
 * Mix an AudioBuffer down to mono Float32Array capped at maxDurationSec.
 */
export function mixToMonoPcm(decoded: AudioBuffer, maxDurationSec = 180): Float32Array {
  const len = Math.min(decoded.length, Math.floor(decoded.sampleRate * maxDurationSec));
  const mono = new Float32Array(Math.max(0, len));
  if (len <= 0) return mono;
  const chCount = Math.max(1, decoded.numberOfChannels);
  for (let ch = 0; ch < chCount; ch++) {
    const chData = decoded.getChannelData(ch);
    for (let i = 0; i < len; i++) mono[i] += chData[i] / chCount;
  }
  return mono;
}

/**
 * Detect speech intervals from mono PCM via adaptive RMS energy VAD.
 */
export function detectSpeechSegments(
  samples: Float32Array,
  sampleRate: number,
  opts: {
    frameSec?: number;
    minMergeGapSec?: number;
    minSegmentSec?: number;
    padSec?: number;
  } = {},
): SpeechSegment[] {
  if (samples.length === 0 || sampleRate <= 0) return [];
  const frameSec = opts.frameSec ?? 0.02;
  const minMergeGap = opts.minMergeGapSec ?? 0.22;
  const minSeg = opts.minSegmentSec ?? 0.12;
  const pad = opts.padSec ?? 0.05;

  const hop = Math.max(1, Math.round(sampleRate * frameSec));
  const rmsList: number[] = [];
  for (let i = 0; i < samples.length; i += hop) {
    const end = Math.min(samples.length, i + hop);
    let sumSq = 0;
    for (let j = i; j < end; j++) sumSq += samples[j] * samples[j];
    rmsList.push(Math.sqrt(sumSq / Math.max(1, end - i)));
  }
  if (rmsList.length === 0) return [];

  const sorted = [...rmsList].sort((a, b) => a - b);
  const p20 = sorted[Math.floor(sorted.length * 0.2)] ?? 0;
  const p90 = sorted[Math.floor(sorted.length * 0.9)] ?? 0;
  if (p90 < 0.008) return [];
  const threshold = Math.max(0.012, Math.min(p90 * 0.35, p20 * 2.5 + 0.008));

  const raw: SpeechSegment[] = [];
  let inSpeech = false;
  let segStart = 0;
  let energyAcc = 0;
  let energyCnt = 0;

  for (let idx = 0; idx < rmsList.length; idx++) {
    const t = idx * frameSec;
    const active = rmsList[idx] >= threshold;
    if (active && !inSpeech) {
      inSpeech = true;
      segStart = t;
      energyAcc = rmsList[idx];
      energyCnt = 1;
    } else if (active && inSpeech) {
      energyAcc += rmsList[idx];
      energyCnt += 1;
    } else if (!active && inSpeech) {
      raw.push({ start: segStart, end: t, energy: energyAcc / energyCnt });
      inSpeech = false;
    }
  }
  const totalDur = samples.length / sampleRate;
  if (inSpeech) {
    raw.push({ start: segStart, end: totalDur, energy: energyAcc / Math.max(1, energyCnt) });
  }

  const merged: SpeechSegment[] = [];
  for (const seg of raw) {
    const prev = merged[merged.length - 1];
    if (prev && seg.start - prev.end <= minMergeGap) {
      const prevDur = prev.end - prev.start;
      const curDur = seg.end - seg.start;
      prev.energy = (prev.energy * prevDur + seg.energy * curDur) / Math.max(0.01, prevDur + curDur);
      prev.end = seg.end;
    } else {
      merged.push({ ...seg });
    }
  }

  return merged
    .filter((s) => s.end - s.start >= minSeg)
    .map((s) => ({
      start: Number(Math.max(0, s.start - pad).toFixed(2)),
      end: Number(Math.min(totalDur, s.end + pad).toFixed(2)),
      energy: Number(s.energy.toFixed(4)),
    }));
}

/**
 * Detect visual shot cuts from sampled RGBA frame buffers via normalized L1 pixel delta.
 */
export function detectVisualCuts(
  frames: Array<{ time: number; data: Uint8ClampedArray }>,
  threshold = 0.28,
): number[] {
  const cuts: number[] = [];
  for (let i = 1; i < frames.length; i++) {
    const a = frames[i - 1].data;
    const b = frames[i].data;
    const len = Math.min(a.length, b.length);
    if (len === 0) continue;
    let diff = 0;
    let count = 0;
    // Sample every 4th pixel (stride 16 bytes) for speed
    for (let p = 0; p + 2 < len; p += 16) {
      diff += Math.abs(a[p] - b[p]) + Math.abs(a[p + 1] - b[p + 1]) + Math.abs(a[p + 2] - b[p + 2]);
      count += 3;
    }
    const normDiff = diff / Math.max(1, count * 255);
    if (normDiff >= threshold) {
      cuts.push(Number(frames[i].time.toFixed(2)));
    }
  }
  return cuts;
}

/**
 * Distribute plain transcript text proportionally across detected speech segments.
 */
export function alignTranscriptToSpeechSegments(
  text: string,
  segments: SpeechSegment[],
): TimedTranscriptSegment[] {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0 || segments.length === 0) return [];
  const durations = segments.map((s) => Math.max(0.05, s.end - s.start));
  const totalSpeech = durations.reduce((acc, d) => acc + d, 0);

  const out: TimedTranscriptSegment[] = [];
  let wordIdx = 0;
  for (let i = 0; i < segments.length && wordIdx < words.length; i++) {
    const remainingSegs = segments.length - i;
    const remainingWords = words.length - wordIdx;
    const quota =
      i === segments.length - 1
        ? remainingWords
        : Math.max(1, Math.min(remainingWords - (remainingSegs - 1), Math.round((durations[i] / totalSpeech) * words.length)));
    const slice = words.slice(wordIdx, wordIdx + quota);
    wordIdx += quota;
    out.push({
      start: segments[i].start,
      end: segments[i].end,
      text: slice.join(' '),
    });
  }
  return out;
}

export function summarizeDecomposition(
  durationSec: number,
  speech_segments: SpeechSegment[],
  cuts: number[],
): VideoDecomposeResult {
  const speech_duration_sec = Number(
    speech_segments.reduce((acc, s) => acc + Math.max(0, s.end - s.start), 0).toFixed(2),
  );
  const speaking_ratio =
    durationSec > 0 ? Number(Math.min(1, speech_duration_sec / durationSec).toFixed(2)) : 0;
  return {
    speech_segments,
    cuts,
    speech_duration_sec,
    speaking_ratio,
  };
}
