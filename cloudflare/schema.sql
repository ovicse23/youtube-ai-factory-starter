-- Cloudflare D1 / Local SQLite Schema for YouTube AI Factory (Hybrid Control Center)
-- Apply locally:  wrangler d1 execute youtube-ai-factory-db --local --file=cloudflare/schema.sql
-- Apply remotely: wrangler d1 execute youtube-ai-factory-db --remote --file=cloudflare/schema.sql

CREATE TABLE IF NOT EXISTS yaf_channels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  handle TEXT NOT NULL,
  niche TEXT NOT NULL,
  default_aspect TEXT NOT NULL DEFAULT '9:16',
  target_countries_json TEXT NOT NULL DEFAULT '["US","UK","CA","AU"]',
  creator_timezone TEXT NOT NULL DEFAULT 'Asia/Dhaka',
  studio_heatmap_override TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  keywords_json TEXT NOT NULL DEFAULT '[]',
  avatar_prompt TEXT NOT NULL DEFAULT '',
  banner_prompt TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_settings (
  id TEXT PRIMARY KEY DEFAULT 'global',
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_ideas (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  title TEXT NOT NULL,
  niche TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 80,
  rubric TEXT NOT NULL DEFAULT '',
  aspect TEXT NOT NULL DEFAULT '9:16',
  vidiq_summary TEXT NOT NULL DEFAULT '',
  promise TEXT NOT NULL DEFAULT '',
  upload_slot TEXT NOT NULL DEFAULT '',
  hooks_json TEXT NOT NULL DEFAULT '[]',
  sources_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'shortlisted',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_videos (
  slug TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  title TEXT NOT NULL,
  niche TEXT NOT NULL,
  aspect TEXT NOT NULL DEFAULT '9:16',
  status TEXT NOT NULL DEFAULT 'draft',
  episode_json TEXT NOT NULL,
  r2_final_key TEXT NOT NULL DEFAULT '',
  r2_thumb_key TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_approvals (
  video_slug TEXT PRIMARY KEY,
  digen_scene1_approved INTEGER NOT NULL DEFAULT 0,
  digen_remaining_approved INTEGER NOT NULL DEFAULT 0,
  qa_approved INTEGER NOT NULL DEFAULT 0,
  qa_checks_json TEXT NOT NULL DEFAULT '[false,false,false,false,false]',
  private_upload_approved INTEGER NOT NULL DEFAULT 0,
  scheduled_publish_window TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_jobs (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  video_slug TEXT NOT NULL DEFAULT '',
  job_type TEXT NOT NULL,
  target_runner TEXT NOT NULL DEFAULT 'local_engine',
  status TEXT NOT NULL DEFAULT 'queued',
  payload_json TEXT NOT NULL DEFAULT '{}',
  result_summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_analytics (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  video_slug TEXT NOT NULL,
  published_at TEXT NOT NULL DEFAULT '',
  views_48h INTEGER NOT NULL DEFAULT 0,
  viewed_vs_swiped_pct REAL NOT NULL DEFAULT 0,
  avg_completion_pct REAL NOT NULL DEFAULT 0,
  ctr_pct REAL NOT NULL DEFAULT 0,
  top_country TEXT NOT NULL DEFAULT 'US',
  publish_slot_used TEXT NOT NULL DEFAULT '',
  studio_heatmap_peak TEXT NOT NULL DEFAULT '',
  retention_notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_yaf_ideas_channel ON yaf_ideas(channel_id);
CREATE INDEX IF NOT EXISTS idx_yaf_videos_channel ON yaf_videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_yaf_jobs_status ON yaf_jobs(status, target_runner);
CREATE INDEX IF NOT EXISTS idx_yaf_analytics_channel ON yaf_analytics(channel_id);

CREATE TABLE IF NOT EXISTS yaf_niches (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  target_audience TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 85,
  demand_evidence TEXT NOT NULL DEFAULT '',
  competition_evidence TEXT NOT NULL DEFAULT '',
  format_recommendation TEXT NOT NULL DEFAULT '',
  breakout_creators_json TEXT NOT NULL DEFAULT '[]',
  experiment_plan_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'recommended',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_automations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  rule_type TEXT NOT NULL,
  schedule TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  channel_id TEXT NOT NULL DEFAULT 'all',
  provider TEXT NOT NULL DEFAULT 'auto',
  max_credits INTEGER NOT NULL DEFAULT 50,
  last_run TEXT NOT NULL DEFAULT '',
  next_run TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_characters (
  id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  name TEXT NOT NULL,
  appearance TEXT NOT NULL,
  clothing TEXT NOT NULL,
  colors TEXT NOT NULL,
  voice_notes TEXT NOT NULL DEFAULT '',
  style_bible TEXT NOT NULL DEFAULT '',
  reference_image_prompt TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yaf_provider_usage (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  action TEXT NOT NULL,
  credits_used REAL NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_yaf_characters_channel ON yaf_characters(channel_id);
CREATE INDEX IF NOT EXISTS idx_yaf_automations_enabled ON yaf_automations(enabled);
