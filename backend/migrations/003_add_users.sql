-- Phase 3: User Authentication System
-- Creates users table and modifies characters table to support user accounts

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Add user_id to characters table (nullable for backward compatibility)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='characters' AND column_name='user_id'
    ) THEN
        ALTER TABLE characters ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_characters_user_id ON characters(user_id);
    END IF;
END $$;

-- Create sessions table for refresh tokens
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(refresh_token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Add comments for documentation
COMMENT ON TABLE users IS 'User accounts for authentication';
COMMENT ON COLUMN users.username IS 'Unique username for login (alphanumeric + underscores)';
COMMENT ON COLUMN users.email IS 'User email address for account recovery';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hashed password';
COMMENT ON COLUMN users.last_login IS 'Timestamp of most recent successful login';

COMMENT ON TABLE sessions IS 'JWT refresh tokens for maintaining authentication';
COMMENT ON COLUMN sessions.refresh_token IS 'Secure random token for refreshing access tokens';
COMMENT ON COLUMN sessions.expires_at IS 'Token expiration timestamp';

COMMENT ON COLUMN characters.user_id IS 'Links character to owning user account (nullable for backward compatibility)';

-- Create a function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to auto-update updated_at on users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

PRINT 'Phase 3 migration completed: Users table and authentication system created';
