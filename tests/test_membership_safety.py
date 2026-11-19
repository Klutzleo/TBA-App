"""
Admin center, phase A: leaving means leaving, the Story Weaver hears about a departure with what they need to plan, and a Story Weaver can
remove (and ban) a player.

Background: 53 of the app's 81 membership lookups never checked left_at, so someone who left could still call a campaign's APIs. The fix is one
choke point (every SELECT on CampaignMembership ignores people who have left unless a query opts in), tested here at the choke point and
through real endpoints.
"""
import asyncio
import os
import uuid
from unittest import mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_membership_safety.db")
os.environ.setdefault("API_KEY", "devkey")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
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

    sw, p1, p2, stranger = user("sw"), user("p1"), user("p2"), user("stranger")
    camp = Campaign(id=uuid.uuid4(), name=f"Safety {tag}", description="x" * 12, created_by_user_id=sw.id, created_by_id=str(sw.id),
                    story_weaver_id=sw.id, join_code=tag[:6].upper())
    db.add(camp)
    db.commit()
    memberships = {}
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player")):
        m = CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role)
        db.add(m)
        memberships[u.id] = m
    db.commit()

    def pc(name, owner, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str(owner.id), user_id=owner.id, campaign_id=camp.id, level=2, pp=2,
                      ip=2, sp=2, dp=10, max_dp=10, edge=1, attack_style="1d6", defense_die="1d4", status="active", **kw)
        db.add(c)
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, p1=p1, p2=p2, stranger=stranger, pc=pc, tag=tag, memberships=memberships)
    db.close()


def _leave(world, user):
    from routes.campaigns import leave_campaign
    return _run(leave_campaign(world["camp"].id, current_user=user, db=world["db"]))


def _remove(world, actor, target, **body):
    from routes.campaigns import RemoveMemberRequest, remove_member
    return _run(remove_member(world["camp"].id, target.id, RemoveMemberRequest(**body), current_user=actor, db=world["db"]))


def _notifications(world, user):
    from backend.models import Notification
    world["db"].expire_all()
    return world["db"].query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at).all()


# ---------------------------------------------------------------- the choke point: people who left are invisible by default
def test_a_member_who_left_is_invisible_to_every_default_membership_query(world):
    from backend.models import CampaignMembership as CM
    db = world["db"]
    assert db.query(CM).filter(CM.campaign_id == world["camp"].id, CM.user_id == world["p1"].id).first() is not None
    _leave(world, world["p1"])
    assert db.query(CM).filter(CM.campaign_id == world["camp"].id, CM.user_id == world["p1"].id).first() is None
    assert db.query(CM).filter(CM.campaign_id == world["camp"].id).count() == 2, "only the Story Weaver and the other player remain"


def test_a_query_can_opt_in_to_see_departures(world):
    from backend.models import CampaignMembership as CM
    _leave(world, world["p1"])
    row = world["db"].query(CM).filter(CM.campaign_id == world["camp"].id, CM.user_id == world["p1"].id) \
        .execution_options(include_left_members=True).first()
    assert row is not None and row.left_at is not None


def test_the_existing_membership_helper_now_refuses_someone_who_left(world):
    from routes.character_fastapi import _is_campaign_member
    assert _is_campaign_member(world["camp"].id, world["p1"].id, world["db"]) is True
    _leave(world, world["p1"])
    assert _is_campaign_member(world["camp"].id, world["p1"].id, world["db"]) is False


def test_someone_who_left_is_refused_by_endpoints_that_used_to_let_them_in(world):
    """routes/vehicles.py and the NPC list never checked left_at before the choke point."""
    from routes.vehicles import list_vehicles
    from routes.character_fastapi import list_npcs
    from types import SimpleNamespace
    db = world["db"]
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    assert _run(list_vehicles(str(world["camp"].id), db, world["p1"])) == []          # still a member: allowed
    _run(list_npcs(str(world["camp"].id), req, db, world["p1"]))                       # allowed
    _leave(world, world["p1"])
    with pytest.raises(HTTPException) as e:
        _run(list_vehicles(str(world["camp"].id), db, world["p1"]))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        _run(list_npcs(str(world["camp"].id), req, db, world["p1"]))
    assert e.value.status_code == 403


def test_the_live_chat_still_sees_recorded_departures_so_it_cannot_resurrect_them():
    import inspect
    from routes import campaign_websocket
    src = inspect.getsource(campaign_websocket.campaign_websocket)
    stale = src[src.index("stale = db.query(CampaignMembership)"):][:400]
    assert "include_left_members=True" in stale


