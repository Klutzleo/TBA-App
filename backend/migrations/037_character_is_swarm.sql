-- Swarms (rules v3.1): lots of weak bodies sharing one stat block. They cannot be healed, and the DP being subtracted is the
-- bodies in the swarm dying. A flag on the character. Additive only; safe to re-run.

ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_swarm BOOLEAN NOT NULL DEFAULT FALSE;
