-- Temporary fix: Drop corrupted users tables
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS password_reset_tokens CASCADE;

SELECT '✅ Dropped corrupted users tables' AS status;