# ---------------------------------------------------------------- the Story Weaver hears about a departure
def test_leaving_gives_the_story_weaver_a_lasting_notification_naming_the_character(world):
    world["pc"]("Beef", world["p1"])
    with mock.patch("backend.notifications.send_push") as push:
        _leave(world, world["p1"])
    notes = _notifications(world, world["sw"])
    assert len(notes) == 1
    n = notes[0]
    assert n.title == "A player left your campaign" and world["p1"].username in n.body
    assert f"Beef {world['tag']} (level 2)" in n.body and "still in the campaign" in n.body
    assert n.data["characters"] == [f"Beef {world['tag']}"] and n.data["in_encounter"] is False
    assert n.data["url"].endswith(str(world["camp"].id))
    assert push.called, "the push still goes out too"


def test_the_notification_says_when_the_character_is_in_the_current_encounter(world):
    from backend.models import Encounter, InitiativeRoll
    c = world["pc"]("Beef", world["p1"])
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True)
    world["db"].add(enc)
    world["db"].commit()
    world["db"].add(InitiativeRoll(encounter_id=enc.id, character_id=c.id, name=c.name, roll_result=5))
    world["db"].commit()
    with mock.patch("backend.notifications.send_push"):
        _leave(world, world["p1"])
    n = _notifications(world, world["sw"])[0]
    assert "in the current encounter" in n.body and "turn order will stop" in n.body and n.data["in_encounter"] is True


def test_leaving_with_no_character_says_nothing_needs_sorting_out(world):
    with mock.patch("backend.notifications.send_push"):
        _leave(world, world["p2"])
    assert "no character" in _notifications(world, world["sw"])[0].body


def test_two_characters_are_both_named(world):
    world["pc"]("Alpha", world["p1"])
    world["pc"]("Bravo", world["p1"])
    with mock.patch("backend.notifications.send_push"):
        _leave(world, world["p1"])
    body = _notifications(world, world["sw"])[0].body
    assert "Alpha" in body and "Bravo" in body and " and " in body and "are still in the campaign" in body


def test_a_notification_failure_never_undoes_the_leave(world):
    from backend.models import CampaignMembership as CM
    with mock.patch("routes.campaigns.notify_story_weaver_of_leave", side_effect=RuntimeError("boom")):
        out = _leave(world, world["p1"])
    assert out["success"] is True
    row = world["db"].query(CM).filter(CM.campaign_id == world["camp"].id, CM.user_id == world["p1"].id).execution_options(include_left_members=True).first()
    assert row.left_at is not None


# ---------------------------------------------------------------- removing a player
def test_the_story_weaver_removes_a_player_and_it_is_recorded(world):
    from backend.models import CampaignMembership as CM
    out = _remove(world, world["sw"], world["p1"], reason="harassing another player")
    assert out["success"] and out["removed"] == world["p1"].username and out["banned"] is False
    row = world["db"].query(CM).filter(CM.campaign_id == world["camp"].id, CM.user_id == world["p1"].id).execution_options(include_left_members=True).first()
    assert row.left_at is not None and row.removed_by_user_id == world["sw"].id and row.removal_reason == "harassing another player"


def test_the_removed_player_is_told_but_never_the_reason(world):
    _remove(world, world["sw"], world["p1"], reason="a private reason")
    n = _notifications(world, world["p1"])[0]
    assert n.title == "Removed from a campaign" and world["camp"].name in n.body and "private reason" not in (n.body + str(n.data))


def test_only_the_story_weaver_can_remove_and_not_themselves_or_each_other(world):
    with pytest.raises(HTTPException) as e:
        _remove(world, world["p1"], world["p2"])
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        _remove(world, world["sw"], world["sw"])
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _remove(world, world["sw"], world["stranger"])
    assert e.value.status_code == 404
    from backend.models import CampaignMembership as CM
    assert world["db"].query(CM).filter(CM.campaign_id == world["camp"].id).count() == 3, "nobody was removed by the refused attempts"


def test_a_removed_player_is_cut_off_from_the_campaigns_data(world):
    from routes.vehicles import list_vehicles
    _remove(world, world["sw"], world["p1"])
    with pytest.raises(HTTPException) as e:
        _run(list_vehicles(str(world["camp"].id), world["db"], world["p1"]))
    assert e.value.status_code == 403


