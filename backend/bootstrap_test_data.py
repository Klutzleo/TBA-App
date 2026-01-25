"""
Bootstrap script to create test campaign for development/testing.
Run this after migrations to create a working test campaign.
"""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment")
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

def bootstrap_test_campaign():
    """Create a test campaign with channels for immediate testing"""

    print("\n🔧 Creating bootstrap test campaign...")
    print("=" * 60)

    # Check if test campaign already exists
    result = db.execute(text("SELECT id FROM campaigns WHERE id = 'test-campaign-001'"))
    if result.fetchone():
        print("✅ Test campaign already exists!")

        # Get channel IDs
        story_result = db.execute(text("""
            SELECT id, name FROM parties
            WHERE campaign_id = 'test-campaign-001' AND party_type = 'story'
        """))
        story_row = story_result.fetchone()

        ooc_result = db.execute(text("""
            SELECT id, name FROM parties
            WHERE campaign_id = 'test-campaign-001' AND party_type = 'ooc'
        """))
        ooc_row = ooc_result.fetchone()

        print(f"\n" + "=" * 60)
        print(f"📋 CAMPAIGN DETAILS - USE THESE IDS FOR TESTING:")
        print(f"=" * 60)
        print(f"Campaign ID:      test-campaign-001")
        if story_row:
            print(f"Story Channel ID: {story_row[0]}")
        if ooc_row:
            print(f"OOC Channel ID:   {ooc_row[0]}")
        print(f"=" * 60)
        return

    try:
        # Create test campaign
        db.execute(text("""
            INSERT INTO campaigns (id, name, description, story_weaver_id, created_by_id, is_active)
            VALUES (
                'test-campaign-001',
                'Test Campaign',
                'Bootstrap campaign for development and testing',
                NULL,
                'bootstrap-user',
                TRUE
            )
        """))

        print("✅ Campaign created!")

        # Trigger should auto-create channels, but let's verify
        db.commit()

        # Get the auto-created channel IDs
        story_result = db.execute(text("""
            SELECT id, name FROM parties
            WHERE campaign_id = 'test-campaign-001' AND party_type = 'story'
        """))
        story_row = story_result.fetchone()

        ooc_result = db.execute(text("""
            SELECT id, name FROM parties
            WHERE campaign_id = 'test-campaign-001' AND party_type = 'ooc'
        """))
        ooc_row = ooc_result.fetchone()

        if not story_row or not ooc_row:
            print("⚠️ Channels not auto-created by trigger, creating manually...")

            db.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, story_weaver_id, created_by_id, is_active)
                VALUES (
                    gen_random_uuid()::text,
                    'Test Campaign - Story',
                    'test-campaign-001',
                    'story',
                    NULL,
                    'bootstrap-user',
                    TRUE
                )
            """))

            db.execute(text("""
                INSERT INTO parties (id, name, campaign_id, party_type, story_weaver_id, created_by_id, is_active)
                VALUES (
                    gen_random_uuid()::text,
                    'Test Campaign - OOC',
                    'test-campaign-001',
                    'ooc',
                    NULL,
                    'bootstrap-user',
                    TRUE
                )
            """))

            db.commit()

            # Fetch again
            story_result = db.execute(text("""
                SELECT id, name FROM parties
                WHERE campaign_id = 'test-campaign-001' AND party_type = 'story'
            """))
            story_row = story_result.fetchone()

            ooc_result = db.execute(text("""
                SELECT id, name FROM parties
                WHERE campaign_id = 'test-campaign-001' AND party_type = 'ooc'
            """))
            ooc_row = ooc_result.fetchone()

        print(f"\n✅ Bootstrap complete!")
        print(f"\n" + "=" * 60)
        print(f"📋 CAMPAIGN DETAILS - USE THESE IDS FOR TESTING:")
        print(f"=" * 60)
        print(f"Campaign ID:      test-campaign-001")
        print(f"Story Channel ID: {story_row[0]}")
        print(f"OOC Channel ID:   {ooc_row[0]}")
        print(f"=" * 60)
        print(f"\n🎯 Next Steps:")
        print(f"   1. Go to /create-character")
        print(f"   2. Use Campaign ID: test-campaign-001")
        print(f"   3. Create 2 characters")
        print(f"   4. Connect to chat with Story Channel ID above")
        print(f"   5. Test messaging between windows!")

    except Exception as e:
        print(f"❌ Error creating bootstrap data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    bootstrap_test_campaign()
