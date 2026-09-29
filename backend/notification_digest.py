"""
backend/notification_digest.py
Twice-daily email digest for 'your turn' / '@mention' notifications the recipient
hasn't seen yet. Piggybacks on the Notification rows already created by
backend/notification_center.py (notify_turn / notify_mention) — this module only
decides which of those rows are still worth emailing, and sends them.

Deliberately conservative, so it never turns into something annoying:
  - At most 2 emails/day per user, by construction (one per window, bundled).
  - Skips anyone currently WebSocket-connected right now — they're already looking at it.
  - Skips anything the user has plausibly already seen (logged in since it fired).
  - Drops anything older than STALE_AFTER_DAYS — a week-old "your turn" ping is more
    confusing than useful.
  - Re-validates 'your turn' against live encounter state right before sending — the
    turn may have moved on since the notification was created. Mentions don't need
    this; a mention stays true forever, so only 'turn' gets revalidated.
  - Respects UserProfile.email_notifications_enabled (default True), which the
    one-click unsubscribe link flips off.

Same background-worker shape as backend/discord_mirror.py: start_workers()/stop_workers()
called from backend/app.py's lifespan.
"""
import asyncio
import html
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.db import SessionLocal

logger = logging.getLogger(__name__)

DIGEST_TIMEZONE = os.getenv("DIGEST_TIMEZONE", "America/New_York")
DIGEST_HOURS = (9, 18)   # local wall-clock hours the sweep fires at
STALE_AFTER_DAYS = 2     # never email about something older than this

_task = None
_stopping = False


# ============================================================================
# Pure helpers — no DB/network, kept separate so they're directly unit-testable
# ============================================================================

def next_digest_datetime(now: datetime, tz_name: str = DIGEST_TIMEZONE, hours=DIGEST_HOURS) -> datetime:
    """Next wall-clock digest time (timezone-aware), strictly after `now` (also aware)."""
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    candidates = []
    for day_offset in (0, 1):
        day = local_now.date() + timedelta(days=day_offset)
        for hour in hours:
            candidates.append(datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=tz))
    return min(c for c in candidates if c > local_now)


def _naive_utc(dt: datetime) -> datetime:
    """Normalize a possibly-tz-aware datetime to naive UTC, matching the naive-UTC
    convention the rest of this codebase uses (User.last_login, datetime.utcnow()
    defaults throughout). Notification.created_at is DateTime(timezone=True) —
    Postgres returns that as tz-aware, which raises TypeError against a naive
    datetime in a direct Python comparison/subtraction. SQLite does NOT return
    tz-aware datetimes for the same column type, which is why this mismatch
    doesn't show up under the SQLite-backed test suite — normalize defensively
    here rather than relying on callers to always pass matching types."""
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def is_stale(now: datetime, created_at: datetime, max_age_days: int = STALE_AFTER_DAYS) -> bool:
    return (_naive_utc(now) - _naive_utc(created_at)) > timedelta(days=max_age_days)


def already_seen(created_at: datetime, last_login) -> bool:
    """True if the user logged in at/after the event fired — they've almost certainly
    already seen it in-app, so there's no need to also email it."""
    if not last_login:
        return False
    return _naive_utc(last_login) >= _naive_utc(created_at)


def relative_time_phrase(now: datetime, dt: datetime) -> str:
    """Real-elapsed-time phrasing for the email. Deliberately NOT narrative/in-game
    time — there's no in-game calendar tracked anywhere in the app, so 'last night'
    would only ever describe the real world, which is what this does directly.

    Based on calendar-day difference plus the actual time of day the event happened,
    not just elapsed hours — a message from yesterday at noon isn't "last night"
    just because it's under 24 hours old."""
    now = _naive_utc(now)
    dt = _naive_utc(dt)
    minutes = (now - dt).total_seconds() / 60
    if minutes < 60:
        return "a few minutes ago"
    days_ago = (now.date() - dt.date()).days
    if days_ago <= 0:
        hours = int(minutes / 60)
        return f"about {hours} hour{'s' if hours != 1 else ''} ago" if hours < 6 else "earlier today"
    if days_ago == 1:
        return "last night" if dt.hour >= 17 else "yesterday"
    return f"{days_ago} days ago"


# ============================================================================
# Live revalidation
# ============================================================================

