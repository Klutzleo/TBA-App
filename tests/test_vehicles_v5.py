"""
Vehicles V5 (rules v3.1.1): disabling. A called shot (sabotage, hacking) is an attack roll against the vehicle's defense; if it lands the Story
Weaver picks one system or the movement, knocked out for 2 rounds at no DP cost. A knocked-out system can't be fired until it comes back.
"""
import asyncio
import itertools
import os
import uuid
from unittest import mock

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vehicles_v5.db")
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
    camp = Campaign(id=uuid.uuid4(), name="Vehicle disabling", description="x" * 12, created_by_user_id=sw.id,
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

    def system(v, slot, macro="/laser", name="Laser Array", power="IP", effect="damage"):
        db.add(Ability(id=uuid.uuid4(), character_id=v.id, slot_number=slot, ability_type="spell", display_name=name, macro_command=macro,
                       power_source=power, effect_type=effect, die="1d12", max_uses=9, uses_remaining=9))
        db.commit()

    yield dict(db=db, camp=camp, sw=sw, pl=pl, person=person, vehicle=vehicle, crew=crew, system=system, tag=tag)
    db.close()


def _disable(world, attacker, target, atk=6, defense=1, command=None):
    from routes import campaign_websocket as cw
    sent, private = [], []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    async def fake_send(_cid, _uid, m):
        private.append(m)

    ob, os_ = cw.manager.broadcast, cw.manager.send_to_user
    cw.manager.broadcast, cw.manager.send_to_user = fake_broadcast, fake_send
    try:
        with mock.patch("backend.roll_logic.roll_dice", return_value=[atk]), mock.patch("backend.roll_logic.roll_die", return_value=defense):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command",
                        "raw_command": command or f"/disable @[{target.name}]", "attacker_id": str(attacker.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast, cw.manager.send_to_user = ob, os_
    world["db"].expire_all()
    return sent, private


def _text(sent):
    return " | ".join((m.get("text") or "") + (m.get("narrative") or "") for m in sent)


def _ko(world, user, v, **kw):
    from routes.vehicles import KnockoutSet, knock_out
    return asyncio.run(knock_out(str(world["camp"].id), str(v.id), KnockoutSet(**kw), world["db"], user))


# ---------------------------------------------------------------- the called shot
def test_a_landed_called_shot_costs_no_dp_and_prompts_only_the_story_weaver(world):
    v = world["vehicle"](level=5)
    raider = world["person"]("Saboteur", npc=True, pp=3, edge=1)
    start = v.dp
    sent, private = _disable(world, raider, v)               # 6 + 3 + 1 = 10 vs 1 + 0 + Edge5 = 6: lands
    assert v.dp == start
    assert "lands" in _text(sent)
    prompts = [m for m in private if m.get("type") == "vehicle_disable_prompt"]
    assert len(prompts) == 1 and prompts[0]["vehicle_id"] == str(v.id)
    assert not any(m.get("type") == "vehicle_disable_prompt" for m in sent), "players are never sent the prompt"


def test_a_missed_called_shot_prompts_nobody(world):
    v = world["vehicle"](level=5)
    raider = world["person"]("Saboteur", npc=True, pp=0, edge=0)
    sent, private = _disable(world, raider, v, atk=1, defense=6)
    assert "misses" in _text(sent)
    assert not any(m.get("type") == "vehicle_disable_prompt" for m in private)


def test_a_called_shot_card_says_called_shot_not_attack(world):
    v = world["vehicle"](level=5)
    raider = world["person"]("Saboteur", npc=True)
    sent, _ = _disable(world, raider, v)
    card = next(m for m in sent if m.get("type") == "combat_result")
    assert card["technique"] == "Called shot" and card["damage"] == 0


def test_disable_only_works_on_vehicles(world):
    foe = world["person"]("Guard", npc=True, dp=20)
    raider = world["person"]("Saboteur", npc=True)
    sent, _ = _disable(world, raider, foe)
    assert foe.dp == 20 and "called shot at a vehicle" in _text(sent)


def test_a_crew_member_makes_the_called_shot_with_the_vehicles_weapon_and_edge(world):
    mine = world["vehicle"](level=5)
    theirs = world["vehicle"](level=5)
    gunner = world["person"]("Gunner", pp=3, edge=0)
    world["crew"](mine, "gunner", gunner)
    sent, private = _disable(world, gunner, theirs, atk=2, defense=3)   # 2 + 3 + vehicle Edge 5 = 10 vs 3 + 0 + 5 = 8: lands
    assert any(m.get("type") == "vehicle_disable_prompt" for m in private)


# ---------------------------------------------------------------- the Story Weaver's choice
def test_the_sw_knocks_out_a_system_for_two_rounds_and_it_cannot_fire(world):
    v = world["vehicle"](level=7)
    world["system"](v, 1)
    gunner = world["person"]("Gunner", ip=3)
    foe = world["person"]("Drone", npc=True, dp=100)
    world["crew"](v, "gunner", gunner)
    out = _ko(world, world["sw"], v, kind="system", slot=1)
    assert out["knockouts"] == [{"id": out["knockouts"][0]["id"], "kind": "system", "slot": 1, "rounds_left": 2, "name": "Laser Array"}]
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[4]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, {"type": "ability_cast", "raw_command": f"/laser @[{foe.name}]",
                        "speaker_id": str(gunner.id), "speaker_type": "pc"}, None, world["pl"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert foe.dp == 100 and "knocked out" in _text(sent) and "2 more rounds" in _text(sent)
    assert v.current_uses == v.max_uses_per_encounter, "a refused cast costs nothing"


def test_a_knockout_wears_off_after_two_rounds(world):
    from backend.buffs import tick_round
    v = world["vehicle"](level=7)
    world["system"](v, 1)
    _ko(world, world["sw"], v, kind="system", slot=1)
    tick_round(world["db"], world["camp"].id)
    world["db"].commit()
    from backend.vehicles import vehicle_dict
    assert vehicle_dict(world["db"], v)["knockouts"][0]["rounds_left"] == 1
    tick_round(world["db"], world["camp"].id)
    world["db"].commit()
    assert vehicle_dict(world["db"], v)["knockouts"] == []


def test_movement_can_be_knocked_out_and_shows_on_the_card(world):
    v = world["vehicle"]()
    out = _ko(world, world["sw"], v, kind="movement")
    assert out["knockouts"][0]["kind"] == "movement" and out["knockouts"][0]["name"] == "Movement" and out["knockouts"][0]["rounds_left"] == 2


def test_knocking_out_the_same_thing_again_restarts_the_timer_not_stacks(world):
    from backend.buffs import tick_round
    v = world["vehicle"]()
    _ko(world, world["sw"], v, kind="movement")
    tick_round(world["db"], world["camp"].id)
    world["db"].commit()
    out = _ko(world, world["sw"], v, kind="movement")
    assert len(out["knockouts"]) == 1 and out["knockouts"][0]["rounds_left"] == 2


def test_a_knocked_out_system_does_not_stop_the_others(world):
    v = world["vehicle"](level=7)
    world["system"](v, 1, macro="/laser", name="Laser")
    world["system"](v, 2, macro="/shield", name="Shield", effect="buff", power="PP")
    op = world["person"]("Crew", pp=3)
    world["crew"](v, "gunner", op)
    _ko(world, world["sw"], v, kind="system", slot=1)
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[4]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, {"type": "ability_cast", "raw_command": "/shield", "speaker_id": str(op.id),
                        "speaker_type": "pc"}, None, world["pl"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    assert any(m.get("type") == "ability_cast" for m in sent)


def test_the_sw_can_restore_a_system_early(world):
    from routes.vehicles import restore_knockout
    v = world["vehicle"](level=7)
    world["system"](v, 1)
    out = _ko(world, world["sw"], v, kind="system", slot=1)
    back = asyncio.run(restore_knockout(str(world["camp"].id), str(v.id), out["knockouts"][0]["id"], world["db"], world["sw"]))
    assert back["knockouts"] == []
    with pytest.raises(HTTPException) as e:
        asyncio.run(restore_knockout(str(world["camp"].id), str(v.id), out["knockouts"][0]["id"], world["db"], world["sw"]))
    assert e.value.status_code == 404


def test_only_the_sw_can_knock_out_or_restore(world):
    from routes.vehicles import restore_knockout
    v = world["vehicle"]()
    with pytest.raises(HTTPException) as e:
        _ko(world, world["pl"], v, kind="movement")
    assert e.value.status_code == 403
    out = _ko(world, world["sw"], v, kind="movement")
    with pytest.raises(HTTPException) as e:
        asyncio.run(restore_knockout(str(world["camp"].id), str(v.id), out["knockouts"][0]["id"], world["db"], world["pl"]))
    assert e.value.status_code == 403


def test_a_system_knockout_needs_an_installed_system(world):
    v = world["vehicle"](level=7)
    with pytest.raises(HTTPException) as e:
        _ko(world, world["sw"], v, kind="system", slot=3)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _ko(world, world["sw"], v, kind="system")
    assert e.value.status_code == 400


def test_a_knockout_changes_no_dp_and_no_stat_math(world):
    from backend.buffs import effect_modifier
    v = world["vehicle"](level=7)
    start = v.dp
    _ko(world, world["sw"], v, kind="movement")
    world["db"].expire_all()
    assert v.dp == start
    for stat in ("pp", "ip", "sp"):
        assert effect_modifier(world["db"], v.id, stat, extra_types=("attack", "defense")) == 0


def test_the_engineers_repair_mentions_what_is_still_offline(world):
    from routes import campaign_websocket as cw
    v = world["vehicle"](level=5, dp=3)
    world["system"](v, 1, name="Laser Array")
    eng = world["person"]("Engineer", ip=3)
    world["crew"](v, "engineer", eng)
    _ko(world, world["sw"], v, kind="system", slot=1)
    sent = []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[2]):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command", "raw_command": "/repair",
                        "attacker_id": str(eng.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    assert "Offline: Laser Array" in _text(sent)


def test_knockouts_end_with_the_encounter(world):
    from backend.models import Encounter
    from backend.vehicles import vehicle_dict
    from routes import campaign_websocket as cw
    v = world["vehicle"]()
    _ko(world, world["sw"], v, kind="movement")
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
    assert vehicle_dict(world["db"], v)["knockouts"] == []


def test_the_page_wires_the_called_shot_and_the_knockout_controls():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "game.html"), encoding="utf-8").read()
    for needle in ("function knockOutVehicle", "function restoreVehicleKnockout", "vehicle_disable_prompt", "startsWith('/disable')", "/knockouts"):
        assert needle in html, needle
