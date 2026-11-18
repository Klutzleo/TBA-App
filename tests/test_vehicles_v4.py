"""
Vehicles V4 (rules v3.1.1): systems. The Story Weaver installs spells and techniques in a vehicle's slots (the die and the area-attack slots come
from the Vehicle Leveling Table), and crew fire them with THEIR stat, the vehicle's spell die and Edge, spending the vehicle's shared uses.
"""
import asyncio
import itertools
import os
import uuid
from unittest import mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vehicles_v4.db")
os.environ.setdefault("API_KEY", "devkey")

_counter = itertools.count(1)


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, Campaign, CampaignMembership, Character, User, VehicleCrew
    from backend.vehicles import apply_level
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
    pl = User(id=uuid.uuid4(), email=f"pl_{tag}@example.com", username=f"pl_{tag}", hashed_password="x")
    db.add_all([sw, pl])
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name="Vehicle systems", description="x" * 12, created_by_user_id=sw.id,
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

    def vehicle(level=7, dp=None):
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

    yield dict(db=db, camp=camp, sw=sw, pl=pl, person=person, vehicle=vehicle, crew=crew, tag=tag, Ability=Ability)
    db.close()


def _set(world, v, slot, user=None, **kw):
    from routes.vehicles import SystemSet, set_system
    body = dict(display_name="Laser Array", macro_command="/laser", power_source="IP", effect_type="damage")
    body.update(kw)
    return asyncio.run(set_system(str(world["camp"].id), str(v.id), slot, SystemSet(**body), world["db"], user or world["sw"]))


def _cast(world, caster, command, die=4, user=None):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[die]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, {"type": "ability_cast", "raw_command": command, "speaker_id": str(caster.id),
                                                                  "speaker_type": "pc" if not caster.is_npc else "npc"},
                                               None, (user or world["pl"]).id if not caster.is_npc else world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    card = next((m for m in sent if m.get("type") == "ability_cast"), None)
    return card, " | ".join((m.get("text") or "") for m in sent)


# ---------------------------------------------------------------- installing systems
def test_a_vehicles_slots_come_from_the_table_with_the_area_slots_marked(world):
    v = world["vehicle"](level=9)
    from backend.vehicles import vehicle_dict
    slots = vehicle_dict(world["db"], v)["systems"]
    assert [s["slot"] for s in slots] == [1, 2, 3, 4, 5]
    assert [s["die"] for s in slots] == ["2d8", "1d12", "1d10", "1d10", "1d10"]
    assert [s["aoe"] for s in slots] == [False, True, False, True, False]
    assert all(s["ability"] is None for s in slots)


def test_the_sw_installs_a_system_and_the_die_and_aoe_come_from_the_slot(world):
    v = world["vehicle"](level=9)
    out = _set(world, v, 2, display_name="Missile Barrage", macro_command="/missiles", power_source="PP")
    slot = out["systems"][1]
    assert slot["die"] == "1d12" and slot["aoe"] is True and slot["ability"]["macro_command"] == "/missiles"
    row = world["db"].query(world["Ability"]).filter_by(character_id=v.id, slot_number=2).one()
    assert row.die == "1d12" and row.is_aoe is True and row.power_source == "PP"


def test_reinstalling_a_slot_replaces_the_system(world):
    v = world["vehicle"]()
    _set(world, v, 1, display_name="One", macro_command="/one")
    _set(world, v, 1, display_name="Two", macro_command="/two")
    rows = world["db"].query(world["Ability"]).filter_by(character_id=v.id, slot_number=1).all()
    assert len(rows) == 1 and rows[0].display_name == "Two"


def test_only_the_sw_can_install_or_clear_a_system(world):
    from routes.vehicles import SystemSet, clear_system, set_system
    v = world["vehicle"]()
    with pytest.raises(HTTPException) as e:
        asyncio.run(set_system(str(world["camp"].id), str(v.id), 1, SystemSet(display_name="x", macro_command="/x1"), world["db"], world["pl"]))
    assert e.value.status_code == 403
    _set(world, v, 1)
    with pytest.raises(HTTPException) as e:
        asyncio.run(clear_system(str(world["camp"].id), str(v.id), 1, world["db"], world["pl"]))
    assert e.value.status_code == 403


