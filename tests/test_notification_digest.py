"""
Tests for backend/notification_digest.py — the twice-daily email digest for
'your turn' / '@mention' notifications.

Focus: the pure gating logic (staleness, already-seen, time phrasing, window
scheduling) and the one correctness-critical DB-backed check — that a stale
'your turn' notification is caught and NOT emailed once the turn has moved on.
"""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from backend.notification_digest import (
    already_seen,
    is_stale,
    next_digest_datetime,
    relative_time_phrase,
    revalidate_turn,
)


# ============================================================================
# is_stale / already_seen
# ============================================================================

def test_is_stale_false_just_under_the_cutoff():
    now = datetime(2026, 9, 29, 12, 0, 0)
    created = now - timedelta(days=2) + timedelta(minutes=1)
    assert is_stale(now, created) is False


def test_is_stale_true_just_over_the_cutoff():
    now = datetime(2026, 9, 29, 12, 0, 0)
    created = now - timedelta(days=2) - timedelta(minutes=1)
    assert is_stale(now, created) is True


def test_already_seen_true_when_login_after_event():
    created = datetime(2026, 9, 29, 9, 0, 0)
    last_login = datetime(2026, 9, 29, 10, 0, 0)
    assert already_seen(created, last_login) is True


def test_already_seen_false_when_login_before_event():
    created = datetime(2026, 9, 29, 9, 0, 0)
    last_login = datetime(2026, 9, 29, 8, 0, 0)
    assert already_seen(created, last_login) is False


def test_already_seen_false_when_never_logged_in():
    created = datetime(2026, 9, 29, 9, 0, 0)
    assert already_seen(created, None) is False


def test_already_seen_true_at_exact_same_instant():
    # A user actively online right when the event fires: covered separately by the
    # WebSocket-connected check, but the last_login comparison alone should still
    # treat "logged in at exactly this moment" as seen, not miss it by a hair.
    t = datetime(2026, 9, 29, 9, 0, 0)
    assert already_seen(t, t) is True


# ============================================================================
# relative_time_phrase — real elapsed time, never in-game/narrative time
# ============================================================================

@pytest.mark.parametrize("now_str,dt_str,expected", [
    ("2026-09-29 12:30", "2026-09-29 12:15", "a few minutes ago"),
    ("2026-09-29 12:30", "2026-09-29 09:30", "about 3 hours ago"),
    ("2026-09-29 12:30", "2026-09-29 11:30", "about 1 hour ago"),
    ("2026-09-29 20:00", "2026-09-29 08:00", "earlier today"),
    ("2026-09-29 08:00", "2026-09-28 22:00", "last night"),
    ("2026-09-29 12:00", "2026-09-28 12:01", "yesterday"),
    ("2026-09-30 12:00", "2026-09-27 12:00", "3 days ago"),
])
def test_relative_time_phrase(now_str, dt_str, expected):
    fmt = "%Y-%m-%d %H:%M"
    now = datetime.strptime(now_str, fmt)
    dt = datetime.strptime(dt_str, fmt)
    assert relative_time_phrase(now, dt) == expected


# ============================================================================
# next_digest_datetime — fixed 9am/6pm windows, DST-aware via zoneinfo
# ============================================================================

def test_next_digest_datetime_picks_evening_window_same_day():
    # 10am Eastern -> next window is 6pm the same day
    now = datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc)  # 10am EDT
    target = next_digest_datetime(now, tz_name="America/New_York")
    local_now = now.astimezone(ZoneInfo("America/New_York"))
    local_target = target.astimezone(ZoneInfo("America/New_York"))
    assert (local_target.date(), local_target.hour) == (local_now.date(), 18)


def test_next_digest_datetime_rolls_to_next_morning():
    # 8pm Eastern -> next window is 9am the following day
    now = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)  # 8pm EDT on the 29th
    target = next_digest_datetime(now, tz_name="America/New_York")
    local_now = now.astimezone(ZoneInfo("America/New_York"))
    local_target = target.astimezone(ZoneInfo("America/New_York"))
    assert local_target > local_now
    assert local_target.hour == 9
    assert local_target.date() == local_now.date() + timedelta(days=1)


def test_next_digest_datetime_always_strictly_in_the_future():
    # Right at a window boundary — must not return "now" itself.
    now = datetime(2026, 9, 29, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    target = next_digest_datetime(now, tz_name="America/New_York")
    assert target > now


# ============================================================================
# revalidate_turn — the correctness-critical live re-check
# ============================================================================

@pytest.fixture
def encounter_world():
    """A minimal active encounter with two PCs in initiative order."""
    from backend.db import SessionLocal
    from backend.models import Campaign, Character, Encounter, InitiativeRoll, User

    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:8]
        sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
        db.add(sw)
        db.commit()

        campaign = Campaign(id=uuid.uuid4(), name=f"Digest Test {tag}", description="digest tests",
                             created_by_user_id=sw.id, created_by_id=str(sw.id), story_weaver_id=sw.id)
        db.add(campaign)
        db.commit()

        def make_char(name):
            c = Character(id=uuid.uuid4(), name=name, owner_id=str(sw.id), user_id=sw.id,
                           campaign_id=campaign.id, is_npc=False, pp=2, ip=2, sp=2, dp=10, max_dp=10,
                           attack_style="melee", defense_die="1d6")
            db.add(c)
            return c

        first, second = make_char("First"), make_char("Second")
        db.commit()

        encounter = Encounter(id=uuid.uuid4(), campaign_id=campaign.id, is_active=True, current_turn_index=0)
        db.add(encounter)
        db.commit()

        db.add(InitiativeRoll(id=uuid.uuid4(), encounter_id=encounter.id, character_id=first.id,
                               name="First", roll_result=10))
        db.add(InitiativeRoll(id=uuid.uuid4(), encounter_id=encounter.id, character_id=second.id,
                               name="Second", roll_result=5))
        db.commit()

        yield {"db": db, "encounter": encounter, "first": first, "second": second}
    finally:
        db.close()


def test_revalidate_turn_true_when_still_their_turn(encounter_world):
    w = encounter_world
    data = {"encounter_id": str(w["encounter"].id), "character_id": str(w["first"].id)}
    assert revalidate_turn(w["db"], data) is True


def test_revalidate_turn_false_once_turn_has_moved_on(encounter_world):
    w = encounter_world
    w["encounter"].current_turn_index = 1  # SW advanced past First while they were away
    w["db"].commit()
    data = {"encounter_id": str(w["encounter"].id), "character_id": str(w["first"].id)}
    assert revalidate_turn(w["db"], data) is False


def test_revalidate_turn_false_once_encounter_ended(encounter_world):
    w = encounter_world
    w["encounter"].is_active = False
    w["db"].commit()
    data = {"encounter_id": str(w["encounter"].id), "character_id": str(w["first"].id)}
    assert revalidate_turn(w["db"], data) is False


def test_revalidate_turn_false_on_missing_data():
    from backend.db import SessionLocal
    db = SessionLocal()
    try:
        assert revalidate_turn(db, {}) is False
    finally:
        db.close()
