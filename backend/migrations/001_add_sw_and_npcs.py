"""
Migration 001: Add Story Weaver tracking, NPCs, and Combat Turns

Phase 2b migration for WebSocket chat macros system.

Changes:
1. Add story_weaver_id and created_by_id to parties table
2. Create npcs table for Story Weaver-created NPCs
3. Create combat_turns table for turn-based combat tracking
4. Backfill existing parties with first member as SW/creator

Usage:
    python backend/migrations/001_add_sw_and_npcs.py

Requirements:
    - Run with DATABASE_URL environment variable set
    - Idempotent: safe to run multiple times
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.db import DATABASE_URL, Base
from backend.models import Party, Character, PartyMembership, NPC, CombatTurn


def column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(engine, table_name):
    """Check if a table exists."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """Execute the migration."""
    print(f"Running migration 001: Add Story Weaver and NPCs")
    print(f"Database: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Step 1: Add story_weaver_id and created_by_id columns to parties table
        if table_exists(engine, 'parties'):
            print("\n[1/4] Updating parties table...")

            if not column_exists(engine, 'parties', 'story_weaver_id'):
                print("  - Adding story_weaver_id column")
                session.execute(text("""
                    ALTER TABLE parties
                    ADD COLUMN story_weaver_id VARCHAR
                """))
                session.commit()
            else:
                print("  - story_weaver_id column already exists")

            if not column_exists(engine, 'parties', 'created_by_id'):
                print("  - Adding created_by_id column")
                session.execute(text("""
                    ALTER TABLE parties
                    ADD COLUMN created_by_id VARCHAR
                """))
                session.commit()
            else:
                print("  - created_by_id column already exists")
        else:
            print("\n[1/4] Parties table doesn't exist yet - will be created by init_db()")

        # Step 2: Create npcs table
        print("\n[2/4] Creating npcs table...")
        if not table_exists(engine, 'npcs'):
            print("  - Creating npcs table")
            Base.metadata.tables['npcs'].create(engine)
            print("  - npcs table created successfully")
        else:
            print("  - npcs table already exists")

        # Step 3: Create combat_turns table
        print("\n[3/4] Creating combat_turns table...")
        if not table_exists(engine, 'combat_turns'):
            print("  - Creating combat_turns table")
            Base.metadata.tables['combat_turns'].create(engine)
            print("  - combat_turns table created successfully")
        else:
            print("  - combat_turns table already exists")

        # Step 4: Backfill existing parties
        print("\n[4/4] Backfilling existing parties...")
        if table_exists(engine, 'parties') and table_exists(engine, 'party_memberships'):
            # Get all parties without story_weaver_id
            parties = session.execute(text("""
                SELECT id FROM parties
                WHERE story_weaver_id IS NULL OR created_by_id IS NULL
            """)).fetchall()

            if parties:
                print(f"  - Found {len(parties)} parties to backfill")

                for party_row in parties:
                    party_id = party_row[0]

                    # Get first member of the party
                    first_member = session.execute(text("""
                        SELECT character_id FROM party_memberships
                        WHERE party_id = :party_id
                        ORDER BY joined_at ASC
                        LIMIT 1
                    """), {'party_id': party_id}).fetchone()

                    if first_member:
                        character_id = first_member[0]
                        print(f"  - Setting party {party_id[:8]}... SW to character {character_id[:8]}...")

                        session.execute(text("""
                            UPDATE parties
                            SET story_weaver_id = :character_id,
                                created_by_id = :character_id
                            WHERE id = :party_id
                        """), {
                            'character_id': character_id,
                            'party_id': party_id
                        })
                session.commit()
                print(f"  - Backfilled {len(parties)} parties")
            else:
                print("  - No parties need backfilling")
        else:
            print("  - Skipping backfill (tables not ready)")

        print("\n✅ Migration 001 completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        session.rollback()
        raise

    finally:
        session.close()


def rollback_migration():
    """Rollback the migration (for development)."""
    print(f"Rolling back migration 001")
    print(f"Database: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Drop tables in reverse order
        if table_exists(engine, 'combat_turns'):
            print("  - Dropping combat_turns table")
            session.execute(text("DROP TABLE combat_turns"))
            session.commit()

        if table_exists(engine, 'npcs'):
            print("  - Dropping npcs table")
            session.execute(text("DROP TABLE npcs"))
            session.commit()

        # Remove columns from parties (SQLite doesn't support DROP COLUMN easily)
        # For PostgreSQL:
        if 'postgresql' in DATABASE_URL:
            if column_exists(engine, 'parties', 'story_weaver_id'):
                print("  - Removing story_weaver_id column")
                session.execute(text("ALTER TABLE parties DROP COLUMN story_weaver_id"))
                session.commit()

            if column_exists(engine, 'parties', 'created_by_id'):
                print("  - Removing created_by_id column")
                session.execute(text("ALTER TABLE parties DROP COLUMN created_by_id"))
                session.commit()
        else:
            print("  ⚠️  SQLite detected - cannot easily drop columns. Manual cleanup required.")

        print("\n✅ Rollback completed!")

    except Exception as e:
        print(f"\n❌ Rollback failed: {e}")
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    import sys
    print("=" * 60, file=sys.stderr, flush=True)
    print("🔧 MIGRATION SCRIPT EXECUTING", file=sys.stderr, flush=True)
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...", file=sys.stderr, flush=True)
    print("=" * 60, file=sys.stderr, flush=True)
    
    try:
        run_migration()
        print("=" * 60, file=sys.stderr, flush=True)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY", file=sys.stderr, flush=True)
        print("=" * 60, file=sys.stderr, flush=True)
    except Exception as e:
        print("=" * 60, file=sys.stderr, flush=True)
        print(f"❌ MIGRATION FAILED: {e}", file=sys.stderr, flush=True)
        print("=" * 60, file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)  # Explicit failure - stops deployment
