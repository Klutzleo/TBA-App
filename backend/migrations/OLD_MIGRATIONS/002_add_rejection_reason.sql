-- Add rejection_reason column to characters table
-- Used when a Story Weaver rejects a character in 'approval_required' mode

ALTER TABLE characters
ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
