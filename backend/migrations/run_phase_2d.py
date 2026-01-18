"""
Phase 2d Migration Runner
Auto-runs SQL migrations on startup if needed.
"""

import logging
import os
from pathlib import Path
from sqlalchemy import text, inspect
from backend.db import engine

logger = logging.getLogger(__name__)

def check_migration_needed() -> bool:
    """
    Check if Phase 2d migrations have already been run.
    Returns True if migrations are needed, False if already applied.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Check if new tables exist
    if 'parties' in tables and 'party_members' in tables and 'abilities' in tables:
        # Tables exist, check if characters has new columns
        columns = {col['name'] for col in inspector.get_columns('characters')}
        if 'notes' in columns and 'status' in columns:
            logger.info("✅ Phase 2d migrations already applied")
            return False

    logger.info("🔄 Phase 2d migrations needed")
    return True


def run_sql_migration(filepath: Path, conn):
    """
    Execute a single SQL migration file.
    Handles multi-statement files and comments.
    """
    logger.info(f"Running {filepath.name}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split by semicolons and execute each statement
    statements = []
    current_stmt = []

    for line in sql.split('\n'):
        # Skip comment-only lines
        if line.strip().startswith('--'):
            continue

        current_stmt.append(line)

        # Check if line ends with semicolon (end of statement)
        if line.strip().endswith(';'):
            stmt = '\n'.join(current_stmt).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current_stmt = []

    # Execute each statement
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception as e:
            # Log warning but continue (might be "column already exists" etc.)
            logger.warning(f"Migration statement warning: {e}")
            logger.debug(f"Statement: {stmt[:100]}...")
            conn.rollback()

    logger.info(f"✓ {filepath.name} completed")


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

                run_sql_migration(filepath, conn)

        logger.info("✅ All Phase 2d migrations completed successfully!")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == '__main__':
    # Can be run standalone for testing
    logging.basicConfig(level=logging.INFO)
    run_migrations()
