-- Migration 012: Fix users table schema to match User model
-- Ensures column names match what the SQLAlchemy model expects

-- Rename password_hash to hashed_password if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'password_hash'
    ) THEN
        ALTER TABLE users RENAME COLUMN password_hash TO hashed_password;
        RAISE NOTICE 'Renamed password_hash to hashed_password';
    ELSE
        RAISE NOTICE 'Column password_hash does not exist or already renamed';
    END IF;
END $$;

-- Add is_active column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
        RAISE NOTICE 'Added is_active column';
    ELSE
        RAISE NOTICE 'Column is_active already exists';
    END IF;
END $$;

-- Make user_id on characters NOT NULL and add CASCADE delete
-- (Only if users table exists and has data)
DO $$
BEGIN
    -- First check if users table has any rows
    IF EXISTS (SELECT 1 FROM users LIMIT 1) THEN
        -- Update characters with NULL user_id to use a default user
        -- (This is a placeholder - in production you'd want manual migration)
        RAISE NOTICE 'Users table has data - manual migration may be needed for characters.user_id';
    ELSE
        RAISE NOTICE 'Users table is empty - skipping characters.user_id update';
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON COLUMN users.hashed_password IS 'bcrypt hashed password (renamed from password_hash)';
COMMENT ON COLUMN users.is_active IS 'Whether user account is active (can login)';

SELECT 'Migration 012: Users table schema fixed to match User model' AS status;
