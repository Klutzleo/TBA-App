"""
Vehicles V3 (rules v3.1.1): crew stations. The Captain (1d6 + SP + Edge) and Pilot (1d6 + IP + Edge) give a one-time add to the Gunner's next
attack or the Defense Officer's next defense roll, the Engineer (1d6 + IP + Edge) restores that much DP, and none of it works from the
wrong station or from a down character.
"""
import asyncio
import itertools
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vehicles_v3.db")
os.environ.setdefault("API_KEY", "devkey")

_counter = itertools.count(1)


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, User, VehicleCrew
    from backend.vehicles import apply_level
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
    pl = User(id=uuid.uuid4(), email=f"pl_{tag}@example.com", username=f"pl_{tag}", hashed_password="x")
    db.add_all([sw, pl])
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name="Vehicle crew", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=pl.id, role="player"))
    db.commit()

    def person(name, npc=False, pp=3, ip=2, sp=2, edge=1, **kw):
        fields = dict(level=2, dp=20, max_dp=20, attack_style="1d6", defense_die="1d4", max_uses_per_encounter=10, current_uses=10)
        fields.update(kw)
        c = Character(id=uuid.uuid4(), name=f"{name}{next(_counter)} {tag}", owner_id=str(sw.id if npc else pl.id),
                      user_id=None if npc else pl.id, campaign_id=camp.id, is_npc=npc, pp=pp, ip=ip, sp=sp, edge=edge, **fields)
        db.add(c)
        db.commit()
        return c

    def vehicle(level=5, dp=None):
        v = Character(id=uuid.uuid4(), name=f"Ship{next(_counter)} {tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      is_vehicle=True, level=level, pp=0, ip=0, sp=0, dp=0, max_dp=0, edge=0, bap=0, attack_style="1d4",
                      defense_die="1d4", max_uses_per_encounter=0, current_uses=0, status="active")
        apply_level(v, level)
        if dp is not None:
            v.dp = dp
        db.add(v)
        db.commit()
        return v

    def crew(v, station, c):
        db.add(VehicleCrew(id=uuid.uuid4(), vehicle_id=v.id, character_id=c.id, station=station))
        db.commit()

    yield dict(db=db, camp=camp, sw=sw, pl=pl, person=person, vehicle=vehicle, crew=crew, tag=tag)
    db.close()


