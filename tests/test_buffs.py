"""
Buffs and debuffs under rules v3.1 (Phase 4).

- Tied to a stat: a buff or debuff only changes rolls that use that stat.
- One buff and one debuff per stat per target; a new one replaces the old; both apply (a +3 and a -2 leave +1).
- Last 2 rounds, counted per ROUND (the cast round and the next), not on each character's own turn.
- A debuff is resisted with 1d6 + the same stat + Edge, not the Defense Die.
- Spell rolls actually carry the caster's and the target's effects (before, only basic attacks did).
"""
import asyncio
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_buffs.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, ActiveEffect, Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Buff test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name):
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id,
                      campaign_id=camp.id, level=2, pp=2, ip=3, sp=1, dp=20, max_dp=20, edge=1,
                      attack_style="1d6", defense_die="1d6", max_uses_per_encounter=40, current_uses=40)
        db.add(c)
        db.commit()
        return c

    def ability(c, macro, effect, die="1d6", stat="IP", slot=1, debuff_stat=None):
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=slot, ability_type="spell",
                       display_name=macro.strip("/").title(), macro_command=macro, power_source=stat,
                       effect_type=effect, die=die, debuff_stat=debuff_stat, max_uses=9, uses_remaining=9))
        db.commit()

    def target(name, defense_die="1d12"):
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      level=1, pp=2, ip=2, sp=2, dp=500, max_dp=500, edge=0, attack_style="1d4",
                      defense_die=defense_die)
        db.add(d)
        db.commit()
        return d

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, ability=ability, target=target, tag=tag,
               ActiveEffect=ActiveEffect)
    db.close()


def _effects(world, char):
    world["db"].expire_all()
    return world["db"].query(world["ActiveEffect"]).filter_by(character_id=char.id).all()


def _add(world, char, modifier, stat, name="fx", rounds=2):
    from backend.buffs import add_effect
    add_effect(world["db"], campaign_id=world["camp"].id, character_id=char.id, name=name, modifier=modifier,
               modifier_type=stat, duration_rounds=rounds, applied_by="test")
    world["db"].commit()


# ---- the stat rules ---------------------------------------------------------------------------------------

def test_a_buff_and_a_debuff_on_the_same_stat_net_out(world):
    from backend.buffs import effect_modifier
    c = world["pc"]("Net")
    _add(world, c, +3, "ip")
    _add(world, c, -2, "ip")
    assert effect_modifier(world["db"], c.id, "ip") == 1


def test_an_effect_only_changes_rolls_that_use_its_stat(world):
    from backend.buffs import effect_modifier
    c = world["pc"]("Stat")
    _add(world, c, -2, "sp")
    assert effect_modifier(world["db"], c.id, "sp") == -2
    assert effect_modifier(world["db"], c.id, "pp") == 0 and effect_modifier(world["db"], c.id, "ip") == 0


def test_a_new_buff_replaces_the_old_one_and_a_new_debuff_replaces_the_old_debuff(world):
    from backend.buffs import effect_modifier
    c = world["pc"]("Replace")
    _add(world, c, +1, "pp", "old buff")
    _add(world, c, -3, "pp", "old debuff")
    _add(world, c, +2, "pp", "new buff")                       # replaces the +1, keeps the -3
    assert sorted(e.name for e in _effects(world, c)) == ["new buff", "old debuff"]
    _add(world, c, -1, "pp", "new debuff")                     # replaces the -3 even though it is weaker
    assert sorted(e.name for e in _effects(world, c)) == ["new buff", "new debuff"]
    assert effect_modifier(world["db"], c.id, "pp") == +1


def test_other_stats_and_other_targets_are_not_replaced(world):
    c, d = world["pc"]("Keep"), world["pc"]("Other")
    _add(world, c, +2, "pp"); _add(world, c, +2, "ip"); _add(world, d, +2, "pp")
    _add(world, c, +1, "pp")
    assert sorted((e.modifier_type, e.modifier) for e in _effects(world, c)) == [("ip", 2), ("pp", 1)]
    assert [(e.modifier_type, e.modifier) for e in _effects(world, d)] == [("pp", 2)]


def test_a_custom_effect_applies_to_every_roll(world):
    from backend.buffs import effect_modifier
    c = world["pc"]("Custom")
    _add(world, c, -1, "custom")
    assert all(effect_modifier(world["db"], c.id, s) == -1 for s in ("pp", "ip", "sp"))


def test_only_the_strongest_buff_and_debuff_count_if_old_rows_pile_up(world):
    """Rows from before v3.1 could stack. They are not summed."""
    from backend.buffs import effect_modifier
    from backend.models import ActiveEffect
    c = world["pc"]("Legacy")
    for m in (+1, +3, -1, -2):
        world["db"].add(ActiveEffect(campaign_id=world["camp"].id, character_id=c.id, name="old", modifier=m,
                                     modifier_type="ip", duration_rounds=3, applied_by="x"))
    world["db"].commit()
    assert effect_modifier(world["db"], c.id, "ip") == 3 + -2


# ---- duration: 2 rounds, counted per round -----------------------------------------------------------------

def test_an_effect_lasts_the_cast_round_and_the_next(world):
    from backend.buffs import tick_round
    c = world["pc"]("Timer")
    _add(world, c, +2, "ip", rounds=2)                         # cast during round N
    assert tick_round(world["db"], world["camp"].id) == []     # round N+1 starts: still here
    world["db"].commit()
    assert [e.duration_rounds for e in _effects(world, c)] == [1]
    expired = tick_round(world["db"], world["camp"].id)        # round N+2 starts: gone
    world["db"].commit()
    assert len(expired) >= 1 and _effects(world, c) == []