def test_by_default_their_character_becomes_an_npc_the_story_weaver_controls(world):
    c = world["pc"]("Beef", world["p1"])
    out = _remove(world, world["sw"], world["p1"])
    world["db"].expire_all()
    assert out["characters_converted"] == [c.name]
    assert c.is_npc is True and c.user_id is None and c.owner_id == str(world["sw"].id) and c.visible_to_players is True


def test_or_the_story_weaver_can_leave_the_character_as_it_is(world):
    c = world["pc"]("Beef", world["p1"])
    out = _remove(world, world["sw"], world["p1"], characters="keep")
    world["db"].expire_all()
    assert out["characters_converted"] == [] and c.is_npc is False and c.user_id == world["p1"].id


def test_an_npc_or_other_players_character_is_never_touched(world):
    mine = world["pc"]("Mine", world["p2"])
    _remove(world, world["sw"], world["p1"])
    world["db"].expire_all()
    assert mine.is_npc is False and mine.user_id == world["p2"].id


# ---------------------------------------------------------------- bans
def _join(world, user):
    from routes.campaigns import JoinCampaignRequest, join_campaign
    return _run(join_campaign(JoinCampaignRequest(join_code=world["camp"].join_code), current_user=user, db=world["db"]))


def test_a_banned_player_cannot_rejoin_with_the_join_code(world):
    from backend.models import CampaignBan
    _remove(world, world["sw"], world["p1"], ban=True, reason="banned")
    assert world["db"].query(CampaignBan).filter_by(campaign_id=world["camp"].id, user_id=world["p1"].id).count() == 1
    with pytest.raises(HTTPException) as e:
        _join(world, world["p1"])
    assert e.value.status_code == 403 and e.value.detail == "You can't join this campaign."


def test_a_player_removed_without_a_ban_can_come_back(world):
    _remove(world, world["sw"], world["p1"], ban=False)
    assert _join(world, world["p1"])["success"] is True
    from routes.vehicles import list_vehicles
    assert _run(list_vehicles(str(world["camp"].id), world["db"], world["p1"])) == []


def test_a_ban_in_one_campaign_does_not_stop_joining_another(world):
    from backend.models import Campaign, CampaignMembership
    other = Campaign(id=uuid.uuid4(), name=f"Other {world['tag']}", description="x" * 12, created_by_user_id=world["sw"].id,
                     created_by_id=str(world["sw"].id), story_weaver_id=world["sw"].id, join_code=("O" + world["tag"][:5]).upper())
    world["db"].add(other)
    world["db"].commit()
    _remove(world, world["sw"], world["p1"], ban=True)
    from routes.campaigns import JoinCampaignRequest, join_campaign
    assert _run(join_campaign(JoinCampaignRequest(join_code=other.join_code), current_user=world["p1"], db=world["db"]))["success"]


# ---------------------------------------------------------------- the live connection
class _FakeSocket:
    def __init__(self):
        self.closed = None

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)


def test_removal_closes_the_players_live_connection_and_only_theirs(world):
    from routes import campaign_websocket as cw
    gone, kept = _FakeSocket(), _FakeSocket()
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    cid = world["camp"].id
    cw.manager.active_connections[cid] = [(gone, world["p1"].id, "p1", "p1"), (kept, world["p2"].id, "p2", "p2")]
    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        _remove(world, world["sw"], world["p1"])
    finally:
        cw.manager.broadcast = original
        remaining = list(cw.manager.active_connections.get(cid, []))
        cw.manager.active_connections.pop(cid, None)
    assert gone.closed and gone.closed[0] == 1008 and "removed" in gone.closed[1].lower()
    assert kept.closed is None
    assert [c[1] for c in remaining] == [world["p2"].id]
    assert any(m.get("type") == "player_left_campaign" and "was removed" in m.get("message", "") for m in sent)


def test_the_close_reason_fits_the_websocket_limit():
    """A WebSocket close reason must be at most 123 bytes or the close itself fails."""
    import inspect
    from routes import campaigns
    src = inspect.getsource(campaigns.remove_member)
    reason = "You were removed from this campaign by the Story Weaver."
    assert reason in src and len(reason.encode()) <= 123


def test_the_game_page_has_the_remove_player_window_and_button():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "game.html"), encoding="utf-8").read()
    for needle in ('id="removePlayerModal"', "function openRemovePlayerModal", "function confirmRemovePlayer", "/members/${_removeTarget.userId}/remove",
                   "isSW() && s.label !== 'Story Weaver'", 'id="rmpBan"', "data.message ||"):
        assert needle in html, needle
    assert "\u2014" not in html[html.index('id="removePlayerModal"'):][:2600], "no em-dashes in the new window's copy"
