-- Migration 023: Env Check effect category (Damage/Debuff/Buff/Healing rework).
-- Damage/Debuff are contested and still create a stat_check_requests row;
-- Buff/Healing "just happen" per the rulebook and apply instantly (no row at all).
-- Additive only — safe to re-run.

ALTER TABLE stat_check_requests
  ADD COLUMN IF NOT EXISTS env_effect VARCHAR(10) NOT NULL DEFAULT 'damage';
