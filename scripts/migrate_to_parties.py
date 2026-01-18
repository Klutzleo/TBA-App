#!/usr/bin/env python3
"""
Migration Script: Migrate existing campaign data to the new party system.

Phase 2d Migration - Creates Story and OOC parties for each campaign,
adds characters to both parties, and updates messages with party_id.

Usage:
    python scripts/migrate_to_parties.py

Features:
    - Discovers campaigns from existing parties and messages
    - Creates 'Story' party (party_type='story') per campaign
    - Creates 'OOC' party (party_type='ooc') per campaign
    - Adds all campaign characters to both Story and OOC parties
    - Updates messages to reference the Story party
    - Idempotent: safe to run multiple times
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables (skip in container)
if not os.path.exists("/.dockerenv"):
    load_dotenv()

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Get database URL and convert to async format
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")

# Convert sync URL to async URL
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("sqlite://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Create async engine and session
engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def should_run_migration() -> bool:
    """
    Check if the migration needs to run.

    Returns False if:
    - Story/OOC parties already exist for campaigns
    - No campaigns exist to migrate

    This allows the migration to be called on every startup
    without doing unnecessary work.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Check if we have any campaigns in messages
            result = await session.execute(
                text("SELECT COUNT(DISTINCT campaign_id) FROM messages WHERE campaign_id IS NOT NULL")
            )
            campaign_count = result.scalar() or 0

            if campaign_count == 0:
                # No campaigns to migrate
                return False

            # Check if we already have story parties for campaigns
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM parties
                    WHERE party_type = 'story' AND campaign_id IS NOT NULL
                """)
            )
            story_party_count = result.scalar() or 0

            # If we have story parties for most campaigns, skip migration
            # (allows for partial migrations to complete)
            if story_party_count >= campaign_count:
                return False

            return True

        except Exception as e:
            # If we can't check, assume migration is needed
            print(f"  Warning: Could not check migration status: {e}")
            return True


async def get_unique_campaigns(session: AsyncSession) -> list[str]:
    """
    Discover unique campaign IDs from existing data.

    Sources:
    - parties.campaign_id (if any exist)
    - messages.campaign_id (primary source)
    """
    campaigns = set()

    # Get campaigns from messages table
    try:
        result = await session.execute(
            text("SELECT DISTINCT campaign_id FROM messages WHERE campaign_id IS NOT NULL")
        )
        for row in result:
            if row[0]:
                campaigns.add(row[0])
        print(f"  Found {len(campaigns)} campaigns in messages table")
    except Exception as e:
        print(f"  Warning: Could not query messages table: {e}")

    # Get campaigns from parties table (in case some already have campaign_id)
    try:
        result = await session.execute(
            text("SELECT DISTINCT campaign_id FROM parties WHERE campaign_id IS NOT NULL")
        )
        for row in result:
            if row[0]:
                campaigns.add(row[0])
        print(f"  Total unique campaigns after checking parties: {len(campaigns)}")
    except Exception as e:
        print(f"  Warning: Could not query parties.campaign_id: {e}")

    return list(campaigns)


async def get_story_weaver_for_campaign(session: AsyncSession, campaign_id: str) -> Optional[str]:
    """
    Find a suitable Story Weaver character ID for a campaign.

    Strategy:
    1. Look for existing party with this campaign_id and use its story_weaver_id
    2. Fall back to any character that has sent messages in this campaign
    3. Fall back to any character in the database
    """
    # Try existing parties first
    try:
        result = await session.execute(
            text("""
                SELECT story_weaver_id FROM parties
                WHERE campaign_id = :campaign_id
                AND story_weaver_id IS NOT NULL
                LIMIT 1
            """),
            {"campaign_id": campaign_id}
        )
        row = result.fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass

    # Try to find a character who sent messages in this campaign
    try:
        result = await session.execute(
            text("""
                SELECT DISTINCT m.sender_id
                FROM messages m
                JOIN characters c ON c.id = m.sender_id
                WHERE m.campaign_id = :campaign_id
                LIMIT 1
            """),
            {"campaign_id": campaign_id}
        )
        row = result.fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass

    # Fall back to any character
    try:
        result = await session.execute(
            text("SELECT id FROM characters LIMIT 1")
        )
        row = result.fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass

    return None


async def party_exists(session: AsyncSession, campaign_id: str, party_type: str) -> Optional[str]:
    """
    Check if a party of given type already exists for the campaign.
    Returns the party ID if it exists, None otherwise.
    """
    try:
        result = await session.execute(
            text("""
                SELECT id FROM parties
                WHERE campaign_id = :campaign_id AND party_type = :party_type
                LIMIT 1
            """),
            {"campaign_id": campaign_id, "party_type": party_type}
        )
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        return None


async def create_party(
    session: AsyncSession,
    campaign_id: str,
    name: str,
    party_type: str,
    story_weaver_id: str
) -> str:
    """
    Create a new party for the campaign.
    Returns the new party ID.
    """
    party_id = str(uuid.uuid4())
    now = datetime.utcnow()

    await session.execute(
        text("""
            INSERT INTO parties (
                id, name, description, campaign_id, party_type,
                story_weaver_id, created_by_id, is_active, created_at, updated_at
            ) VALUES (
                :id, :name, :description, :campaign_id, :party_type,
                :story_weaver_id, :created_by_id, :is_active, :created_at, :updated_at
            )
        """),
        {
            "id": party_id,
            "name": name,
            "description": f"Auto-created {party_type} party for campaign migration",
            "campaign_id": campaign_id,
            "party_type": party_type,
            "story_weaver_id": story_weaver_id,
            "created_by_id": story_weaver_id,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
    )

    return party_id


async def get_campaign_characters(session: AsyncSession, campaign_id: str) -> list[str]:
    """
    Get all character IDs associated with a campaign.

    Sources:
    - Characters who sent messages in this campaign
    - Characters in existing party memberships for parties in this campaign
    """
    characters = set()

    # Get characters from messages
    try:
        result = await session.execute(
            text("""
                SELECT DISTINCT m.sender_id
                FROM messages m
                JOIN characters c ON c.id = m.sender_id
                WHERE m.campaign_id = :campaign_id
            """),
            {"campaign_id": campaign_id}
        )
        for row in result:
            if row[0]:
                characters.add(row[0])
    except Exception as e:
        print(f"    Warning: Could not get characters from messages: {e}")

    # Get characters from existing party memberships
    try:
        result = await session.execute(
            text("""
                SELECT DISTINCT pm.character_id
                FROM party_memberships pm
                JOIN parties p ON p.id = pm.party_id
                WHERE p.campaign_id = :campaign_id
            """),
            {"campaign_id": campaign_id}
        )
        for row in result:
            if row[0]:
                characters.add(row[0])
    except Exception as e:
        print(f"    Warning: Could not get characters from party_memberships: {e}")

    return list(characters)


async def membership_exists(session: AsyncSession, party_id: str, character_id: str) -> bool:
    """Check if a character is already a member of a party."""
    try:
        result = await session.execute(
            text("""
                SELECT 1 FROM party_memberships
                WHERE party_id = :party_id AND character_id = :character_id
                LIMIT 1
            """),
            {"party_id": party_id, "character_id": character_id}
        )
        return result.fetchone() is not None
    except Exception:
        return False


async def add_party_member(session: AsyncSession, party_id: str, character_id: str):
    """Add a character to a party."""
    membership_id = str(uuid.uuid4())
    now = datetime.utcnow()

    await session.execute(
        text("""
            INSERT INTO party_memberships (id, party_id, character_id, joined_at)
            VALUES (:id, :party_id, :character_id, :joined_at)
        """),
        {
            "id": membership_id,
            "party_id": party_id,
            "character_id": character_id,
            "joined_at": now
        }
    )


async def update_messages_party_id(session: AsyncSession, campaign_id: str, story_party_id: str) -> int:
    """
    Update all messages in a campaign to reference the Story party.
    Returns the number of messages updated.
    """
    result = await session.execute(
        text("""
            UPDATE messages
            SET party_id = :party_id
            WHERE campaign_id = :campaign_id
            AND (party_id IS NULL OR party_id != :party_id)
        """),
        {"party_id": story_party_id, "campaign_id": campaign_id}
    )
    return result.rowcount


async def migrate_campaign(session: AsyncSession, campaign_id: str) -> dict:
    """
    Migrate a single campaign to the party system.

    Returns a summary dict with counts.
    """
    summary = {
        "campaign_id": campaign_id,
        "story_party_created": False,
        "ooc_party_created": False,
        "members_added": 0,
        "messages_updated": 0,
        "errors": []
    }

    print(f"\n  Processing campaign: {campaign_id[:8]}...")

    # Get Story Weaver for this campaign
    story_weaver_id = await get_story_weaver_for_campaign(session, campaign_id)
    if not story_weaver_id:
        summary["errors"].append("No suitable Story Weaver found")
        print(f"    ERROR: No Story Weaver found for campaign")
        return summary

    print(f"    Story Weaver: {story_weaver_id[:8]}...")

    # Create or get Story party
    story_party_id = await party_exists(session, campaign_id, "story")
    if story_party_id:
        print(f"    Story party already exists: {story_party_id[:8]}...")
    else:
        story_party_id = await create_party(
            session, campaign_id, "Story", "story", story_weaver_id
        )
        summary["story_party_created"] = True
        print(f"    Created Story party: {story_party_id[:8]}...")

    # Create or get OOC party
    ooc_party_id = await party_exists(session, campaign_id, "ooc")
    if ooc_party_id:
        print(f"    OOC party already exists: {ooc_party_id[:8]}...")
    else:
        ooc_party_id = await create_party(
            session, campaign_id, "OOC", "ooc", story_weaver_id
        )
        summary["ooc_party_created"] = True
        print(f"    Created OOC party: {ooc_party_id[:8]}...")

    # Get characters for this campaign
    characters = await get_campaign_characters(session, campaign_id)
    print(f"    Found {len(characters)} characters")

    # Add characters to both parties
    for char_id in characters:
        # Add to Story party
        if not await membership_exists(session, story_party_id, char_id):
            await add_party_member(session, story_party_id, char_id)
            summary["members_added"] += 1

        # Add to OOC party
        if not await membership_exists(session, ooc_party_id, char_id):
            await add_party_member(session, ooc_party_id, char_id)
            summary["members_added"] += 1

    print(f"    Added {summary['members_added']} party memberships")

    # Update messages to reference Story party
    messages_updated = await update_messages_party_id(session, campaign_id, story_party_id)
    summary["messages_updated"] = messages_updated
    print(f"    Updated {messages_updated} messages with party_id")

    return summary


async def run_migration():
    """Main migration function."""
    print("=" * 60)
    print("Phase 2d Migration: Migrate to Party System")
    print("=" * 60)
    print(f"\nDatabase: {DATABASE_URL[:50]}...")
    print(f"Async URL: {ASYNC_DATABASE_URL[:50]}...")

    async with AsyncSessionLocal() as session:
        try:
            # Test connection
            await session.execute(text("SELECT 1"))
            print("\n✅ Database connection established")

            # Discover campaigns
            print("\n[1/4] Discovering campaigns...")
            campaigns = await get_unique_campaigns(session)

            if not campaigns:
                print("\n⚠️ No campaigns found to migrate.")
                print("   This could mean:")
                print("   - No messages exist in the database yet")
                print("   - Messages don't have campaign_id set")
                return

            print(f"\n[2/4] Found {len(campaigns)} campaigns to process")

            # Process each campaign
            print("\n[3/4] Migrating campaigns...")
            total_summary = {
                "campaigns_processed": 0,
                "story_parties_created": 0,
                "ooc_parties_created": 0,
                "members_added": 0,
                "messages_updated": 0,
                "errors": []
            }

            for campaign_id in campaigns:
                try:
                    summary = await migrate_campaign(session, campaign_id)
                    total_summary["campaigns_processed"] += 1
                    if summary["story_party_created"]:
                        total_summary["story_parties_created"] += 1
                    if summary["ooc_party_created"]:
                        total_summary["ooc_parties_created"] += 1
                    total_summary["members_added"] += summary["members_added"]
                    total_summary["messages_updated"] += summary["messages_updated"]
                    total_summary["errors"].extend(summary["errors"])
                except Exception as e:
                    print(f"    ERROR: {e}")
                    total_summary["errors"].append(f"{campaign_id}: {str(e)}")

            # Commit all changes
            print("\n[4/4] Committing changes...")
            await session.commit()
            print("✅ Changes committed successfully")

            # Print summary
            print("\n" + "=" * 60)
            print("Migration Summary")
            print("=" * 60)
            print(f"  Campaigns processed:    {total_summary['campaigns_processed']}")
            print(f"  Story parties created:  {total_summary['story_parties_created']}")
            print(f"  OOC parties created:    {total_summary['ooc_parties_created']}")
            print(f"  Party members added:    {total_summary['members_added']}")
            print(f"  Messages updated:       {total_summary['messages_updated']}")

            if total_summary["errors"]:
                print(f"\n⚠️ Errors encountered: {len(total_summary['errors'])}")
                for err in total_summary["errors"]:
                    print(f"   - {err}")
            else:
                print("\n✅ Migration completed successfully!")

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
