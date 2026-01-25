"""
Phase 2d Migration Runner (PostgreSQL)
Auto-runs SQL migrations on startup if needed.
Properly handles PostgreSQL DO blocks and CREATE FUNCTION statements.
"""

import logging
import re
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
    if table_exists('parties') and table_exists('abilities'):
        # Tables exist, check if characters has new columns
        if (column_exists('characters', 'notes') and
            column_exists('characters', 'status') and
            column_exists('party_memberships', 'left_at')):
            logger.info("✅ Phase 2d migrations already applied")
            return False

    logger.info("🔄 Phase 2d migrations needed")
    return True


def split_sql_statements(sql_content: str) -> list:
    """
    Split SQL content into individual statements.
    Properly handles:
    - DO $$ ... END $$; blocks
    - CREATE FUNCTION ... $$ LANGUAGE plpgsql; blocks
    - Regular statements ending with ;
    - Comments
    """
    statements = []
    current = []
    in_dollar_block = False
    dollar_tag = None

    lines = sql_content.split('\n')

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comment-only lines when not in a block
        if not in_dollar_block and (not stripped or stripped.startswith('--')):
            continue

        # Check for start of dollar-quoted block (DO $$, CREATE FUNCTION ... AS $$)
        if not in_dollar_block:
            # Match $$ or $tag$ at start of dollar quoting
            dollar_match = re.search(r'\$(\w*)\$', line)
            if dollar_match:
                in_dollar_block = True
                dollar_tag = dollar_match.group(0)  # e.g., "$$" or "$tag$"
                current.append(line)

                # Check if block ends on same line (e.g., $$ LANGUAGE plpgsql;)
                # Count occurrences of the dollar tag
                occurrences = line.count(dollar_tag)
                if occurrences >= 2:
                    # Block starts and ends on same line
                    in_dollar_block = False
                    if stripped.endswith(';'):
                        statements.append('\n'.join(current))
                        current = []
                continue

        # Inside a dollar-quoted block
        if in_dollar_block:
            current.append(line)
            # Check for end of dollar block
            if dollar_tag and dollar_tag in line:
                # Check if this closes the block (second occurrence)
                in_dollar_block = False
                dollar_tag = None
                if stripped.endswith(';'):
                    statements.append('\n'.join(current))
                    current = []
            continue

        # Regular statement
        current.append(line)
        if stripped.endswith(';'):
            stmt = '\n'.join(current).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current = []

    # Don't forget any remaining content
    if current:
        stmt = '\n'.join(current).strip()
        if stmt and not stmt.startswith('--'):
            statements.append(stmt)

    return statements


def run_sql_file(filepath: Path, conn):
    """
    Execute a single SQL migration file.
    """
    logger.info(f"Running {filepath.name}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split into proper statements
    statements = split_sql_statements(sql_content)

    success_count = 0
    error_count = 0

    for stmt in statements:
        if not stmt.strip():
            continue

        try:
            conn.execute(text(stmt))
            conn.commit()
            success_count += 1
        except Exception as e:
            error_msg = str(e).lower()
            # Ignore "already exists" errors
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                logger.debug(f"  Skipping (already exists)")
                success_count += 1  # Count as success
            else:
                logger.warning(f"  Statement error: {e}")
                error_count += 1
            conn.rollback()

    if error_count > 0:
        logger.warning(f"⚠️ {filepath.name} completed with {error_count} errors ({success_count} succeeded)")
    else:
        logger.info(f"✓ {filepath.name} completed ({success_count} statements)")


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
        '005_update_messages.sql',
        '006_add_left_at_column.sql'
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

        logger.info("✅ All Phase 2d migrations completed!")

        # Verify critical tables were created
        if not table_exists('parties'):
            logger.error("❌ CRITICAL: 'parties' table was not created!")
        if not table_exists('abilities'):
            logger.error("❌ CRITICAL: 'abilities' table was not created!")
        if not table_exists('party_members'):
            logger.error("❌ CRITICAL: 'party_members' table was not created!")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def run_cleanup():
    """
    Run cleanup script to remove failed migration artifacts.
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