def _say(world, command, actor, die=4):
    """Run a /support or /repair command as `actor` (the Story Weaver acts for them) and return what was announced."""
    from routes import campaign_websocket as cw
    sent = []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[die]):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command", "raw_command": command,
                        "attacker_id": str(actor.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return " | ".join((m.get("text") or "") for m in sent)


def _attack(world, attacker, target, atk=6, defense=1):
    from routes import campaign_websocket as cw
    sent = []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("backend.roll_logic.roll_dice", return_value=[atk]), mock.patch("backend.roll_logic.roll_die", return_value=defense):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command", "raw_command": f"/attack @[{target.name}]",
                        "attacker_id": str(attacker.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent


def _adds(world, v):
    from backend.vehicles import pending_adds
    return pending_adds(world["db"], v.id)


# ---------------------------------------------------------------- Captain and Pilot
def test_the_captain_rolls_1d6_sp_and_the_vehicles_edge_and_the_add_waits(world):
    v = world["vehicle"](level=5)                              # Edge 5
    cap = world["person"]("Captain", sp=3)
    world["crew"](v, "captain", cap)
    out = _say(world, "/support attack", cap, die=4)          # 4 + SP3 + Edge5 = 12
    assert "= 12" in out and "next attack roll" in out
    assert _adds(world, v) == [{"station": "captain", "target": "attack", "amount": 12}]


def test_the_pilot_adds_with_intellect(world):
    v = world["vehicle"](level=5)
    pilot = world["person"]("Pilot", ip=3, sp=1)
    world["crew"](v, "pilot", pilot)
    _say(world, "/support defense", pilot, die=2)             # 2 + IP3 + Edge5 = 10
    assert _adds(world, v) == [{"station": "pilot", "target": "defense", "amount": 10}]


def test_a_new_support_roll_replaces_that_stations_waiting_one(world):
    v = world["vehicle"](level=5)
    cap = world["person"]("Captain", sp=2)
    world["crew"](v, "captain", cap)
    _say(world, "/support attack", cap, die=6)                # 13
    _say(world, "/support defense", cap, die=1)               # 8
    assert _adds(world, v) == [{"station": "captain", "target": "defense", "amount": 8}]


def test_the_gunners_next_attack_gets_the_add_once(world):
    v = world["vehicle"](level=5)
    gun, cap = world["person"]("Gunner", pp=3), world["person"]("Captain", sp=2)
    foe = world["person"]("Drone", npc=True, pp=2, edge=0, dp=100)
    world["crew"](v, "gunner", gun)
    world["crew"](v, "captain", cap)
    _attack(world, gun, foe)                                  # 6 + 3 + 5 = 14 vs 1 + 2 + 0 = 3: 11
    assert foe.dp == 89
    _say(world, "/support attack", cap, die=4)                # 4 + 2 + 5 = 11
    _attack(world, gun, foe)                                  # 11 + 11 = 25 vs 3: 22
    assert foe.dp == 89 - 22
    assert _adds(world, v) == []
    _attack(world, gun, foe)                                  # back to 11: the add was used up
    assert foe.dp == 89 - 22 - 11


def test_captain_and_pilot_adds_stack_on_the_same_roll(world):
    v = world["vehicle"](level=5)
    gun, cap, pilot = world["person"]("Gunner", pp=3), world["person"]("Captain", sp=2), world["person"]("Pilot", ip=2)
    foe = world["person"]("Drone", npc=True, pp=2, edge=0, dp=100)
    for st, c in (("gunner", gun), ("captain", cap), ("pilot", pilot)):
        world["crew"](v, st, c)
    _say(world, "/support attack", cap, die=4)                # 11
    _say(world, "/support attack", pilot, die=1)              # 1 + 2 + 5 = 8
    _attack(world, gun, foe)                                  # 14 + 11 + 8 = 33 vs 3: 30
    assert foe.dp == 70


def test_an_attack_add_does_not_leak_onto_a_defense_roll(world):
    v = world["vehicle"](level=5)
    cap, foe = world["person"]("Captain", sp=2), world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    world["crew"](v, "captain", cap)
    _say(world, "/support attack", cap, die=4)
    start = v.dp
    _attack(world, foe, v)                                    # 10 vs 1 + 0 + Edge5 = 6: 4
    assert v.dp == start - 4 and len(_adds(world, v)) == 1


def test_a_defense_add_goes_on_the_vehicles_defense_and_is_used_up(world):
    v = world["vehicle"](level=5)
    cap, foe = world["person"]("Captain", sp=2), world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    world["crew"](v, "captain", cap)
    _say(world, "/support defense", cap, die=4)               # 11
    start = v.dp
    _attack(world, foe, v)                                    # 10 vs 6 + 11 = 17: 0 damage
    assert v.dp == start and _adds(world, v) == []
    _attack(world, foe, v)                                    # add gone: 4 damage
    assert v.dp == start - 4


def test_the_add_lands_on_one_die_of_a_multi_die_roll_not_all(world):
    from backend.roll_logic import resolve_multi_die_attack
    with mock.patch("backend.roll_logic.roll_dice", return_value=[3, 3]), mock.patch("backend.roll_logic.roll_die", return_value=1):
        out = resolve_multi_die_attack({"name": "A"}, "2d6", 2, {"name": "D"}, "1d4", 1, 1, defender_edge=0, roll_add=10)
    rolls = out["individual_rolls"]
    assert rolls[0]["crew_add"] == 10 and rolls[1]["crew_add"] == 0
    assert rolls[0]["attacker_roll"] - rolls[1]["attacker_roll"] == 10


def test_support_from_the_wrong_station_or_no_station_is_refused(world):
    v = world["vehicle"]()
    gun, nobody = world["person"]("Gunner"), world["person"]("Deckhand")
    world["crew"](v, "gunner", gun)
    assert "Only the Captain or Pilot" in _say(world, "/support attack", gun)
    assert "aren't on a vehicle station" in _say(world, "/support attack", nobody) or "isn't on a vehicle station" in _say(world, "/support attack", nobody)
    assert _adds(world, v) == []


def test_support_needs_a_target_and_an_enabled_vehicle(world):
    v = world["vehicle"](dp=0)
    cap = world["person"]("Captain")
    world["crew"](v, "captain", cap)
    assert "disabled" in _say(world, "/support attack", cap)
    v.dp = 10
    world["db"].commit()
    assert "Usage" in _say(world, "/support sideways", cap)
    assert _adds(world, v) == []


def test_a_down_crew_member_cannot_work_a_station(world):
    v = world["vehicle"]()
    cap = world["person"]("Captain", dp=0)
    world["crew"](v, "captain", cap)
    assert "can't work a station" in _say(world, "/support attack", cap)


# ---------------------------------------------------------------- Engineer
def test_the_engineer_restores_dp_equal_to_the_roll(world):
    v = world["vehicle"](level=5, dp=3)                       # max 16, Edge 5
    eng = world["person"]("Engineer", ip=3)
    world["crew"](v, "engineer", eng)
    out = _say(world, "/repair", eng, die=2)                  # 2 + IP3 + Edge5 = 10
    assert "= 10" in out and v.dp == 13


def test_repair_is_capped_at_max_dp(world):
    v = world["vehicle"](level=5, dp=14)
    eng = world["person"]("Engineer", ip=3)
    world["crew"](v, "engineer", eng)
    _say(world, "/repair", eng, die=6)
    assert v.dp == v.max_dp == 16


def test_repair_works_on_a_disabled_vehicle_and_climbs_from_below_zero(world):
    v = world["vehicle"](level=5, dp=-4)
    eng = world["person"]("Engineer", ip=3)
    world["crew"](v, "engineer", eng)
    _say(world, "/repair", eng, die=1)                        # 1 + 3 + 5 = 9
    assert v.dp == 5


def test_only_the_engineer_repairs(world):
    v = world["vehicle"](dp=3)
    cap = world["person"]("Captain")
    world["crew"](v, "captain", cap)
    assert "Only the Engineer" in _say(world, "/repair", cap)
    assert v.dp == 3


def test_the_story_weaver_can_run_an_npc_engineer(world):
    v = world["vehicle"](level=5, dp=2)
    eng = world["person"]("Mechanic", npc=True, ip=2)
    world["crew"](v, "engineer", eng)
    _say(world, "/repair", eng, die=3)                        # 3 + 2 + 5 = 10
    assert v.dp == 12


def test_a_player_cannot_act_for_someone_else(world):
    from routes import campaign_websocket as cw
    v = world["vehicle"](dp=3)
    eng = world["person"]("Engineer", npc=True)
    world["crew"](v, "engineer", eng)
    sent = []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command", "raw_command": "/repair",
                    "attacker_id": str(eng.id)}, WS(), world["pl"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert v.dp == 3 and any("Only the Story Weaver" in (m.get("text") or "") for m in sent)


# ---------------------------------------------------------------- cleanup and display
def test_waiting_adds_are_cleared_when_the_encounter_ends(world):
    from backend.models import Encounter
    from routes import campaign_websocket as cw
    v = world["vehicle"]()
    cap = world["person"]("Captain")
    world["crew"](v, "captain", cap)
    _say(world, "/support attack", cap)
    assert len(_adds(world, v)) == 1
    world["db"].add(Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True))
    world["db"].commit()

    class WS:
        async def send_json(self, m):
            pass

    async def fake_broadcast(_cid, m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(cw.end_encounter(world["camp"].id, world["sw"].id, world["db"], WS()))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert _adds(world, v) == []


def test_pending_adds_show_on_the_vehicle_card(world):
    from backend.vehicles import vehicle_dict
    v = world["vehicle"]()
    cap = world["person"]("Captain")
    world["crew"](v, "captain", cap)
    _say(world, "/support defense", cap)
    card = vehicle_dict(world["db"], v)
    assert card["pending_adds"] and card["pending_adds"][0]["target"] == "defense"


def test_the_page_wires_the_station_buttons_and_commands():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "game.html"), encoding="utf-8").read()
    for needle in ("function vehicleStationAction", "startsWith('/support')", "startsWith('/repair')", "/support attack", "Boost attack", "pending_adds"):
        assert needle in html, needle
