-- Admin center, phase B: player and bug reports, and the admin audit log. Additive only; safe to re-run.

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY,
    kind VARCHAR(10) NOT NULL,
    reporter_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    campaign_id UUID,
    message_id UUID,
    reason VARCHAR(30) NOT NULL,
    note VARCHAR(2000),
    snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(12) NOT NULL DEFAULT 'open',
    admin_note VARCHAR(2000),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_reports_reporter_user_id ON reports (reporter_user_id);
CREATE INDEX IF NOT EXISTS ix_reports_reported_user_id ON reports (reported_user_id);
CREATE INDEX IF NOT EXISTS ix_reports_campaign_id ON reports (campaign_id);
CREATE INDEX IF NOT EXISTS ix_reports_created_at ON reports (created_at);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY,
    admin_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(40) NOT NULL,
    report_id UUID,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_admin_user_id ON admin_audit_log (admin_user_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_report_id ON admin_audit_log (report_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_created_at ON admin_audit_log (created_at);
