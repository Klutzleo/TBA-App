"""
scripts/achievement_sweep.py
One-time retroactive achievement sweep.

Evaluates every user against all achievement conditions and awards
anything they've already earned. Notifications are created with
silent=True so no toasts fire — players discover them by opening
the scroll drawer.

Run on Railway:
    python scripts/achievement_sweep.py

Run with --dry-run to see what would be awarded without writing anything:
    python scripts/achievement_sweep.py --dry-run
"""
import sys
import os
import argparse
import logging
from datetime import datetime

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run_sweep(dry_run=False):
    from backend.db import SessionLocal
    from backend.models import User
    from backend.achievements import check_and_award

    db = SessionLocal()

    try:
        users = db.query(User).filter(User.is_active == True).all()
        log.info(f"Found {len(users)} active users")

        total_awarded = 0
        results = []

        for i, user in enumerate(users, 1):
            try:
                if dry_run:
                    # Peek at what would be awarded without committing
                    newly = _dry_run_check(user.id, db)
                else:
                    newly = check_and_award(user.id, db, silent=True)

                if newly:
                    total_awarded += len(newly)
                    results.append((user.username, newly))
                    log.info(f"[{i}/{len(users)}] {user.username}: +{len(newly)} — {', '.join(newly)}")
                else:
                    log.info(f"[{i}/{len(users)}] {user.username}: nothing new")

            except Exception as e:
                log.warning(f"[{i}/{len(users)}] {user.username}: ERROR — {e}")
                db.rollback()

        log.info("─" * 60)
        log.info(f"Sweep complete — {total_awarded} achievements awarded across {len(results)} users")
        if dry_run:
            log.info("DRY RUN — nothing was written to the database")

        return results

    finally:
        db.close()


def _dry_run_check(user_id, db):
    """
    Peek at what check_and_award would return without writing anything.
    Opens a savepoint, runs the check, then rolls back.
    """
    from backend.achievements import check_and_award
    try:
        db.begin_nested()  # savepoint
        newly = check_and_award(user_id, db, silent=True)
        db.rollback()      # roll back the savepoint — nothing persisted
        return newly
    except Exception:
        db.rollback()
        return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retroactive achievement sweep")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.dry_run:
        log.info("DRY RUN MODE — previewing awards, nothing will be saved")
    else:
        log.info("LIVE MODE — awards will be written and notifications created (silent)")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            log.info("Aborted.")
            sys.exit(0)

    start = datetime.now()
    run_sweep(dry_run=args.dry_run)
    elapsed = (datetime.now() - start).total_seconds()
    log.info(f"Done in {elapsed:.1f}s")
