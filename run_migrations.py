#!/usr/bin/env python3
"""
Automatic Database Migration Runner
Runs all SQL migrations in backend/migrations/ directory.
Tracks applied migrations in schema_migrations table so each file
runs exactly once — already-applied migrations are fully skipped
(no locks acquired), preventing deadlocks during rolling deploys.
"""
import os
import sys
import time
from pathlib import Path
import psycopg2

def run_migrations():
    """Run all SQL migration files in order."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("🚀 Starting database migrations...")
    print(f"📦 Database: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
    print("")

    migrations_dir = Path(__file__).parent / 'backend' / 'migrations'
    all_files = sorted(migrations_dir.glob('*.sql'))
    sql_files = [f for f in all_files if not f.name.startswith('MANUAL_') and not f.name.endswith('.bak')]

    if not sql_files:
        print("⚠️  No migration files found in backend/migrations/")
        return

    # Postgres may still be mid-restart/crash-recovery (e.g. after a Railway maintenance
    # update) — retry the initial connection instead of failing immediately, so the app
    # comes back up on its own once the DB is ready instead of needing a manual restart.
    max_wait_seconds = 120
    retry_interval_seconds = 3
    deadline = time.monotonic() + max_wait_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            conn = psycopg2.connect(database_url, connect_timeout=5)
            conn.autocommit = True
            cursor = conn.cursor()
            print(f"✅ Connected to database (attempt {attempt})")
            print("")
            break
        except Exception as e:
            if time.monotonic() >= deadline:
                print(f"❌ Failed to connect to database after {attempt} attempts over {max_wait_seconds}s: {e}")
                sys.exit(1)
            print(f"⏳ Database not ready yet (attempt {attempt}): {e}")
            print(f"   Retrying in {retry_interval_seconds}s...")
            time.sleep(retry_interval_seconds)

    # Serialize concurrent migration runs (e.g. two Railway dynos starting simultaneously).
    # pg_advisory_lock blocks until free; released automatically when connection closes.
    print("🔒 Acquiring migration advisory lock...")
    cursor.execute("SELECT pg_advisory_lock(20260317)")
    print("✅ Lock acquired")
    print("")

    # Create migration tracking table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Fetch already-applied migrations
    cursor.execute("SELECT filename FROM schema_migrations")
    applied = {row[0] for row in cursor.fetchall()}

    success_count = 0
    skip_count = 0
    error_count = 0

    for sql_file in sql_files:
        if 'README' in sql_file.name or sql_file.name.startswith('run_'):
            continue

        if sql_file.name in applied:
            print(f"⏭️  Already applied: {sql_file.name}")
            skip_count += 1
            continue

        print(f"📄 Applying: {sql_file.name}")

        try:
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            cursor.execute(sql_content)
            cursor.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (sql_file.name,)
            )
            print(f"   ✅ Applied successfully")
            success_count += 1

        except Exception as e:
            try: conn.rollback()
            except: pass
            error_msg = str(e).lower()
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                print(f"   ⏭️  Skipped (already exists)")
                # Still record it so we don't retry every deploy
                try:
                    cursor.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                        (sql_file.name,)
                    )
                except: pass
                skip_count += 1
            elif 'does not exist' in error_msg and 'relation' in error_msg:
                print(f"   ⚠️  Skipped (dependency not met): {e}")
                skip_count += 1
            else:
                print(f"   ❌ Error: {e}")
                error_count += 1

        print("")

    cursor.close()
    conn.close()

    print("=" * 60)
    print("📊 Migration Summary:")
    print(f"   ✅ Applied: {success_count}")
    print(f"   ⏭️  Skipped: {skip_count}")
    print(f"   ❌ Errors: {error_count}")
    print("=" * 60)

    if error_count > 0 and success_count == 0 and skip_count == 0:
        print("❌ CRITICAL: All migrations failed.")
        sys.exit(1)
    elif error_count > 0:
        print("⚠️  Some migrations had errors, but proceeding with deployment...")
        sys.exit(0)
    else:
        print("✅ All migrations completed successfully!")
        sys.exit(0)

if __name__ == '__main__':
    run_migrations()
