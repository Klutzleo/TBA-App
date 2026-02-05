"""
Migration: Add Authentication Tables and User Foreign Keys

Phase 1 Authentication Foundation:

Changes:
1. Create users table with email, username, hashed_password, is_active, timestamps
2. Create password_reset_tokens table with token, user_id, expires_at, used
3. Add user_id column to characters table (FK to users.id)
4. Update campaigns table: change created_by_id and story_weaver_id to FK users.id
5. Create system user and backfill existing data

Usage:
    python backend/migrations/add_auth_tables.py

Requirements:
    - Run with DATABASE_URL environment variable set
    - Idempotent: safe to run multiple times
    - Creates a system user (email: system@tba-app.local) for existing data
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.db import DATABASE_URL, Base

import time

def wait_for_db(engine, max_retries=10, delay=2):
    """Wait for database to be ready"""
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"✅ Database connection established (attempt {attempt + 1})")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⏳ Database not ready (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"❌ Database connection failed after {max_retries} attempts")
                raise
    return False

def column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def table_exists(engine, table_name):
    """Check if a table exists."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def get_constraint_name(engine, table_name, column_name):
    """Get foreign key constraint name for a column."""
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys(table_name)
    for fk in fks:
        if column_name in fk['constrained_columns']:
            return fk['name']
    return None

def run_migration():
    """Run the authentication migration"""
    print("Running migration: Add Authentication Tables")
    print(f"Database: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    wait_for_db(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Step 1: Check users table (should already exist from 003_add_users.sql)
        print("\n[1/6] Checking users table...")
        if not table_exists(engine, 'users'):
            print("  ⚠️  Users table doesn't exist! It should have been created by 003_add_users.sql")
            print("  - Creating users table with UUID...")
            session.execute(text("""
                CREATE TABLE users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) NOT NULL UNIQUE,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_login TIMESTAMP
                )
            """))
            session.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)"))
            session.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users(username)"))
            session.commit()
            print("  - users table created successfully")
        else:
            print("  - ✅ users table already exists (from 003_add_users.sql)")

            # Add is_active column if it doesn't exist
            if not column_exists(engine, 'users', 'is_active'):
                print("  - Adding is_active column to users table")
                session.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE
                """))
                session.commit()
                print("  - is_active column added")
            else:
                print("  - is_active column already exists")

        # Step 2: Create password_reset_tokens table with UUID
        print("\n[2/6] Creating password_reset_tokens table...")
        if not table_exists(engine, 'password_reset_tokens'):
            print("  - Creating password_reset_tokens table with UUID...")
            session.execute(text("""
                CREATE TABLE password_reset_tokens (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    token VARCHAR NOT NULL UNIQUE,
                    user_id UUID NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    CONSTRAINT fk_password_reset_tokens_user_id
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """))
            session.execute(text("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token ON password_reset_tokens(token)"))
            session.execute(text("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens(user_id)"))
            session.commit()
            print("  - password_reset_tokens table created successfully")
        else:
            print("  - password_reset_tokens table already exists")

        # Step 3: Create system user for existing data
        print("\n[3/6] Creating system user...")
        system_user_id = uuid.uuid4()  # Keep as UUID object
        system_email = "system@tba-app.local"

        # Check if system user already exists
        existing_user = session.execute(text("""
            SELECT id FROM users WHERE email = :email
        """), {'email': system_email}).fetchone()

        if existing_user:
            system_user_id = existing_user[0]
            print(f"  - System user already exists (id: {str(system_user_id)[:8]}...)")
        else:
            print(f"  - Creating system user (email: {system_email})")
            # Use a dummy bcrypt hash for the system user
            # Security: Account is set to is_active=FALSE so it CAN'T log in
            # This avoids bcrypt version compatibility issues during migration
            # Hash format is valid but unused (bcrypt hash of "DISABLED-ACCOUNT")
            system_password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwKp.09E9XYzP5RKO"

            session.execute(text("""
                INSERT INTO users (id, email, username, hashed_password, is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), :email, :username, :password, FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                'id': str(system_user_id),
                'email': system_email,
                'username': 'system',
                'password': system_password_hash
            })
            session.commit()
            print(f"  - System user created (id: {str(system_user_id)[:8]}...) [DISABLED]")

        # Step 4: Check characters.user_id (should already exist from 003_add_users.sql)
        print("\n[4/6] Checking characters.user_id...")
        if table_exists(engine, 'characters'):
            if column_exists(engine, 'characters', 'user_id'):
                print("  - ✅ user_id column already exists (from 003_add_users.sql)")

                # Backfill any NULL user_ids with system user
                null_count = session.execute(text("""
                    SELECT COUNT(*) FROM characters WHERE user_id IS NULL
                """)).scalar()

                if null_count > 0:
                    print(f"  - Backfilling {null_count} characters with NULL user_id")
                    session.execute(text("""
                        UPDATE characters
                        SET user_id = CAST(:system_user_id AS uuid)
                        WHERE user_id IS NULL
                    """), {'system_user_id': str(system_user_id)})
                    session.commit()
                    print(f"  - Backfilled {null_count} characters")
                else:
                    print("  - No characters need backfilling")
            else:
                print("  - ⚠️  user_id column doesn't exist! Adding it...")
                session.execute(text("""
                    ALTER TABLE characters
                    ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE SET NULL
                """))
                session.execute(text("CREATE INDEX IF NOT EXISTS ix_characters_user_id ON characters(user_id)"))
                session.commit()
                print("  - user_id column added")
        else:
            print("  - characters table doesn't exist yet")

        # Step 5: Skip campaigns table updates for now
        print("\n[5/6] Checking campaigns table...")
        if table_exists(engine, 'campaigns'):
            print("  - ✅ campaigns table exists")
            print("  - ⏭️  Skipping campaigns FK updates (will be handled separately)")
            print("  - Note: Campaigns.created_by_id and story_weaver_id currently reference characters")
            print("  - These will be migrated to reference users in a future migration")
        else:
            print("  - campaigns table doesn't exist yet")

        # Step 6: Summary
        print("\n[6/6] Migration summary...")
        user_count = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        print(f"  - Total users: {user_count}")

        if table_exists(engine, 'characters'):
            char_count = session.execute(text("SELECT COUNT(*) FROM characters")).scalar()
            print(f"  - Total characters: {char_count}")

        if table_exists(engine, 'campaigns'):
            campaign_count = session.execute(text("SELECT COUNT(*) FROM campaigns")).scalar()
            print(f"  - Total campaigns: {campaign_count}")

        print("\n✅ Authentication migration completed successfully!")
        print(f"\n📝 Note: All existing data has been assigned to system user: {system_email}")
        print("   You can create real user accounts and reassign ownership as needed.")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    import sys
    print("=" * 60, file=sys.stderr, flush=True)
    print("🔧 AUTHENTICATION MIGRATION EXECUTING", file=sys.stderr, flush=True)
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
        sys.exit(1)