def test_a_slot_the_vehicle_does_not_have_is_refused(world):
    v = world["vehicle"](level=2)                             # level 2 has one system slot
    with pytest.raises(HTTPException) as e:
        _set(world, v, 2)
    assert e.value.status_code == 400


@pytest.mark.parametrize("macro", ["/attack", "/pp", "/repair", "laser", "/Laser Beam", "/"])
def test_built_in_and_malformed_commands_are_refused(world, macro):
    from pydantic import ValidationError
    v = world["vehicle"]()
    with pytest.raises((HTTPException, ValidationError)) as e:     # a bare "/" is stopped by the request model before the route
        _set(world, v, 1, macro_command=macro)
    if isinstance(e.value, HTTPException):
        assert e.value.status_code == 400


def test_two_systems_on_one_vehicle_cannot_share_a_command(world):
    v = world["vehicle"](level=7)
    _set(world, v, 1, macro_command="/fire")
    with pytest.raises(HTTPException) as e:
        _set(world, v, 2, macro_command="/fire")
    assert e.value.status_code == 409


def test_levelling_updates_the_dice_and_drops_slots_that_no_longer_exist(world):
    from routes.vehicles import VehicleUpdate, update_vehicle
    v = world["vehicle"](level=7)                             # slots 1-4
    _set(world, v, 1, macro_command="/one")
    _set(world, v, 4, macro_command="/four")
    up = asyncio.run(update_vehicle(str(world["camp"].id), str(v.id), VehicleUpdate(level=9), world["db"], world["sw"]))
    assert up["systems"][0]["die"] == "2d8" and up["systems"][3]["die"] == "1d10"
    down = asyncio.run(update_vehicle(str(world["camp"].id), str(v.id), VehicleUpdate(level=2), world["db"], world["sw"]))
    assert len(down["systems"]) == 1 and down["systems"][0]["ability"]["macro_command"] == "/one"
    assert world["db"].query(world["Ability"]).filter_by(character_id=v.id).count() == 1


def test_deleting_a_vehicle_removes_its_systems(world):
    from routes.vehicles import delete_vehicle
    v = world["vehicle"]()
    _set(world, v, 1)
    asyncio.run(delete_vehicle(str(world["camp"].id), str(v.id), world["db"], world["sw"]))
    assert world["db"].query(world["Ability"]).filter_by(character_id=v.id).count() == 0


# ---------------------------------------------------------------- firing them
def test_crew_fire_a_system_with_their_stat_the_vehicles_die_and_edge_and_the_vehicles_uses(world):
    v = world["vehicle"](level=7)                             # Edge 7, 9 uses, slot 1 die 1d12
    gunner = world["person"]("Gunner", ip=3, edge=0, current_uses=4)
    foe = world["person"]("Drone", npc=True, ip=1, pp=1, sp=1, edge=0, dp=200)
    world["crew"](v, "gunner", gunner)
    _set(world, v, 1, display_name="Laser Array", macro_command="/laser", power_source="IP")
    card, text = _cast(world, gunner, f"/laser @[{foe.name}]", die=4)
    assert card is not None, text
    r = card["results"][0]
    assert r["success"] is not None
    breakdown = " ".join(str(x) for x in r.values() if isinstance(x, str))
    assert "Edge(7)" in breakdown and "IP(3)" in breakdown and "1d12" in breakdown, breakdown
    assert v.current_uses == 8, "the vehicle's pool paid"
    assert gunner.current_uses == 4, "the crew member's own uses were not touched"
    assert card["uses_remaining"] == 8 and card["max_uses"] == 9


def test_a_vehicle_out_of_uses_cannot_fire_even_if_the_crew_has_some(world):
    v = world["vehicle"](level=7)
    v.current_uses = 0
    world["db"].commit()
    gunner = world["person"]("Gunner", current_uses=10)
    foe = world["person"]("Drone", npc=True, dp=50)
    world["crew"](v, "gunner", gunner)
    _set(world, v, 1, macro_command="/laser")
    card, text = _cast(world, gunner, f"/laser @[{foe.name}]")
    assert card is None and "no uses remaining" in text and foe.dp == 50


