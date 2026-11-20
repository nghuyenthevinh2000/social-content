export type JobKind = 'profile' | 'reel' | 'keyword';

export type KeywordQuery = {
  kind: 'original' | 'abbreviation' | 'vi' | string;
  text: string;
};

export type DiscoveredCreator = {
  name: string;
  handle: string;
  url: string;
  platform: string;
  followers?: number;
  video_count: number;
  top_views: number;
  relevance?: string;
  why_relevant?: string;
};

export type Topic = {
  title: string;
  hook: string;
  angle: string;
  why_viral: string;
  outline: string[];
  format: string;
  source_urls: string[];
  generated_by: string;
  prompt?: string;
  reel_url?: string;
  video_url?: string;
  video_id?: string;
  platform?: string;
  author_url?: string;
  matched_query?: string;
  views?: number;
  velocity_per_hour?: number;
  current_pool?: number;
  pool_name?: string;
  likes?: number;
  comments?: number;
  shares?: number;
  author_handle?: string;
  author_name?: string;
  transcript?: string;
  visual?: string;
};

export type Sheet = {
  name: string;
  slug: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  targets: number;
  target_list?: { name: string; url: string }[];
  reels: number;
  pool_distribution: Record<string, number>;
  source_breakdown?: {
    glasser_api?: string[];
    cache?: string[];
    empty?: string[];
  };
  queries?: KeywordQuery[];
  creators?: DiscoveredCreator[];
  topics: Topic[];
  error: string | null;
  notice?: string | null;
};

export type Job = {
  id: string;
  job_kind?: JobKind;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  filename: string;
  created_at?: string;
  current_sheet: string | null;
  sheets: Sheet[];
  logs: { at: string; sheet: string | null; message: string }[];
};

export type JobSummary = {
  id: string;
  job_kind?: JobKind;
  status: Job['status'];
  filename: string;
  created_at: string;
  finished_at: string | null;
  current_sheet: string | null;
  total_sheets: number;
  completed_sheets: number;
  total_topics: number;
};
