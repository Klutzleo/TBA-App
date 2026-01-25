"""Manual bootstrap - run this if automatic bootstrap fails"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

print("\n🔧 Manually creating test campaign...")
print("=" * 60)

with engine.connect() as conn:
    try:
        # Check if campaign already exists
        result = conn.execute(text("SELECT id FROM campaigns WHERE id = 'test-campaign-001'"))
        if result.fetchone():
            print("✅ Test campaign already exists!")

            # Get channel IDs
            result = conn.execute(text("""
                SELECT id, name, party_type
                FROM parties
                WHERE campaign_id = 'test-campaign-001'
                ORDER BY party_type
            """))

            channels = result.fetchall()

            if channels:
                print(f"\n✅ Found {len(channels)} channels:")
                for channel in channels:
                    print(f"   {channel[2]}: {channel[0]} ({channel[1]})")

                story_channel = next((c for c in channels if c[2] == 'story'), None)
                ooc_channel = next((c for c in channels if c[2] == 'ooc'), None)

                print(f"\n" + "=" * 60)
                print(f"📋 CAMPAIGN DETAILS - USE THESE IDS FOR TESTING:")
                print(f"=" * 60)
                print(f"Campaign ID:      test-campaign-001")
                print(f"Story Channel ID: {story_channel[0] if story_channel else 'NOT FOUND'}")
                print(f"OOC Channel ID:   {ooc_channel[0] if ooc_channel else 'NOT FOUND'}")
                print(f"=" * 60)

            return

        # Create campaign
        conn.execute(text("""
            INSERT INTO campaigns (id, name, description, story_weaver_id, created_by_id, is_active)
            VALUES (
                'test-campaign-001',
                'Test Campaign',
                'Bootstrap campaign for testing',
                NULL,
                'bootstrap-user',
                TRUE
            )
        """))
        conn.commit()
        print("✅ Campaign created!")

        # Check if channels were auto-created by trigger
        result = conn.execute(text("""
            SELECT id, name, party_type
            FROM parties
            WHERE campaign_id = 'test-campaign-001'
            ORDER BY party_type
        """))

        channels = result.fetchall()

        if channels:
            print(f"\n✅ Found {len(channels)} auto-created channels:")
            for channel in channels:
                print(f"   {channel[2]}: {channel[0]} ({channel[1]})")

            story_channel = next((c for c in channels if c[2] == 'story'), None)
            ooc_channel = next((c for c in channels if c[2] == 'ooc'), None)

            print(f"\n" + "=" * 60)
            print(f"📋 CAMPAIGN DETAILS - USE THESE IDS FOR TESTING:")
            print(f"=" * 60)
            print(f"Campaign ID:      test-campaign-001")
            print(f"Story Channel ID: {story_channel[0] if story_channel else 'NOT FOUND'}")
            print(f"OOC Channel ID:   {ooc_channel[0] if ooc_channel else 'NOT FOUND'}")
            print(f"=" * 60)
        else:
            print("\n⚠️ No channels auto-created! Creating manually...")

            conn.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, created_by_id, is_active)
                VALUES (
                    gen_random_uuid()::text,
                    'Test Campaign - Story',
                    'test-campaign-001',
                    'story',
                    'bootstrap-user',
                    TRUE
                )
            """))

            conn.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, created_by_id, is_active)
                VALUES (
                    gen_random_uuid()::text,
                    'Test Campaign - OOC',
                    'test-campaign-001',
                    'ooc',
                    'bootstrap-user',
                    TRUE
                )
            """))

            conn.commit()

            # Fetch again
            result = conn.execute(text("""
                SELECT id, name, party_type
                FROM parties
                WHERE campaign_id = 'test-campaign-001'
            """))

            channels = result.fetchall()
            story_channel = next((c for c in channels if c[2] == 'story'), None)
            ooc_channel = next((c for c in channels if c[2] == 'ooc'), None)

            print(f"\n" + "=" * 60)
            print(f"📋 CAMPAIGN DETAILS - USE THESE IDS FOR TESTING:")
            print(f"=" * 60)
            print(f"Campaign ID:      test-campaign-001")
            print(f"Story Channel ID: {story_channel[0]}")
            print(f"OOC Channel ID:   {ooc_channel[0]}")
            print(f"=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
