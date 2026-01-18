"""
Phase 2d Migration Runner (PostgreSQL)
Auto-runs SQL migrations on startup if needed.
"""

import logging
import os
from pathlib import Path
from sqlalchemy import text, inspect
from backend.db import engine

logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = {col['name'] for col in inspector.get_columns(table_name)}
    return column_name in columns


def check_migration_needed() -> bool:
    """
    Check if Phase 2d migrations have already been run.
    Returns True if migrations are needed, False if already applied.
    """
    # Check if new tables exist
    if table_exists('parties') and table_exists('party_members') and table_exists('abilities'):
        # Tables exist, check if characters has new columns
        if column_exists('characters', 'notes') and column_exists('characters', 'status'):
            logger.info("✅ Phase 2d migrations already applied")
            return False

    logger.info("🔄 Phase 2d migrations needed")
    return True


def run_sql_file(filepath: Path, conn):
    """
    Execute a single SQL migration file.
    Handles multi-statement files including DO blocks.
    """
    logger.info(f"Running {filepath.name}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # For PostgreSQL, we can execute the entire file as one transaction
    # But we need to handle DO blocks specially

    # Split on semicolons that are NOT inside DO blocks
    # Simple approach: execute the whole file
    try:
        conn.execute(text(sql_content))
        conn.commit()
        logger.info(f"✓ {filepath.name} completed")
    except Exception as e:
        logger.warning(f"⚠️ {filepath.name} warning: {e}")
        conn.rollback()

        # Try statement-by-statement for better error handling
        logger.info(f"  Retrying {filepath.name} statement-by-statement...")
        run_sql_statements(sql_content, conn, filepath.name)


def run_sql_statements(sql_content: str, conn, filename: str):
    """
    Execute SQL content statement by statement.
    Handles DO blocks and regular statements.
    """
    # Split into statements, being careful with DO blocks
    statements = []
    current = []
    in_do_block = False

    for line in sql_content.split('\n'):
        stripped = line.strip()

        # Track DO block state
        if stripped.upper().startswith('DO $$') or stripped.upper().startswith('DO $'):
            in_do_block = True

        current.append(line)

        # Check for end of DO block
        if in_do_block and stripped.endswith('$$;'):
            in_do_block = False
            statements.append('\n'.join(current))
            current = []
        # Check for regular statement end (not in DO block)
        elif not in_do_block and stripped.endswith(';') and not stripped.startswith('--'):
            stmt = '\n'.join(current).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current = []

    # Execute each statement
    success_count = 0
    for stmt in statements:
        if not stmt.strip() or stmt.strip().startswith('--'):
            continue
        try:
            conn.execute(text(stmt))
            conn.commit()
            success_count += 1
        except Exception as e:
            error_msg = str(e).lower()
            # Ignore "already exists" errors
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                logger.debug(f"  Skipping (already exists): {stmt[:50]}...")
            else:
                logger.warning(f"  Statement warning: {e}")
            conn.rollback()

    logger.info(f"✓ {filename} completed ({success_count} statements)")


def run_migrations():
    """
    Run Phase 2d migrations in order.
    Safe to run multiple times (idempotent).
    """
    logger.info("🔧 Checking Phase 2d migrations...")

    # Check if migrations are needed
    if not check_migration_needed():
        return

    migration_files = [
        '001_add_parties.sql',
        '002_add_party_members.sql',
        '003_update_characters.sql',
        '004_add_abilities.sql',
        '005_update_messages.sql'
    ]

    migrations_dir = Path(__file__).parent

    try:
        with engine.connect() as conn:
            for filename in migration_files:
                filepath = migrations_dir / filename

                if not filepath.exists():
                    logger.error(f"❌ Migration file not found: {filename}")
                    continue

                run_sql_file(filepath, conn)

        logger.info("✅ All Phase 2d migrations completed successfully!")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def run_cleanup():
    """
    Run cleanup script to remove failed migration artifacts.
    Use this if migrations failed partway through.
    """
    logger.info("🧹 Running cleanup for failed migrations...")

    migrations_dir = Path(__file__).parent
    cleanup_file = migrations_dir / '000_cleanup_failed_migration.sql'

    if not cleanup_file.exists():
        logger.error("❌ Cleanup file not found")
        return

    try:
        with engine.connect() as conn:
            run_sql_file(cleanup_file, conn)
        logger.info("✅ Cleanup completed!")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == '--cleanup':
        run_cleanup()
    else:
        run_migrations()
