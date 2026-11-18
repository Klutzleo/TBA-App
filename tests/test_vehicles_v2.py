"""
Vehicles V2 (rules v3.1.1): whoever operates a vehicle attacks with its weapon die and Edge, a vehicle defends with its defense die
+ the crew member's PP + its own Edge, damage goes to the vehicle's DP (0 = disabled, -10 = critical, never The Calling), and an
operator's maneuver (a stat roll) uses the vehicle's Edge.
"""
import asyncio
import itertools
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vehicles_v2.db")
os.environ.setdefault("API_KEY", "devkey")

_counter = itertools.count(1)


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, Campaign, CampaignMembership, Character, InventoryItem, User, VehicleCrew
    from backend.vehicles import apply_level
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
    pl = User(id=uuid.uuid4(), email=f"pl_{tag}@example.com", username=f"pl_{tag}", hashed_password="x")
    db.add_all([sw, pl])
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name="Vehicle combat", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=pl.id, role="player"))
    db.commit()

    def person(name, npc=False, pp=3, edge=1, **kw):
        fields = dict(level=2, ip=2, sp=2, dp=20, max_dp=20, attack_style="1d6", defense_die="1d4", max_uses_per_encounter=10, current_uses=10)
        fields.update(kw)
        c = Character(id=uuid.uuid4(), name=f"{name}{next(_counter)} {tag}", owner_id=str(sw.id if npc else pl.id),
                      user_id=None if npc else pl.id, campaign_id=camp.id, is_npc=npc, pp=pp, edge=edge, **fields)
        db.add(c)
        db.commit()
        return c

    def vehicle(level=5, dp=None, **kw):
        v = Character(id=uuid.uuid4(), name=f"Vessel{next(_counter)} {tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      is_vehicle=True, level=level, pp=0, ip=0, sp=0, dp=0, max_dp=0, edge=0, bap=0, attack_style="1d4",
                      defense_die="1d4", max_uses_per_encounter=0, current_uses=0, status="active")
        apply_level(v, level)
        if dp is not None:
            v.dp = dp
        for k, val in kw.items():
            setattr(v, k, val)
        db.add(v)
        db.commit()
        return v

    def crew(v, station, c):
        db.add(VehicleCrew(id=uuid.uuid4(), vehicle_id=v.id, character_id=c.id, station=station))
        db.commit()

    yield dict(db=db, camp=camp, sw=sw, pl=pl, person=person, vehicle=vehicle, crew=crew, tag=tag, Ability=Ability,
               InventoryItem=InventoryItem, Character=Character)
    db.close()


