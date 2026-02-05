-- Migration 011: Add password_reset_tokens table for password recovery
-- Phase 3: Authentication system - password reset functionality

-- Create password_reset_tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    token VARCHAR(36) UNIQUE NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_password_reset_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires ON password_reset_tokens(expires_at);

-- Add comments for documentation
COMMENT ON TABLE password_reset_tokens IS 'Password reset tokens for secure password recovery';
COMMENT ON COLUMN password_reset_tokens.token IS 'Unique token sent to user via email';
COMMENT ON COLUMN password_reset_tokens.expires_at IS 'Token expiration timestamp';
COMMENT ON COLUMN password_reset_tokens.used IS 'Whether token has been used (single-use)';

SELECT 'Migration 011: Password reset tokens table created' AS status;
