CREATE TABLE IF NOT EXISTS automation_runs (
    id SERIAL PRIMARY KEY,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    business_name VARCHAR(255) NOT NULL,
    niche TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    trend_keywords TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    hook TEXT NOT NULL DEFAULT '',
    pain_point TEXT NOT NULL DEFAULT '',
    cta TEXT NOT NULL DEFAULT '',
    idea_summary TEXT NOT NULL DEFAULT '',
    script_json TEXT NOT NULL DEFAULT '{}',
    caption TEXT NOT NULL DEFAULT '',
    hashtags TEXT NOT NULL DEFAULT '',
    video_prompt_json TEXT NOT NULL DEFAULT '{}',
    local_video_path TEXT NOT NULL DEFAULT '',
    public_video_url TEXT NOT NULL DEFAULT '',
    instagram_media_id VARCHAR(255) NOT NULL DEFAULT '',
    facebook_video_id VARCHAR(255) NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_automation_runs_status ON automation_runs(status);
CREATE INDEX IF NOT EXISTS ix_automation_runs_created_at ON automation_runs(created_at);