def revalidate_turn(db, data: dict) -> bool:
    """Re-check a stored 'your turn' notification is still actually true right now.
    Other players/the SW may have moved on while the recipient was away."""
    from backend.models import Encounter, InitiativeRoll
    from routes.campaign_websocket import _sort_initiative_rolls

    encounter_id = data.get("encounter_id")
    character_id = data.get("character_id")
    if not encounter_id or not character_id:
        return False

    encounter = db.query(Encounter).filter(
        Encounter.id == encounter_id, Encounter.is_active == True  # noqa: E712
    ).first()
    if not encounter:
        return False

    rolls = db.query(InitiativeRoll).filter(
        InitiativeRoll.encounter_id == encounter.id,
        InitiativeRoll.is_silent == False,  # noqa: E712
    ).all()
    if not rolls:
        return False
    rolls = _sort_initiative_rolls(rolls, db)
    if encounter.current_turn_index >= len(rolls):
        return False
    return str(rolls[encounter.current_turn_index].character_id) == str(character_id)


def _connected_user_ids() -> set:
    from routes.campaign_websocket import manager
    ids = set()
    for conns in manager.active_connections.values():
        for _, user_id, _, _ in conns:
            ids.add(str(user_id))
    return ids


# ============================================================================
# Sweep
# ============================================================================

def _run_digest_sweep():
    db = SessionLocal()
    try:
        _process(db)
    except Exception as e:
        logger.error(f"notification_digest: sweep error: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _process(db):
    from backend.models import Notification, User, UserProfile, Campaign
    from backend.email_service import send_digest_email, create_unsubscribe_token

    now = datetime.utcnow()
    connected = _connected_user_ids()

    candidates = (
        db.query(Notification)
        .filter(
            Notification.type.in_(("turn", "mention")),
            Notification.emailed_at.is_(None),
            Notification.created_at >= now - timedelta(days=STALE_AFTER_DAYS),
        )
        .order_by(Notification.created_at.asc())
        .all()
    )
    if not candidates:
        return

    by_user = {}
    for n in candidates:
        by_user.setdefault(str(n.user_id), []).append(n)

    frontend_url = os.getenv("FRONTEND_URL", "https://tba-app-production.up.railway.app")

    for user_id, notifs in by_user.items():
        if user_id in connected:
            continue  # already looking at it — reconsider next sweep

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.email:
            continue

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile and not profile.email_notifications_enabled:
            continue  # opted out — reconsider next sweep in case they re-enable

        to_send = []
        resolved_ids = []
        for n in notifs:
            if already_seen(n.created_at, user.last_login):
                resolved_ids.append(n.id)  # they logged in since — permanently moot
                continue
            if n.type == "turn" and not revalidate_turn(db, n.data or {}):
                resolved_ids.append(n.id)  # turn moved on — permanently moot
                continue
            to_send.append(n)

        if to_send:
            campaign_ids = {(n.data or {}).get("campaign_id") for n in to_send if n.data}
            campaign_ids.discard(None)
            campaign_names = {
                str(c.id): c.name
                for c in db.query(Campaign).filter(Campaign.id.in_(campaign_ids)).all()
            } if campaign_ids else {}

            lines = []
            for n in to_send:
                camp_name = campaign_names.get((n.data or {}).get("campaign_id"), "your campaign")
                when = relative_time_phrase(now, n.created_at)
                icon = "⚔️" if n.type == "turn" else "💬"
                lines.append(
                    f'{icon} <strong>{html.escape(n.title)}</strong> — {html.escape(n.body or "")} '
                    f'<span style="color:#999;">({html.escape(camp_name)}, {when})</span>'
                )

            try:
                token = create_unsubscribe_token(user_id)
                send_digest_email(
                    user.email, lines,
                    unsubscribe_url=f"{frontend_url}/api/profile/unsubscribe?token={token}",
                )
                resolved_ids.extend(n.id for n in to_send)
            except Exception as e:
                logger.error(f"notification_digest: send failed for {user.email}: {e}")
                # leave un-resolved — retry next sweep

        if resolved_ids:
            db.query(Notification).filter(Notification.id.in_(resolved_ids)).update(
                {"emailed_at": now}, synchronize_session=False
            )
            db.commit()


# ============================================================================
# Worker lifecycle
# ============================================================================

async def _worker():
    global _stopping
    while not _stopping:
        target = next_digest_datetime(datetime.now(timezone.utc))
        sleep_for = (target - datetime.now(timezone.utc)).total_seconds()
        try:
            await asyncio.sleep(max(sleep_for, 0))
        except asyncio.CancelledError:
            raise
        if _stopping:
            break
        try:
            _run_digest_sweep()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"notification_digest: worker error: {e}", exc_info=True)


def start_workers():
    """Call once from backend/app.py's lifespan() startup."""
    global _task, _stopping
    _stopping = False
    _task = asyncio.create_task(_worker())
    logger.info(f"notification_digest: worker started (windows: {DIGEST_HOURS} {DIGEST_TIMEZONE})")


async def stop_workers():
    """Call once from backend/app.py's lifespan() shutdown."""
    global _stopping
    _stopping = True
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
