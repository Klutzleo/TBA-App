-- Email verification at signup. New accounts get a confirmation link; confirming sets email_verified_at.
--
-- Accounts that already exist were never asked to verify, so they are marked exempt ("signed up before verification existed"). That is honest
-- (they are NOT recorded as verified) and means turning the optional REQUIRE_VERIFIED_EMAIL switch on later cannot lock out anyone who is
-- already playing. The exemption is applied only the one time the column is first added, so re-running this file never exempts a new signup.
-- Additive only.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'email_verification_exempt') THEN
        ALTER TABLE users ADD COLUMN email_verification_exempt BOOLEAN NOT NULL DEFAULT FALSE;
        UPDATE users SET email_verification_exempt = TRUE;
    END IF;
END $$;

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMP;