def test_ticking_is_once_per_round_for_everyone_not_per_turn(world):
    """next_turn used to tick only the effects on the character whose turn just ended."""
    from routes import campaign_websocket as cw
    from backend.models import Encounter, InitiativeRoll
    a, b = world["pc"]("TurnA"), world["pc"]("TurnB")
    _add(world, a, +2, "ip", rounds=2)
    _add(world, b, -1, "pp", rounds=2)
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True, round_number=1, current_turn_index=0)
    world["db"].add(enc)
    world["db"].commit()
    for i, ch in enumerate((a, b)):
        world["db"].add(InitiativeRoll(id=uuid.uuid4(), encounter_id=enc.id, character_id=ch.id, name=ch.name,
                                       roll_result=20 - i))
    world["db"].commit()

    class WS:
        async def send_json(self, _m):
            pass

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        # A's turn ends: same round, nothing ticks (B's effect must NOT lose a round just because A acted)
        asyncio.run(cw.advance_turn(world["camp"].id, world["sw"].id, world["db"], WS()))
        assert [e.duration_rounds for e in _effects(world, a)] == [2]
        assert [e.duration_rounds for e in _effects(world, b)] == [2]
        # B's turn ends: the round wraps, so BOTH effects tick once
        asyncio.run(cw.advance_turn(world["camp"].id, world["sw"].id, world["db"], WS()))
    finally:
        cw.manager.broadcast = original
    assert [e.duration_rounds for e in _effects(world, a)] == [1]
    assert [e.duration_rounds for e in _effects(world, b)] == [1]
    world["db"].expire_all()
    world["db"].query(InitiativeRoll).filter_by(encounter_id=enc.id).delete()
    world["db"].delete(world["db"].get(Encounter, enc.id))
    world["db"].commit()


# ---- the rolls ----------------------------------------------------------------------------------------------

def _cast(world, caster, command, dice):
    """Cast with scripted dice; returns (card, requested_die_strings)."""
    from routes import campaign_websocket as cw
    sent, asked = [], []
    seq = iter(dice)

    def fake_roll(die, *_a, **_k):
        asked.append(die)
        return [next(seq)]

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command, "speaker_id": str(caster.id), "speaker_type": "pc"}
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=fake_roll):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, world["player"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return next((m for m in sent if m.get("type") == "ability_cast"), None), asked


def test_a_debuff_is_resisted_with_1d6_not_the_defense_die(world):
    caster, t = world["pc"]("Hex"), world["target"]("Armored", defense_die="1d12")
    world["ability"](caster, "/fear", "debuff", die="1d8", stat="IP")
    card, asked = _cast(world, caster, f"/fear @[{t.name}]", dice=[6, 2])      # cast 6, resist 2
    assert asked == ["1d8", "1d6"], asked                                       # NOT the target's 1d12
    r = card["results"][0]
    assert r["success"] and r["defense_breakdown"].startswith("1d6 = [2]")      # 6+3+1=10 vs 2+IP2+0=4
    effs = _effects(world, t)
    assert [(e.modifier_type, e.modifier, e.duration_rounds) for e in effs] == [("ip", -2, 2)]   # 1d8 is -2, 2 rounds


def test_a_buffed_caster_and_a_debuffed_target_change_a_spell_roll(world):
    caster, t = world["pc"]("Boosted"), world["target"]("Weakened", defense_die="1d4")
    world["ability"](caster, "/bolt", "damage", die="1d6", stat="IP")
    base, _ = _cast(world, caster, f"/bolt @[{t.name}]", dice=[4, 2])           # 4+3+1=8 vs 2+2+0=4 -> 4
    assert base["results"][0]["damage"] == 4 and "Effects" not in base["results"][0]["attack_breakdown"]
    _add(world, caster, +2, "ip")                                              # caster buffed on IP
    _add(world, t, -1, "ip")                                                   # target debuffed on IP
    card, _ = _cast(world, caster, f"/bolt @[{t.name}]", dice=[4, 2])          # 8+2=10 vs 4-1=3 -> 7
    r = card["results"][0]
    assert r["damage"] == 7
    assert "Effects(+2)" in r["attack_breakdown"] and "Effects(-1)" in r["defense_breakdown"]


def test_a_buff_on_another_stat_does_not_change_the_spell(world):
    caster, t = world["pc"]("WrongStat"), world["target"]("Plain", defense_die="1d4")
    world["ability"](caster, "/zap", "damage", die="1d6", stat="IP")
    _add(world, caster, +5, "pp")                                              # Physical buff, spell is Intellect
    card, _ = _cast(world, caster, f"/zap @[{t.name}]", dice=[4, 2])
    assert card["results"][0]["damage"] == 4 and "Effects" not in card["results"][0]["attack_breakdown"]


def test_casting_a_second_buff_replaces_the_first_on_the_same_stat(world):
    caster = world["pc"]("Buffer")
    world["ability"](caster, "/shield", "buff", die="1d8", stat="PP", slot=1)        # +2 PP
    world["ability"](caster, "/might", "buff", die="1d12", stat="PP", slot=2)        # +3 PP
    _cast(world, caster, "/shield @[" + caster.name + "]", dice=[])
    assert [(e.modifier, e.name) for e in _effects(world, caster)] == [(2, "Shield")]
    _cast(world, caster, "/might @[" + caster.name + "]", dice=[])
    assert [(e.modifier, e.name) for e in _effects(world, caster)] == [(3, "Might")]   # replaced, not 5
