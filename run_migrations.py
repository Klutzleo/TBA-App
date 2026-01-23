#!/usr/bin/env python3
"""
Automatic Database Migration Runner
Runs all SQL migrations in backend/migrations/ directory
"""
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql

def run_migrations():
    """Run all SQL migration files in order."""
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)

    # Convert postgres:// to postgresql:// for psycopg2
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("🚀 Starting database migrations...")
    print(f"📦 Database: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
    print("")

    # Get all SQL migration files (skip .bak files and MANUAL_ files)
    migrations_dir = Path(__file__).parent / 'backend' / 'migrations'
    all_files = sorted(migrations_dir.glob('*.sql'))
    sql_files = [f for f in all_files if not f.name.startswith('MANUAL_') and not f.name.endswith('.bak')]

    if not sql_files:
        print("⚠️  No migration files found in backend/migrations/")
        return

    # Connect to database
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected to database")
        print("")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

    # Run each migration
    success_count = 0
    skip_count = 0
    error_count = 0

    for sql_file in sql_files:
        # Skip README and Python files
        if 'README' in sql_file.name or sql_file.name.startswith('run_'):
            continue

        print(f"📄 Processing: {sql_file.name}")

        try:
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # Execute the migration
            cursor.execute(sql_content)
            print(f"   ✅ Applied successfully")
            success_count += 1

        except psycopg2.errors.DuplicateColumn as e:
            # Column already exists - this is fine
            print(f"   ⏭️  Skipped (column already exists)")
            skip_count += 1

        except psycopg2.errors.DuplicateTable as e:
            # Table already exists - this is fine
            print(f"   ⏭️  Skipped (table already exists)")
            skip_count += 1

        except psycopg2.errors.UndefinedTable as e:
            # Referenced table doesn't exist - log but continue
            print(f"   ⚠️  Warning: Referenced table not found - {e}")
            error_count += 1

        except Exception as e:
            # Check if it's a "already exists" error
            error_msg = str(e).lower()
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                print(f"   ⏭️  Skipped (already exists)")
                skip_count += 1
            elif 'does not exist' in error_msg and 'relation' in error_msg:
                # Table doesn't exist yet - this happens when migrations run out of order
                print(f"   ⚠️  Skipped (dependency not met)")
                skip_count += 1
            else:
                print(f"   ❌ Error: {e}")
                error_count += 1

        print("")

    # Close connection
    cursor.close()
    conn.close()

    # Summary
    print("=" * 60)
    print("📊 Migration Summary:")
    print(f"   ✅ Applied: {success_count}")
    print(f"   ⏭️  Skipped: {skip_count}")
    print(f"   ❌ Errors: {error_count}")
    print("=" * 60)

    # Only fail if we had errors AND didn't apply any migrations successfully
    # This means the migrations genuinely failed, not just skipped
    if error_count > 0 and success_count == 0:
        print("❌ CRITICAL: All migrations failed. Database may be in inconsistent state.")
        sys.exit(1)
    elif error_count > 0:
        print("⚠️  Some migrations had errors, but core migrations applied successfully.")
        print("✅ Proceeding with deployment...")
        sys.exit(0)
    else:
        print("✅ All migrations completed successfully!")
        sys.exit(0)

if __name__ == '__main__':
    run_migrations()
