import type { Job, Topic } from './types';

export const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export const STATUS_LABEL: Record<Job['status'], string> = {
  queued: 'Đang chờ',
  running: 'Đang chạy',
  completed: 'Hoàn tất',
  failed: 'Có lỗi',
  cancelled: 'Đã dừng',
};

export const formatNumber = (value: number): string => new Intl.NumberFormat('vi-VN').format(value);

export const formatCompact = (val?: number | null): string => {
  if (!val && val !== 0) return '0';
  if (val >= 1_000_000) return (val / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (val >= 1_000) return (val / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(val);
};

export const reelLink = (url: string): string => {
  if (!url) return '';
  const trimmed = url.trim();
  if (trimmed.includes('/reel/') || trimmed.includes('/videos/') || trimmed.includes('/watch/')) {
    return trimmed;
  }
  if (trimmed.includes('facebook.com') && !trimmed.includes('/reels')) {
    return trimmed.replace(/\/+$/, '') + '/reels/';
  }
  return trimmed;
};

export const getTopicReelUrl = (topic: Topic): string => {
  if (topic.reel_url) return reelLink(topic.reel_url);
  if (topic.source_urls && topic.source_urls.length > 0) return reelLink(topic.source_urls[0]);
  if (topic.video_id) return `https://www.facebook.com/reel/${topic.video_id}`;
  return '';
};

export function formatTopicForAI(topic: Topic, sheetName?: string): string {
  // Use the AI-generated director prompt directly from backend
  if (topic.prompt && topic.prompt.trim()) {
    return topic.prompt.trim();
  }
  // Minimal fallback for legacy topics without generated prompt
  const lines: string[] = [];
  lines.push(`### Chủ đề: ${topic.title}`);
  if (sheetName) lines.push(`- **Nhóm chủ đề**: ${sheetName}`);
  if (topic.format) lines.push(`- **Định dạng**: ${topic.format}`);
  if (topic.hook) lines.push(`- **Hook**: "${topic.hook}"`);
  if (topic.angle) lines.push(`- **Góc tiếp cận**: ${topic.angle}`);
  if (topic.outline && topic.outline.length > 0) {
    lines.push(`- **Dàn ý triển khai**:`);
    topic.outline.forEach((step, idx) => lines.push(`  ${idx + 1}. ${step}`));
  }
  return lines.join('\n');
}

export function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-999999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand('copy');
    textarea.remove();
    return Promise.resolve();
  } catch (err) {
    textarea.remove();
    return Promise.reject(err);
  }
}

export const cleanTopicTitle = (title?: string | null): string => {
  if (!title) return 'Phân tích';
  const stripped = String(title).replace(/\.(xlsx|json)$/i, '');
  if (stripped === 'all_topics' || stripped === 'tong-hop') return 'Tất cả chủ đề';
  return stripped;
};

export const formatTime = (iso?: string): string => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    }).format(d);
  } catch {
    return iso;
  }
};
