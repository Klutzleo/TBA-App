"""
backend/notification_center.py
In-app notification center — drives the drawer and toast popups.

Separate from notifications.py which handles Web Push (browser push via VAPID).

Every call to create_notification() produces one DB row that drives two things:
  - The drawer  — persistent, grouped, always accessible on any page
  - The toast   — ephemeral popup fired live (unless silent=True)

Pass silent=True for the retroactive achievement sweep so the drawer
fills up without triggering toast spam on next login.
"""
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_RECENT = 50  # max non-permanent notifications kept per user


def create_notification(
    db: Session,
    user_id,
    type: str,
    title: str,
    body: str = None,
    icon: str = "bell",
    data: dict = None,
    is_permanent: bool = False,
    shame: bool = False,
    silent: bool = False,
    commit: bool = False,
):
    """
    Create a notification row. Returns the Notification or None on error.

    silent=True  — row created, no toast fired (retroactive sweep mode)
    commit=True  — commit immediately (use False when batching with other writes)
    """
    from backend.models import Notification

    try:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            icon=icon,
            data=data or {},
            is_permanent=is_permanent,
            shame=shame,
            silent=silent,
        )
        db.add(notif)

        if not is_permanent:
            _trim_recent(db, user_id)

        if commit:
            db.commit()

        return notif
    except Exception as e:
        logger.warning(f"create_notification failed for user {user_id}: {e}")
        return None


def notify_achievement(
    db: Session,
    user_id,
    achievement_id: str,
    silent: bool = False,
):
    """
    Create a notification row for a newly earned achievement.
    Permanent for: prestige difficulty, founding category, narrative category.
    Shame section routes to Hall of Shame.
    """
    from backend.achievements import ACHIEVEMENTS

    meta = ACHIEVEMENTS.get(achievement_id)
    if not meta:
        return

    category  = meta.get("category", "standard")
    difficulty = meta.get("difficulty")
    is_permanent = (
        category in ("founding", "narrative")
        or difficulty == "prestige"
    )
    is_shame = category == "shame"

    create_notification(
        db=db,
        user_id=user_id,
        type="achievement",
        title=meta["name"],
        body=meta.get("description", ""),
        icon=meta.get("icon", "award"),
        data={
            "achievement_id": achievement_id,
            "points": meta["points"],
            "section": meta["section"],
            "category": category,
            "difficulty": difficulty,
        },
        is_permanent=is_permanent,
        shame=is_shame,
        silent=silent,
    )


def _trim_recent(db: Session, user_id):
    """Keep only the MAX_RECENT most recent non-permanent notifications per user."""
    from backend.models import Notification
    from sqlalchemy import func

    try:
        count = (
            db.query(func.count(Notification.id))
            .filter(
                Notification.user_id == user_id,
                Notification.is_permanent == False,
            )
            .scalar()
        )
        if count >= MAX_RECENT:
            oldest = (
                db.query(Notification.id)
                .filter(
                    Notification.user_id == user_id,
                    Notification.is_permanent == False,
                )
                .order_by(Notification.created_at.asc())
                .limit(count - MAX_RECENT + 1)
                .subquery()
            )
            db.query(Notification).filter(
                Notification.id.in_(oldest)
            ).delete(synchronize_session=False)
    except Exception as e:
        logger.warning(f"_trim_recent failed: {e}")
