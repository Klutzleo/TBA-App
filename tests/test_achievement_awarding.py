"""
Achievements are awarded once per account.

check_and_award() only inserts a row when the account doesn't already hold that achievement. These tests pin that down
for the scene achievements ("Let There Be Light" at 1 scene update, "Ch-Ch-Changes" at 25).
"""
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_achievement_awarding.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def db():
    from backend.db import SessionLocal, init_db
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def new_user(db):
    from backend.models import User
    tag = uuid.uuid4().hex[:8]
    u = User(id=uuid.uuid4(), email=f"ach_{tag}@example.com", username=f"ach_{tag}", hashed_password="x")
    db.add(u)
    db.commit()
    return str(u.id)


def held(db, user_id, achievement_id):
    from backend.models import UserAchievement
    db.expire_all()
    return db.query(UserAchievement).filter_by(user_id=uuid.UUID(user_id), achievement_id=achievement_id).count()


def test_first_scene_update_awards_let_there_be_light_exactly_once(db):
    from backend.stats_tracker import commit_stats, track_scene_update
    uid = new_user(db)
    track_scene_update(db, uid)
    assert "sw_let_there_be_light" in commit_stats(db, uid)
    assert held(db, uid, "sw_let_there_be_light") == 1
    # setting more scenes never awards it again
    for _ in range(3):
        track_scene_update(db, uid)
        assert "sw_let_there_be_light" not in commit_stats(db, uid)
    assert held(db, uid, "sw_let_there_be_light") == 1


def test_nothing_is_awarded_before_the_first_scene_update(db):
    from backend.stats_tracker import commit_stats
    uid = new_user(db)
    assert "sw_let_there_be_light" not in commit_stats(db, uid)
    assert held(db, uid, "sw_let_there_be_light") == 0


def test_twenty_five_updates_award_the_second_tier_once(db):
    from backend.stats_tracker import commit_stats, track_scene_update
    uid = new_user(db)
    awarded = []
    for _ in range(26):
        track_scene_update(db, uid)
        awarded += commit_stats(db, uid)
    assert awarded.count("sw_let_there_be_light") == 1 and awarded.count("sw_changes") == 1


def test_re_evaluating_never_duplicates_anything(db):
    from backend.achievements import check_and_award
    from backend.models import UserAchievement
    uid = new_user(db)
    check_and_award(uuid.UUID(uid), db)
    db.commit()
    first = db.query(UserAchievement).filter_by(user_id=uuid.UUID(uid)).count()
    for _ in range(3):
        assert check_and_award(uuid.UUID(uid), db) == []
        db.commit()
    assert db.query(UserAchievement).filter_by(user_id=uuid.UUID(uid)).count() == first
