-- Migration 003: Add BAP token fields to characters table
-- BAP token system: SW grants tokens, players spend before rolls, or SW applies retroactively

ALTER TABLE characters
  ADD COLUMN IF NOT EXISTS bap_token_active BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS bap_token_expires_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS bap_token_type VARCHAR(20);
-- bap_token_type values: 'encounter', '24hrs', 'sw_choice'
