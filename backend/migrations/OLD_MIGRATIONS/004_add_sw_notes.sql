-- Migration 004: Add sw_notes column to campaigns table
ALTER TABLE campaigns
  ADD COLUMN IF NOT EXISTS sw_notes TEXT;
