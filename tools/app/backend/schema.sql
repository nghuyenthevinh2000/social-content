-- AIBrand centralized PostgreSQL schema

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    client_id TEXT,
    user_id TEXT,
    heartbeat DOUBLE PRECISION,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_client ON jobs (status, client_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS job_logs (
    seq BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    at TEXT,
    sheet TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_logs_job_seq ON job_logs (job_id, seq);

CREATE TABLE IF NOT EXISTS video_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    profile_media_id TEXT NOT NULL,
    context_media_ids TEXT,
    cost BIGINT NOT NULL,
    status TEXT NOT NULL,
    blob_key TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_video_jobs_status_created ON video_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS idx_video_jobs_user_status ON video_jobs (user_id, status);

CREATE TABLE IF NOT EXISTS user_credits (
    user_id TEXT PRIMARY KEY,
    balance BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    delta BIGINT NOT NULL,
    reason TEXT NOT NULL,
    job_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_id ON credit_ledger (user_id, id DESC);

CREATE TABLE IF NOT EXISTS user_media (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    blob_key TEXT NOT NULL,
    mime TEXT NOT NULL,
    bytes BIGINT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_media_user_kind ON user_media (user_id, kind);

CREATE TABLE IF NOT EXISTS topics (
    user_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, slug)
);

CREATE TABLE IF NOT EXISTS profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic_slug TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    handle TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, topic_slug, url)
);
CREATE INDEX IF NOT EXISTS idx_profiles_user_topic ON profiles (user_id, topic_slug);

CREATE TABLE IF NOT EXISTS profile_cache (
    handle TEXT PRIMARY KEY,
    profile_url TEXT,
    reels_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    reel_count INTEGER NOT NULL DEFAULT 0,
    fetched_at DOUBLE PRECISION NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    video_id TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    author_handle TEXT NOT NULL,
    title TEXT,
    sound_id TEXT,
    sound_name TEXT,
    duration_sec INTEGER,
    current_pool INTEGER DEFAULT 1,
    published_at TIMESTAMP WITH TIME ZONE,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    transcript TEXT,
    transcribed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_videos_author ON videos (author_handle);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    views BIGINT NOT NULL DEFAULT 0,
    likes BIGINT NOT NULL DEFAULT 0,
    comments BIGINT NOT NULL DEFAULT 0,
    shares BIGINT NOT NULL DEFAULT 0,
    pool_level INTEGER NOT NULL,
    velocity_per_hour DOUBLE PRECISION DEFAULT 0.0,
    acceleration DOUBLE PRECISION DEFAULT 0.0,
    comment_ratio DOUBLE PRECISION DEFAULT 0.0,
    engagement_rate DOUBLE PRECISION DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_snapshots_video ON metric_snapshots (video_id, timestamp);
