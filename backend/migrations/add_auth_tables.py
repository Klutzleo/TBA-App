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
        # Step 1: Create users table
        print("\n[1/6] Creating users table...")
        if not table_exists(engine, 'users'):
            print("  - Creating users table")
            session.execute(text("""
                CREATE TABLE users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR NOT NULL UNIQUE,
                    username VARCHAR NOT NULL UNIQUE,
                    hashed_password VARCHAR NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """))
            session.execute(text("CREATE INDEX ix_users_id ON users(id)"))
            session.execute(text("CREATE INDEX ix_users_email ON users(email)"))
            session.execute(text("CREATE INDEX ix_users_username ON users(username)"))
            session.commit()
            print("  - users table created successfully")
        else:
            print("  - users table already exists")

        # Step 2: Create password_reset_tokens table
        print("\n[2/6] Creating password_reset_tokens table...")
        if not table_exists(engine, 'password_reset_tokens'):
            print("  - Creating password_reset_tokens table")
            session.execute(text("""
                CREATE TABLE password_reset_tokens (
                    id VARCHAR PRIMARY KEY,
                    token VARCHAR NOT NULL UNIQUE,
                    user_id VARCHAR NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """))
            session.execute(text("CREATE INDEX ix_password_reset_tokens_id ON password_reset_tokens(id)"))
            session.execute(text("CREATE INDEX ix_password_reset_tokens_token ON password_reset_tokens(token)"))
            session.execute(text("CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens(user_id)"))
            session.commit()
            print("  - password_reset_tokens table created successfully")
        else:
            print("  - password_reset_tokens table already exists")

        # Step 3: Create system user for existing data
        print("\n[3/6] Creating system user...")
        system_user_id = str(uuid.uuid4())
        system_email = "system@tba-app.local"

        # Check if system user already exists
        existing_user = session.execute(text("""
            SELECT id FROM users WHERE email = :email
        """), {'email': system_email}).fetchone()

        if existing_user:
            system_user_id = existing_user[0]
            print(f"  - System user already exists (id: {system_user_id[:8]}...)")
        else:
            print(f"  - Creating system user (email: {system_email})")
            # Generate a secure random password hash for the system user
            # User will never log in with this account, it's just for data ownership
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            system_password_hash = pwd_context.hash(str(uuid.uuid4()))

            session.execute(text("""
                INSERT INTO users (id, email, username, hashed_password, is_active, created_at, updated_at)
                VALUES (:id, :email, :username, :password, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                'id': system_user_id,
                'email': system_email,
                'username': 'system',
                'password': system_password_hash
            })
            session.commit()
            print(f"  - System user created (id: {system_user_id[:8]}...)")

        # Step 4: Add user_id to characters table
        print("\n[4/6] Adding user_id to characters table...")
        if table_exists(engine, 'characters'):
            if not column_exists(engine, 'characters', 'user_id'):
                print("  - Adding user_id column")
                session.execute(text("""
                    ALTER TABLE characters
                    ADD COLUMN user_id VARCHAR
                """))
                session.commit()

                # Backfill existing characters with system user
                print(f"  - Backfilling existing characters with system user")
                session.execute(text("""
                    UPDATE characters
                    SET user_id = :system_user_id
                    WHERE user_id IS NULL
                """), {'system_user_id': system_user_id})
                session.commit()

                # Make column NOT NULL after backfill
                print("  - Making user_id NOT NULL")
                session.execute(text("""
                    ALTER TABLE characters
                    ALTER COLUMN user_id SET NOT NULL
                """))

                # Add foreign key constraint
                print("  - Adding foreign key constraint")
                session.execute(text("""
                    ALTER TABLE characters
                    ADD CONSTRAINT fk_characters_user_id
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                """))

                # Add index
                session.execute(text("CREATE INDEX ix_characters_user_id ON characters(user_id)"))
                session.commit()
                print("  - user_id column added successfully")
            else:
                print("  - user_id column already exists")
        else:
            print("  - characters table doesn't exist yet")

        # Step 5: Update campaigns table foreign keys
        print("\n[5/6] Updating campaigns table foreign keys...")
        if table_exists(engine, 'campaigns'):
            # Update created_by_id to reference users
            if column_exists(engine, 'campaigns', 'created_by_id'):
                print("  - Updating created_by_id to reference users table")

                # Backfill with system user
                session.execute(text("""
                    UPDATE campaigns
                    SET created_by_id = :system_user_id
                    WHERE created_by_id IS NULL OR created_by_id NOT IN (SELECT id FROM users)
                """), {'system_user_id': system_user_id})
                session.commit()

                # Drop old constraint if it exists
                fk_name = get_constraint_name(engine, 'campaigns', 'created_by_id')
                if fk_name:
                    print(f"  - Dropping old constraint {fk_name}")
                    session.execute(text(f"ALTER TABLE campaigns DROP CONSTRAINT {fk_name}"))
                    session.commit()

                # Add new constraint to users table
                print("  - Adding foreign key to users table")
                session.execute(text("""
                    ALTER TABLE campaigns
                    ADD CONSTRAINT fk_campaigns_created_by_user_id
                    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                session.commit()

            # Handle story_weaver_id rename and update
            if column_exists(engine, 'campaigns', 'story_weaver_id'):
                print("  - Updating story_weaver_id to reference users table")

                # Drop old constraint if it exists (referenced characters.id)
                fk_name = get_constraint_name(engine, 'campaigns', 'story_weaver_id')
                if fk_name:
                    print(f"  - Dropping old constraint {fk_name}")
                    session.execute(text(f"ALTER TABLE campaigns DROP CONSTRAINT {fk_name}"))
                    session.commit()

                # Backfill with system user
                session.execute(text("""
                    UPDATE campaigns
                    SET story_weaver_id = :system_user_id
                    WHERE story_weaver_id IS NULL OR story_weaver_id NOT IN (SELECT id FROM users)
                """), {'system_user_id': system_user_id})
                session.commit()

                # Make NOT NULL
                session.execute(text("""
                    ALTER TABLE campaigns
                    ALTER COLUMN story_weaver_id SET NOT NULL
                """))

                # Add new constraint to users table
                print("  - Adding foreign key to users table")
                session.execute(text("""
                    ALTER TABLE campaigns
                    ADD CONSTRAINT fk_campaigns_story_weaver_id
                    FOREIGN KEY (story_weaver_id) REFERENCES users(id) ON DELETE CASCADE
                """))
                session.commit()

            # Rename created_by_id to created_by_user_id if needed
            if column_exists(engine, 'campaigns', 'created_by_id') and not column_exists(engine, 'campaigns', 'created_by_user_id'):
                print("  - Renaming created_by_id to created_by_user_id")
                session.execute(text("""
                    ALTER TABLE campaigns
                    RENAME COLUMN created_by_id TO created_by_user_id
                """))
                session.commit()

            print("  - campaigns table updated successfully")
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
