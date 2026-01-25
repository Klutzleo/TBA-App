"""Manual bootstrap - run this if automatic bootstrap fails"""
import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

print("="*70)
print("🔧 MANUAL BOOTSTRAP - Creating test campaign...")
print("="*70)

try:
    with engine.connect() as conn:
        # Check if already exists
        result = conn.execute(text("SELECT id FROM campaigns WHERE id = 'test-campaign-001'"))
        if result.fetchone():
            print("✅ Test campaign already exists!")

            # Get channel IDs
            channels = conn.execute(text("""
                SELECT id, name, party_type
                FROM parties
                WHERE campaign_id = 'test-campaign-001'
            """))

            for channel in channels:
                print(f"   {channel[2]}: {channel[0]}")

            sys.exit(0)

        # Create campaign
        print("Creating campaign...")
        conn.execute(text("""
            INSERT INTO campaigns (id, name, description, story_weaver_id, created_by_id, is_active)
            VALUES ('test-campaign-001', 'Test Campaign', 'Bootstrap', NULL, NULL, TRUE)
        """))
        conn.commit()
        print("✅ Campaign created!")

        # Check if channels were auto-created
        result = conn.execute(text("""
            SELECT id, name, party_type
            FROM parties
            WHERE campaign_id = 'test-campaign-001'
        """))

        channels = list(result.fetchall())

        if channels:
            print(f"✅ Found {len(channels)} auto-created channels")
        else:
            print("⚠️ No channels auto-created, creating manually...")

            conn.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, is_active)
                VALUES (gen_random_uuid()::text, 'Test Campaign - Story', 'test-campaign-001', 'story', TRUE)
            """))

            conn.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, is_active)
                VALUES (gen_random_uuid()::text, 'Test Campaign - OOC', 'test-campaign-001', 'ooc', TRUE)
            """))

            conn.commit()

            result = conn.execute(text("""
                SELECT id, name, party_type
                FROM parties
                WHERE campaign_id = 'test-campaign-001'
            """))
            channels = list(result.fetchall())

        # Print results
        print("\n" + "="*70)
        print("✅ BOOTSTRAP COMPLETE!")
        print("="*70)
        print(f"\n📋 Campaign ID: test-campaign-001")

        for channel in channels:
            if channel[2] == 'story':
                print(f"📖 Story Channel ID: {channel[0]}")
            elif channel[2] == 'ooc':
                print(f"💬 OOC Channel ID: {channel[0]}")

        print("\n🎯 Next Steps:")
        print("   1. Go to /create-character")
        print("   2. Use Campaign ID: test-campaign-001")
        print("   3. Create 2 characters")
        print("   4. Connect to chat with Story Channel ID above")
        print("="*70)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