def _attack(world, attacker, target, atk=6, defense=1):
    from routes import campaign_websocket as cw
    sent, dice_calls = [], []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    async def fake_broadcast(_cid, m):
        sent.append(m)

    def fake_dice(notation, *a, **k):
        dice_calls.append(notation)
        return [atk]

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("backend.roll_logic.roll_dice", side_effect=fake_dice), \
                mock.patch("backend.roll_logic.roll_die", return_value=defense):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command",
                        "raw_command": f"/attack @[{target.name}]", "attacker_id": str(attacker.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent, dice_calls


def _texts(sent):
    return " | ".join((m.get("text") or "") for m in sent)


# ---------------------------------------------------------------- attacking from a vehicle
def test_an_operator_attacks_with_the_vehicles_weapon_die_and_edge(world):
    v = world["vehicle"](level=5)                       # Edge 5, weapon 1d8
    pilot = world["person"]("Ace", pp=3, edge=1, weapon_bonus=2)
    foe = world["person"]("Drone", npc=True, pp=2, edge=0, dp=30)
    on_foot, _ = _attack(world, pilot, foe)             # 6 + PP3 + Edge1 = 10 vs 1 + 2 + 0 = 3: 7
    assert foe.dp == 23
    world["crew"](v, "operator", pilot)
    _sent, dice = _attack(world, pilot, foe)            # 6 + PP3 + vehicle Edge 5 = 14 vs 3: 11
    assert foe.dp == 23 - 11
    assert "1d8" in dice, "the vehicle's weapon die is rolled, not the character's own"


def test_a_gunner_attacks_the_same_way(world):
    v = world["vehicle"](level=3)                       # Edge 3
    gun = world["person"]("Gunner", pp=2, edge=0)
    foe = world["person"]("Pirate", npc=True, pp=2, edge=0, dp=30)
    world["crew"](v, "gunner", gun)
    _attack(world, gun, foe)                            # 6 + 2 + 3 = 11 vs 3: 8
    assert foe.dp == 22


@pytest.mark.parametrize("station", ["defense_officer", "captain", "pilot", "engineer"])
def test_a_station_that_does_not_attack_cannot_attack(world, station):
    v = world["vehicle"]()
    c = world["person"]("Crew")
    foe = world["person"]("Target", npc=True, dp=30)
    world["crew"](v, station, c)
    sent, _ = _attack(world, c, foe)
    assert foe.dp == 30 and "doesn't attack" in _texts(sent)


def test_a_disabled_vehicle_cannot_attack(world):
    v = world["vehicle"](dp=0)
    pilot = world["person"]("Stranded")
    foe = world["person"]("Target", npc=True, dp=30)
    world["crew"](v, "operator", pilot)
    sent, _ = _attack(world, pilot, foe)
    assert foe.dp == 30 and "disabled" in _texts(sent)


def test_a_vehicle_attacks_through_its_crew_not_by_itself(world):
    v = world["vehicle"]()
    foe = world["person"]("Target", npc=True, dp=30)
    sent, _ = _attack(world, v, foe)
    assert foe.dp == 30 and "through its crew" in _texts(sent)


# ---------------------------------------------------------------- defending as a vehicle
def test_a_vehicle_defends_with_its_die_the_crews_pp_and_its_own_edge(world):
    v = world["vehicle"](level=5)                       # defense 1d8, Edge 5
    op = world["person"]("Driver", pp=3, edge=0)
    foe = world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    world["crew"](v, "operator", op)
    start = v.dp
    _attack(world, foe, v)                              # 6 + 3 + 1 = 10 vs 1 + PP3 + Edge5 = 9: 1 damage
    assert v.dp == start - 1


def test_an_unmanned_vehicle_defends_with_no_character_stat(world):
    v = world["vehicle"](level=5)
    foe = world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    start = v.dp
    _attack(world, foe, v)                              # 10 vs 1 + 0 + Edge5 = 6: 4 damage
    assert v.dp == start - 4


def test_the_defense_officer_defends_when_there_is_one(world):
    v = world["vehicle"](level=5)
    op, officer = world["person"]("Pilot", pp=3), world["person"]("Officer", pp=1)
    foe = world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    world["crew"](v, "gunner", op)
    world["crew"](v, "defense_officer", officer)
    start = v.dp
    _attack(world, foe, v)                              # 10 vs 1 + officer PP1 + Edge5 = 7: 3 damage
    assert v.dp == start - 3


def test_a_disabled_vehicle_gets_no_crew_stat_on_defense(world):
    v = world["vehicle"](level=5, dp=0)
    op = world["person"]("Driver", pp=3)
    world["crew"](v, "operator", op)
    foe = world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    _attack(world, foe, v)                              # 10 vs 1 + 0 + 5 = 6: 4 damage
    assert v.dp == -4


# ---------------------------------------------------------------- DP states
def test_zero_dp_disables_and_minus_ten_is_critical_and_there_is_no_calling(world):
    v = world["vehicle"](level=5, dp=2)
    foe = world["person"]("Raider", npc=True, pp=3, edge=1, dp=20)
    sent, _ = _attack(world, foe, v)                    # 4 damage: -2
    assert v.dp == -2 and "disabled" in _texts(sent) and "critically" not in _texts(sent)
    assert not v.in_calling
    sent, _ = _attack(world, foe, v, atk=16)            # 16 + 3 + 1 = 20 vs 6: 14 damage: -16
    assert v.dp == -16 and "critically damaged" in _texts(sent)
    assert not v.in_calling and "knocked out" not in _texts(sent)
    assert any(m.get("type") == "vehicles_changed" for m in sent)
    sent, _ = _attack(world, foe, v)                    # a critical vehicle is the Story Weaver's to rule on
    assert v.dp == -16 and "critically damaged" in _texts(sent)


def test_a_disabled_vehicle_can_still_be_hit(world):
    v = world["vehicle"](dp=0)
    foe = world["person"]("Raider", npc=True, dp=20)
    sent, _ = _attack(world, foe, v)
    assert v.dp < 0 and "already unconscious" not in _texts(sent)


def test_the_announcements_fire_once_not_every_hit(world):
    v = world["vehicle"](level=5, dp=-3)
    foe = world["person"]("Raider", npc=True, dp=20)
    sent, _ = _attack(world, foe, v)
    assert "disabled!" not in _texts(sent), "it was already disabled before this hit"


# ---------------------------------------------------------------- maneuvers
def _stat_roll(world, character, stat="PP", die=4):
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
            asyncio.run(cw.handle_stat_check(world["camp"].id, {"stat": stat, "character_id": str(character.id)},
                                             world["sw"].id, WS(), world["db"]))
    finally:
        cw.manager.broadcast = original
    return next(m for m in sent if m.get("type") == "stat_roll")


def test_an_operators_maneuver_uses_the_vehicles_edge(world):
    v = world["vehicle"](level=7)                       # Edge 7
    pilot = world["person"]("Stunt", pp=3, edge=1)
    before = _stat_roll(world, pilot)                   # 4 + 3 + 1
    assert before["total"] == 8
    world["crew"](v, "operator", pilot)
    after = _stat_roll(world, pilot)                    # 4 + 3 + vehicle Edge 7
    assert after["total"] == 14 and after["edge"] == 7


def test_only_the_operators_rolls_swap_in_the_vehicles_edge(world):
    v = world["vehicle"](level=7)
    gun = world["person"]("Gunner", pp=3, edge=1)
    world["crew"](v, "gunner", gun)
    assert _stat_roll(world, gun)["total"] == 8


# ---------------------------------------------------------------- no healing a vehicle by spell, potion or Combo
def test_a_heal_spell_cannot_repair_a_vehicle(world):
    from routes import campaign_websocket as cw
    h = world["person"]("Healer")
    world["db"].add(world["Ability"](id=uuid.uuid4(), character_id=h.id, slot_number=1, ability_type="spell", display_name="Mend",
                                     macro_command="/mend", power_source="IP", effect_type="heal", die="1d6", max_uses=9, uses_remaining=9))
    world["db"].commit()
    v = world["vehicle"](level=5, dp=3)
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[4]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, {"type": "ability_cast", "raw_command": f"/mend @[{v.name}]",
                                                                  "speaker_id": str(h.id), "speaker_type": "pc"}, None, world["pl"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    card = next(m for m in sent if m.get("type") == "ability_cast")
    assert not card["results"][0]["success"] and "vehicle" in card["results"][0]["message"] and v.dp == 3


def test_a_potion_cannot_repair_a_vehicle(world):
    from fastapi import HTTPException
    from routes.character_fastapi import use_inventory_item
    owner = world["person"]("Holder")
    item = world["InventoryItem"](id=uuid.uuid4(), character_id=owner.id, campaign_id=world["camp"].id, name="Potion",
                                  item_type="consumable", quantity=1, tier=3, effect_type="heal")
    world["db"].add(item)
    world["db"].commit()
    v = world["vehicle"](dp=3)
    with pytest.raises(HTTPException) as e:
        asyncio.run(use_inventory_item(str(owner.id), str(item.id), {"target_id": str(v.id)}, current_user=world["pl"], db=world["db"]))
    assert "vehicle" in e.value.detail
    world["db"].expire_all()
    assert v.dp == 3


def test_a_crew_member_cannot_attack_their_own_vehicle(world):
    v = world["vehicle"]()
    gun = world["person"]("Mutineer")
    world["crew"](v, "gunner", gun)
    start = v.dp
    sent, _ = _attack(world, gun, v)
    assert v.dp == start and "own vehicle" in _texts(sent)


def test_the_game_page_offers_vehicles_as_attack_targets():
    html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "game.html"), encoding="utf-8").read()
    assert "type: 'Vehicle'" in html and "campaignVehicles || []" in html
