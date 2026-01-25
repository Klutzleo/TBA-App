"""Fix the trigger to not use story_weaver_id"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    exit(1)

engine = create_engine(DATABASE_URL)

trigger_sql = """
-- Drop existing trigger and function WITH CASCADE
DROP TRIGGER IF EXISTS create_default_campaign_channels_trigger ON campaigns CASCADE;
DROP FUNCTION IF EXISTS create_default_campaign_channels() CASCADE;

-- Recreate function WITHOUT story_weaver_id
CREATE OR REPLACE FUNCTION create_default_campaign_channels()
RETURNS TRIGGER AS $$
BEGIN
    -- Create Story channel (no story_weaver_id - it's campaign-level)
    INSERT INTO parties (
        id, campaign_id, name, description, party_type, created_by_id, is_active
    ) VALUES (
        gen_random_uuid()::text, NEW.id, NEW.name || ' - Story',
        'Main story channel for ' || NEW.name, 'story', NEW.created_by_id, TRUE
    );

    -- Create OOC channel
    INSERT INTO parties (
        id, campaign_id, name, description, party_type, created_by_id, is_active
    ) VALUES (
        gen_random_uuid()::text, NEW.id, NEW.name || ' - OOC',
        'Out-of-character chat for ' || NEW.name, 'ooc', NEW.created_by_id, TRUE
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate trigger
CREATE TRIGGER create_default_campaign_channels_trigger
    AFTER INSERT ON campaigns
    FOR EACH ROW
    EXECUTE FUNCTION create_default_campaign_channels();
"""

print("🔧 Fixing trigger to not use story_weaver_id...")

try:
    with engine.connect() as conn:
        conn.execute(text(trigger_sql))
        conn.commit()
        print("✅ Trigger fixed!")
except Exception as e:
    print(f"⚠️ Trigger fix failed (non-blocking): {e}")
    print("   Continuing with bootstrap...")
