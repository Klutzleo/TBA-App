-- Moderation foundation + campaign banner columns. Additive only.
-- The banner columns are dormant until the banner upload endpoint ships; the report table
-- ships first so a way to report and remove a banner exists before any banner can.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS banner_url TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS banner_locked BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS content_reports (
    id                   UUID PRIMARY KEY,
    reporter_user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_type         VARCHAR(30) NOT NULL,
    content_id           UUID NOT NULL,
    reason               VARCHAR(30) NOT NULL,
    note                 VARCHAR(500),
    snapshot             JSONB NOT NULL DEFAULT '{}',
    status               VARCHAR(20) NOT NULL DEFAULT 'open',
    resolution           VARCHAR(30),
    created_at           TIMESTAMP NOT NULL DEFAULT now(),
    resolved_at          TIMESTAMP,
    resolved_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_content_report_once UNIQUE (reporter_user_id, content_type, content_id)
);

CREATE INDEX IF NOT EXISTS ix_content_reports_reporter_user_id ON content_reports(reporter_user_id);
CREATE INDEX IF NOT EXISTS ix_content_reports_content_id ON content_reports(content_id);
CREATE INDEX IF NOT EXISTS ix_content_reports_status ON content_reports(status);
