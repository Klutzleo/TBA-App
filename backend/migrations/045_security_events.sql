-- Admin center, phase E: a small log of blocked signups, failed logins, rate-limit hits and unhandled server errors.
-- No raw IPs (a salted hash only), no emails, no request bodies. Old rows are pruned by the app after 30 days. Additive only; safe to re-run.

CREATE TABLE IF NOT EXISTS security_events (
    id UUID PRIMARY KEY,
    kind VARCHAR(20) NOT NULL,
    ip_hash VARCHAR(16),
    user_id UUID,
    path VARCHAR(200),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_security_events_kind ON security_events (kind);
CREATE INDEX IF NOT EXISTS ix_security_events_ip_hash ON security_events (ip_hash);
CREATE INDEX IF NOT EXISTS ix_security_events_created_at ON security_events (created_at);
