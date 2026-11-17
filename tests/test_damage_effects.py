"""
Damage Effects (poison, burning, bleeding...) under rules v3.1.

Cast like a debuff and defended the same way (1d6 + the same stat + Edge). If it lands, the target takes the spell die ONCE at
the start of their next turn, can resist it for half (beat or tie the damage with 1d6 + stat + Edge, rounded down), and it can take
them to 0 and below, all the way to -10 and The Calling. A new one replaces the old one.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_damage_effects.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, ActiveEffect, Campaign, CampaignMembership, Character, Encounter,
                                InitiativeRoll, Message, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="DoT test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, **kw):
        kw.setdefault("dp", 20)
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id,
                      campaign_id=camp.id, level=3, pp=2, ip=3, sp=1, max_dp=20, edge=1, attack_style="1d6",
                      defense_die="1d6", max_uses_per_encounter=10, current_uses=10, **kw)
        db.add(c)
        db.commit()
        return c

    def ability(c, effect="dot", die="1d6", stat="IP", name="Venom"):
        a = Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name=name,
                    macro_command="/venom", power_source=stat, effect_type=effect, die=die, max_uses=9, uses_remaining=9)
        db.add(a)
        db.commit()
        return a

    def target(name, defense_die="1d4", max_dp=30, **kw):
        kw.setdefault("dp", 30)
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      level=1, pp=2, ip=2, sp=2, max_dp=max_dp, edge=0, attack_style="1d4", defense_die=defense_die, **kw)
        db.add(d)
        db.commit()
        return d

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, ability=ability, target=target, tag=tag,
               ActiveEffect=ActiveEffect, Encounter=Encounter, InitiativeRoll=InitiativeRoll, Message=Message)
    db.close()


def _cast(world, caster, command, dice):
    from routes import campaign_websocket as cw
    seq = iter(dice)
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command, "speaker_id": str(caster.id), "speaker_type": "pc"}
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, world["player"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return next((m for m in sent if m.get("type") == "ability_cast"), None)


def _dots(world, c):
    world["db"].expire_all()
    return world["db"].query(world["ActiveEffect"]).filter_by(character_id=c.id, modifier_type="dot").all()


def test_a_landed_damage_effect_waits_for_the_targets_next_turn(world):
    c, t = world["pc"]("Poisoner"), world["target"]("Victim")
    world["ability"](c)
    card = _cast(world, c, f"/venom @[{t.name}]", dice=[5, 1])       # 5+IP3+Edge1 = 9 vs 1+IP2+0 = 3: it lands
    r = card["results"][0]
    assert r["success"] and r["dot"] is True and t.dp == 30, "no damage yet"
    fx = _dots(world, t)
    assert len(fx) == 1 and fx[0].modifier == 0 and fx[0].data["die"] == "1d6" and fx[0].data["stat"] == "IP"
    assert c.current_uses == 9, "an ordinary cast: 1 use"
    assert "start of their next turn" in card["narrative"]


def test_a_resisted_damage_effect_does_nothing(world):
    c, t = world["pc"]("Weak"), world["target"]("Tough")
    world["ability"](c)
    card = _cast(world, c, f"/venom @[{t.name}]", dice=[1, 6])       # 1+3+1 = 5 vs 6+2 = 8
    assert not card["results"][0]["success"] and _dots(world, t) == []


def test_a_new_damage_effect_replaces_the_old_one(world):
    from backend.models import Ability
    c, t = world["pc"]("Twice"), world["target"]("Doubled")
    ab = world["ability"](c)
    _cast(world, c, f"/venom @[{t.name}]", dice=[5, 1])
    ab = world["db"].query(Ability).filter_by(character_id=c.id).one()
    ab.die = "1d8"
    ab.display_name = "Fire"
    world["db"].commit()
    _cast(world, c, f"/venom @[{t.name}]", dice=[5, 1])
    fx = _dots(world, t)
    assert len(fx) == 1 and fx[0].data["die"] == "1d8" and fx[0].name == "Fire"


def test_a_summon_cannot_be_hit_by_a_damage_effect(world):
    c = world["pc"]("Hexer")
    s = world["target"]("Spirit", is_summon=True, dp=1, max_dp=1)
    world["ability"](c)
    card = _cast(world, c, f"/venom @[{s.name}]", dice=[5, 1])
    assert not card["results"][0]["success"] and "hits, not DP" in card["results"][0]["message"] and _dots(world, s) == []
    assert c.current_uses == 10, "nothing landed, nothing spent"


def _fire_at_turn_start(world, victim, dice):
    from routes import campaign_websocket as cw
    seq = iter(dice)
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    roll = SimpleNamespace(character_id=victim.id if not victim.is_npc else None,
                           npc_id=None if not victim.is_npc else uuid.uuid4(), name=victim.name)
    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)]):
            asyncio.run(cw._resolve_damage_effects_at_turn_start(world["camp"].id, world["db"], roll))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent


def _poison(world, victim, die="1d6", stat="IP"):
    from backend.buffs import add_damage_effect
    add_damage_effect(world["db"], campaign_id=world["camp"].id, character_id=victim.id, name="Venom", die=die,
                      stat=stat, caster_name="Someone")
    world["db"].commit()


def test_at_the_start_of_their_turn_the_target_takes_the_full_spell_die_once(world):
    v = world["pc"]("Hurt1", dp=20)
    _poison(world, v)
    sent = _fire_at_turn_start(world, v, dice=[6, 1])                 # damage 6; resist 1+IP3+1 = 5 < 6: full damage
    assert v.dp == 14 and _dots(world, v) == []
    ev = next(m for m in sent if m.get("type") == "damage_effect")
    assert ev["damage"] == 6 and ev["resisted"] is False and ev["old_dp"] == 20 and ev["new_dp"] == 14
    assert world["db"].query(world["Message"]).filter_by(id=ev["message_id"]).count() == 1, "saved, so it survives a refresh"
    assert _fire_at_turn_start(world, v, dice=[6, 1]) == [] and v.dp == 14, "it fired once and is gone"


def test_a_resisted_damage_effect_does_half_rounded_down(world):
    v = world["pc"]("Hurt2", dp=20)
    _poison(world, v)
    sent = _fire_at_turn_start(world, v, dice=[5, 1])                 # damage 5; resist 5 ties: beat OR tie is enough
    ev = next(m for m in sent if m.get("type") == "damage_effect")
    assert ev["resisted"] is True and ev["damage"] == 2 and v.dp == 18          # 5 // 2


def test_it_can_take_a_player_to_minus_ten_and_into_the_calling(world):
    v = world["pc"]("Hurt3", dp=-5)
    _poison(world, v, die="2d8")
    _fire_at_turn_start(world, v, dice=[8, 1])                        # the mocked roll returns one die at a time
    world["db"].expire_all()
    assert v.dp <= -10 and v.in_calling is True


def test_an_npc_is_hurt_too(world):
    n = world["target"]("Bandit", dp=30)
    _poison(world, n)
    _fire_at_turn_start(world, n, dice=[4, 1])                        # resist 1+IP2+0 = 3 < 4: full 4
    assert n.dp == 26


def test_a_character_already_in_the_calling_just_loses_the_effect(world):
    v = world["pc"]("Hurt4", dp=-12, in_calling=True)
    _poison(world, v)
    _fire_at_turn_start(world, v, dice=[6, 1])
    assert v.dp == -12 and _dots(world, v) == []


def test_it_fires_when_the_turn_advances_to_the_target(world):
    """Through the real turn order: a Damage Effect on B hurts B when the turn moves from A to B."""
    from routes import campaign_websocket as cw
    a, b = world["pc"]("TurnA"), world["pc"]("TurnB", dp=20)
    enc = world["Encounter"](id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True, round_number=1, current_turn_index=0)
    world["db"].add(enc)
    world["db"].commit()
    for ch, init in ((a, 20), (b, 10)):
        world["db"].add(world["InitiativeRoll"](id=uuid.uuid4(), encounter_id=enc.id, character_id=ch.id, name=ch.name,
                                                roll_result=init))
    world["db"].commit()
    _poison(world, b)

    class WS:
        async def send_json(self, _m):
            pass

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        # every die rolls 6: damage 6, and the resist 6 + IP3 + Edge1 = 10 beats it, so half (3) is taken
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [6]):
            asyncio.run(cw.advance_turn(world["camp"].id, world["sw"].id, world["db"], WS()))
    finally:
        cw.manager.broadcast = original
        enc.is_active = False
        world["db"].commit()
    world["db"].expire_all()
    assert b.dp == 17 and _dots(world, b) == []


def test_a_boost_that_lands_a_missed_damage_effect_puts_it_on_the_target(world):
    from routes import campaign_websocket as cw
    from routes.character_fastapi import _boost_ability_cast
    c, t = world["pc"]("Booster"), world["target"]("Boosted", defense_die="1d4")
    world["ability"](c)
    card = _cast(world, c, f"/venom @[{t.name}]", dice=[1, 5])        # 1+3+1 = 5 vs 5+2 = 7: it misses
    assert not card["results"][0]["success"] and _dots(world, t) == []
    msg = world["db"].query(world["Message"]).filter_by(id=card["message_id"]).one()

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(_boost_ability_cast(world["db"], c, msg, dict(msg.extra_data), [{"type": "bap", "bonus": 5}], 5,
                                        str(msg.id), world["player"]))
    finally:
        cw.manager.broadcast = original
    assert len(_dots(world, t)) == 1


def test_the_npc_editors_old_healing_value_still_heals(world):
    c, t = world["pc"]("OldHealer"), world["pc"]("Patient", dp=5)
    world["ability"](c, effect="healing", name="Mend")
    card = _cast(world, c, f"/venom @[{t.name}]", dice=[3])
    assert card["results"][0]["success"] and t.dp > 5
