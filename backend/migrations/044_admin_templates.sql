-- Admin center, phase D: saved message templates for the admin. Additive only; safe to re-run.

CREATE TABLE IF NOT EXISTS admin_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(60) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    body VARCHAR(1000) NOT NULL,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
