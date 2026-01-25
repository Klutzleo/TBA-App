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

        # Fix 4: Drop foreign key on parties.created_by_id (points to wrong table)
        print("   Dropping foreign key parties_created_by_id_fkey...")
        try:
            conn.execute(text("ALTER TABLE parties DROP CONSTRAINT IF EXISTS parties_created_by_id_fkey"))
            conn.commit()
            print("   ✅ Foreign key dropped")
        except Exception as e:
            print(f"   ⚠️ FK drop failed (might not exist): {e}")

        # Fix 5: Make parties.created_by_id nullable
        print("   Making parties.created_by_id nullable...")
        conn.execute(text("ALTER TABLE parties ALTER COLUMN created_by_id DROP NOT NULL"))
        conn.commit()
        print("   ✅ parties.created_by_id is now nullable")

        print("\n✅ SUCCESS! All constraints fixed.")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
