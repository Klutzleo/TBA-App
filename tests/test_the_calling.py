"""
The Calling under rules v3.1.

- Win by 4+: clean return at 1 DP, and it does NOT count toward the five.
- Tie, or win by 1-3: Marked by Death (survive at 1 DP). A tie used to kill.
- Lose: dead.
- Only a Mark counts. A Mark that would be the fifth kills instead, but only after the roll
  (the old code killed on entering the Calling a fifth time, with no roll at all).
- The Called check: 1 nightmare, 2-5 peaceful, 6 vision (was 1-2 nightmare).
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_the_calling.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Calling test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, times_called=0):
        c = Character(id=uuid.uuid4(), name=name, owner_id=str(player.id), user_id=player.id, campaign_id=camp.id,
                      level=2, pp=2, ip=3, sp=1, dp=-10, max_dp=10, edge=0, attack_style="1d4", defense_die="1d4",
                      in_calling=True, times_called=times_called)
        db.add(c)
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc)
    db.close()


def _roll_calling(world, char, player_die, sw_die):
    """Resolve the Calling with fixed dice. Level 2 means the SW die is 1d6; IP 3, Edge 0, so the player total is die + 3."""
    from routes.character_fastapi import resolve_the_calling
    rolls = iter([player_die, sw_die])
    request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
    with mock.patch("backend.roll_logic.roll_dice", side_effect=lambda *_a, **_k: [next(rolls)]):
        result = asyncio.run(resolve_the_calling(str(char.id), request, {"stat_choice": "ip"}, world["db"], world["player"]))
    world["db"].expire_all()
    return result


def test_a_tie_is_marked_not_death(world):
    c = world["pc"]("Tied")
    r = _roll_calling(world, c, player_die=3, sw_die=6)        # 3 + IP 3 = 6 vs 6
    assert r["margin"] == 0 and r["outcome"] == "scarred" and r["survived"]
    assert c.dp == 1 and c.is_called and c.times_called == 1 and c.status != "archived" and not c.in_calling


def test_win_by_one_to_three_is_marked(world):
    c = world["pc"]("Close")
    r = _roll_calling(world, c, player_die=4, sw_die=4)        # 7 vs 4, margin 3
    assert r["margin"] == 3 and r["outcome"] == "scarred" and c.times_called == 1


def test_win_by_four_or_more_is_clean_and_does_not_count(world):
    c = world["pc"]("Clean")
    r = _roll_calling(world, c, player_die=5, sw_die=2)        # 8 vs 2
    assert r["outcome"] == "clean" and c.dp == 1 and not c.is_called
    assert c.times_called == 0, "a clean return must not count toward the five"


def test_losing_the_roll_is_death(world):
    c = world["pc"]("Loser")
    r = _roll_calling(world, c, player_die=1, sw_die=6)        # 4 vs 6
    assert r["outcome"] == "dead" and not r["survived"] and r["fifth_mark"] is False
    assert c.status == "archived"


def test_a_clean_return_is_still_possible_with_four_marks(world):
    """The old code refused the roll entirely ('There is no fifth Calling') once times_called reached 4."""
    c = world["pc"]("FourMarks", times_called=4)
    r = _roll_calling(world, c, player_die=6, sw_die=1)
    assert r["outcome"] == "clean" and c.times_called == 4 and c.status != "archived"


def test_a_fifth_mark_kills(world):
    c = world["pc"]("FifthMark", times_called=4)
    r = _roll_calling(world, c, player_die=3, sw_die=6)        # tie would be a Mark, but it would be the fifth
    assert r["outcome"] == "dead" and r["fifth_mark"] is True and not r["survived"]
    assert c.status == "archived" and c.times_called == 5


def test_reaching_minus_ten_with_four_marks_enters_the_calling_not_instant_death(world):
    from routes import campaign_websocket as cw
    c = world["pc"]("AtTheEdge", times_called=4)
    c.in_calling = False
    c.dp = -10
    world["db"].commit()
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(cw._trigger_the_calling(c, world["camp"].id, world["db"], actor_user_id=world["sw"].id))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert c.in_calling and c.status != "archived"
    assert any(m.get("type") == "calling_triggered" for m in sent)
    assert not any(m.get("type") == "permadeath" for m in sent)


@pytest.mark.parametrize("die,effect", [(1, "nightmare"), (2, "peaceful"), (5, "peaceful"), (6, "vision")])
def test_called_check_table(world, die, effect):
    from routes.character_fastapi import called_check
    c = world["pc"](f"Haunted{die}")
    c.is_called = True
    world["db"].commit()
    request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
    with mock.patch("backend.roll_logic.roll_dice", return_value=[die]):
        result = asyncio.run(called_check(str(c.id), request, world["db"], world["sw"]))
    assert result["effect"] == effect
