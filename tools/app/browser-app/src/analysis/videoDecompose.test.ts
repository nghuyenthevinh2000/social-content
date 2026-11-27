import { describe, expect, test } from 'vitest';

import {
  alignTranscriptToSpeechSegments,
  detectSpeechSegments,
  detectVisualCuts,
  encodeMonoWavBase64,
  summarizeDecomposition,
} from './videoDecompose';

describe('videoDecompose', () => {
  test('detectSpeechSegments finds speech intervals and merges short gaps', () => {
    const sr = 16000;
    const total = sr * 4; // 4 seconds
    const pcm = new Float32Array(total);
    // Speech burst 1: 0.5s .. 1.5s
    for (let i = Math.floor(0.5 * sr); i < Math.floor(1.5 * sr); i++) {
      pcm[i] = 0.25 * Math.sin((2 * Math.PI * 220 * i) / sr);
    }
    // Speech burst 2: 2.3s .. 3.4s
    for (let i = Math.floor(2.3 * sr); i < Math.floor(3.4 * sr); i++) {
      pcm[i] = 0.25 * Math.sin((2 * Math.PI * 260 * i) / sr);
    }

    const segs = detectSpeechSegments(pcm, sr);
    expect(segs).toHaveLength(2);
    expect(segs[0].start).toBeGreaterThanOrEqual(0.4);
    expect(segs[0].end).toBeLessThanOrEqual(1.65);
    expect(segs[1].start).toBeGreaterThanOrEqual(2.2);
    expect(segs[1].end).toBeLessThanOrEqual(3.55);

    const summary = summarizeDecomposition(4.0, segs, [1.9]);
    expect(summary.speech_duration_sec).toBeGreaterThan(1.8);
    expect(summary.speaking_ratio).toBeGreaterThan(0.45);
    expect(summary.cuts).toEqual([1.9]);
  });

  test('detectVisualCuts detects sharp scene changes', () => {
    const dark = new Uint8ClampedArray(64).fill(10);
    const dark2 = new Uint8ClampedArray(64).fill(14);
    const bright = new Uint8ClampedArray(64).fill(240);
    const cuts = detectVisualCuts([
      { time: 0.5, data: dark },
      { time: 1.5, data: dark2 },
      { time: 2.5, data: bright },
    ]);
    expect(cuts).toEqual([2.5]);
  });

  test('alignTranscriptToSpeechSegments distributes words proportionally', () => {
    const aligned = alignTranscriptToSpeechSegments('Một hai ba bốn năm sáu', [
      { start: 0.5, end: 1.5, energy: 0.2 },
      { start: 2.0, end: 4.0, energy: 0.2 },
    ]);
    expect(aligned).toHaveLength(2);
    expect(aligned[0].text).toBe('Một hai');
    expect(aligned[1].text).toBe('ba bốn năm sáu');
  });

  test('encodeMonoWavBase64 produces valid RIFF/WAVE header', () => {
    const b64 = encodeMonoWavBase64(new Float32Array(160), 16000);
    const raw = atob(b64);
    expect(raw.slice(0, 4)).toBe('RIFF');
    expect(raw.slice(8, 12)).toBe('WAVE');
    expect(raw.length).toBe(44 + 160 * 2);
  });
});
