-- HymnFlow — Supabase Table Setup
-- Run this in your Supabase SQL editor (Dashboard → SQL Editor → New Query)

-- ── Hymns table ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hymns (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title            TEXT NOT NULL,
    theme            TEXT NOT NULL,
    style            TEXT NOT NULL,          -- Praise | Worship | Lament | Thanksgiving | Intercession
    lyrics           JSONB NOT NULL,         -- Array of stanzas, each with label + lines[]
    bible_verse      TEXT NOT NULL,
    bible_reference  TEXT NOT NULL,          -- e.g. "John 3:16"
    seo_title        TEXT,
    seo_description  TEXT,
    seo_tags         JSONB DEFAULT '[]',
    status           TEXT DEFAULT 'pending', -- pending | approved | rejected | rendered | scheduled | posted
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── Videos table ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    hymn_id          UUID REFERENCES hymns(id) ON DELETE CASCADE,
    video_path       TEXT NOT NULL,          -- Path on Render disk / cloud storage
    thumbnail_path   TEXT,
    rendered_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── YouTube posts table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS youtube_posts (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    hymn_id          UUID REFERENCES hymns(id) ON DELETE CASCADE,
    video_id         TEXT NOT NULL,          -- YouTube video ID (e.g. "dQw4w9WgXcQ")
    youtube_url      TEXT NOT NULL,
    views            INTEGER DEFAULT 0,
    likes            INTEGER DEFAULT 0,
    comments         INTEGER DEFAULT 0,
    posted_at        TIMESTAMPTZ DEFAULT NOW(),
    stats_updated_at TIMESTAMPTZ
);

-- ── Indexes for common queries ────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hymns_status     ON hymns(status);
CREATE INDEX IF NOT EXISTS idx_hymns_created_at ON hymns(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_hymn_id   ON videos(hymn_id);
CREATE INDEX IF NOT EXISTS idx_posts_hymn_id    ON youtube_posts(hymn_id);

-- ── Auto-update updated_at on hymns ──────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER hymns_updated_at
    BEFORE UPDATE ON hymns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