def test_a_disabled_vehicles_systems_are_offline(world):
    v = world["vehicle"](level=7, dp=0)
    gunner = world["person"]("Gunner")
    foe = world["person"]("Drone", npc=True, dp=50)
    world["crew"](v, "gunner", gunner)
    _set(world, v, 1, macro_command="/laser")
    card, text = _cast(world, gunner, f"/laser @[{foe.name}]")
    assert card is None and "offline" in text and v.current_uses == v.max_uses_per_encounter


def test_someone_who_is_not_crew_cannot_fire_the_vehicles_systems(world):
    v = world["vehicle"](level=7)
    outsider = world["person"]("Outsider")
    foe = world["person"]("Drone", npc=True, dp=50)
    _set(world, v, 1, macro_command="/laser")
    card, text = _cast(world, outsider, f"/laser @[{foe.name}]")
    assert card is None and "not found" in text and v.current_uses == v.max_uses_per_encounter


def test_a_crew_members_own_ability_with_the_same_command_still_wins(world):
    v = world["vehicle"](level=7)
    mage = world["person"]("Mage", ip=3)
    foe = world["person"]("Drone", npc=True, dp=100)
    world["crew"](v, "gunner", mage)
    world["db"].add(world["Ability"](id=uuid.uuid4(), character_id=mage.id, slot_number=1, ability_type="spell", display_name="Own Bolt",
                                     macro_command="/laser", power_source="IP", effect_type="damage", die="1d6", max_uses=9, uses_remaining=9))
    world["db"].commit()
    _set(world, v, 1, macro_command="/laser")
    card, _ = _cast(world, mage, f"/laser @[{foe.name}]")
    assert card["ability_name"] == "Own Bolt" and mage.current_uses == 9 and v.current_uses == v.max_uses_per_encounter


def test_the_sw_can_fire_a_system_for_an_npc_crew_member(world):
    v = world["vehicle"](level=7)
    npc = world["person"]("Pirate", npc=True, ip=2)
    foe = world["person"]("Target", dp=100)
    world["crew"](v, "gunner", npc)
    _set(world, v, 1, macro_command="/laser")
    card, text = _cast(world, npc, f"/laser @[{foe.name}]")
    assert card is not None, text
    assert v.current_uses == v.max_uses_per_encounter - 1


def test_a_buff_system_defaults_to_the_vehicle_and_helps_its_defense_and_weapon(world):
    from backend.buffs import effect_modifier
    v = world["vehicle"](level=7)                             # slot 1 die 1d12 -> +3
    op = world["person"]("Pilot", pp=3)
    world["crew"](v, "gunner", op)
    _set(world, v, 1, display_name="Shield Boost", macro_command="/shield", effect_type="buff", power_source="PP")
    card, text = _cast(world, op, "/shield")
    assert card is not None, text
    assert effect_modifier(world["db"], v.id, "pp") == 3
    assert effect_modifier(world["db"], op.id, "pp") == 0, "the crew member did not get it, the ship did"
    foe = world["person"]("Drone", npc=True, pp=2, edge=0, dp=100)
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
        with mock.patch("backend.roll_logic.roll_dice", return_value=[6]), mock.patch("backend.roll_logic.roll_die", return_value=1):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command", "raw_command": f"/attack @[{foe.name}]",
                        "attacker_id": str(op.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    # 6 + PP3 + vehicle Edge 7 + the ship's own +3 = 19 vs 1 + 2 + 0 = 3: 16 (it would be 13 without the buff)
    assert foe.dp == 100 - 16


# ---------------------------------------------------------------- the page
def test_the_page_has_the_systems_editor_and_crew_macros():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "game.html"), encoding="utf-8").read()
    for needle in ("function saveVehicleSystem", "function clearVehicleSystem", "/systems/", "vehicleMacrosFor"):
        assert needle in html, needle
