-- ================================================================
-- Migration 024: Fix password_reset_tokens UUID Types
-- ================================================================
-- Problem: Migration 011 created password_reset_tokens with VARCHAR ids
-- but users.id is UUID, causing FK constraint failure.
--
-- Solution: Drop and recreate password_reset_tokens with UUID types.
-- ================================================================

DO $$
BEGIN
    -- Drop the table if it exists (it may have wrong types)
    DROP TABLE IF EXISTS password_reset_tokens CASCADE;
    RAISE NOTICE '✅ Dropped password_reset_tokens table';

    -- Recreate password_reset_tokens table with UUID types
    CREATE TABLE password_reset_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        token VARCHAR NOT NULL UNIQUE,
        user_id UUID NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        used BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT fk_password_reset_tokens_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Create indexes for performance
    CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens(token);
    CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
    CREATE INDEX idx_password_reset_tokens_expires ON password_reset_tokens(expires_at);

    -- Add comments for documentation
    COMMENT ON TABLE password_reset_tokens IS 'Password reset tokens for secure password recovery';
    COMMENT ON COLUMN password_reset_tokens.token IS 'Unique token sent to user via email';
    COMMENT ON COLUMN password_reset_tokens.expires_at IS 'Token expiration timestamp';
    COMMENT ON COLUMN password_reset_tokens.used IS 'Whether token has been used (single-use)';

    RAISE NOTICE '✅ Recreated password_reset_tokens table with UUID types';
    RAISE NOTICE '✅✅✅ Migration 024: password_reset_tokens UUID types fixed!';

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE '❌ Migration 024 failed: %', SQLERRM;
        RAISE;
END $$;
