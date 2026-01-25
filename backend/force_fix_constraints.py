"""
EMERGENCY FIX: Directly alter table constraints.
Run this if migrations are not working properly.
"""
import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

print("🔧 Forcing constraint fixes...")

try:
    with engine.connect() as conn:
        # Fix 1: Make parties.story_weaver_id nullable
        print("   Making parties.story_weaver_id nullable...")
        conn.execute(text("ALTER TABLE parties ALTER COLUMN story_weaver_id DROP NOT NULL"))
        conn.commit()
        print("   ✅ parties.story_weaver_id is now nullable")

        # Fix 2: Make campaigns.story_weaver_id nullable
        print("   Making campaigns.story_weaver_id nullable...")
        conn.execute(text("ALTER TABLE campaigns ALTER COLUMN story_weaver_id DROP NOT NULL"))
        conn.commit()
        print("   ✅ campaigns.story_weaver_id is now nullable")

        # Fix 3: Make campaigns.created_by_id nullable
        print("   Making campaigns.created_by_id nullable...")
        conn.execute(text("ALTER TABLE campaigns ALTER COLUMN created_by_id DROP NOT NULL"))
        conn.commit()
        print("   ✅ campaigns.created_by_id is now nullable")

        # Fix 4: Make characters.campaign_id nullable (SKIP - column doesn't exist yet)
        # print("   Making characters.campaign_id nullable...")
        # conn.execute(text("ALTER TABLE characters ALTER COLUMN campaign_id DROP NOT NULL"))
        # conn.commit()
        # print("   ✅ characters.campaign_id is now nullable")

        # Verify the fix
        result = conn.execute(text("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'parties' AND column_name = 'story_weaver_id'
        """))
        row = result.fetchone()

        if row[1] == 'YES':
            print("\n✅ SUCCESS! All constraints fixed.")
            print("   parties.story_weaver_id is now nullable")
        else:
            print("\n❌ FAILED! Constraint still exists!")
            sys.exit(1)

except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
