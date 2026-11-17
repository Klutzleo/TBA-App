"""
Ascension (levels 11-15) under rules v3.1 (Phase 9).

- The level cap is 15 for characters and NPCs; Allies stop at 10. DP 28 to 36, Edge up to +7, BAP up to +8.
- Slot N gains a secondary effect at level 10 + N. It is part of the same activation: no extra use, no second roll. A debuff
  lands automatically on a hit and a new one on the same stat replaces the old. It never deals damage.
- The Calling: the Story Weaver's die gets +1 at levels 13-14 and +2 at 15.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ascension.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import ascension as A  # noqa: E402


def test_unlock_levels_and_validation():
    assert [A.secondary_unlock_level(s) for s in range(1, 6)] == [11, 12, 13, 14, 15]
    assert A.secondary_unlocked(11, 1) and not A.secondary_unlocked(10, 1) and not A.secondary_unlocked(14, 5)
    assert A.normalize_secondary(None) is None and A.normalize_secondary({}) is None
    assert A.normalize_secondary({"kind": "debuff", "stat": "IP", "strength": 9, "note": " fear "}) == {
        "kind": "debuff", "stat": "ip", "strength": 4, "note": "fear"}
    assert A.normalize_secondary({"kind": "buff", "stat": "pp", "strength": 0})["strength"] == 1
    assert A.normalize_secondary({"kind": "note", "note": "heals a little"})["kind"] == "note"
    for bad in ({"kind": "damage", "stat": "ip"}, {"kind": "debuff", "stat": "xx"}, {"kind": "note"}, "junk"):
        with pytest.raises(ValueError):
            A.normalize_secondary(bad)


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
    camp = Campaign(id=uuid.uuid4(), name="Ascension test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, level=11, **kw):
        kw.setdefault("dp", 30)
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id,
                      campaign_id=camp.id, level=level, pp=2, ip=3, sp=1, max_dp=36, edge=5, bap=6,
                      attack_style="1d12", defense_die="1d12", max_uses_per_encounter=13, current_uses=13, **kw)
        db.add(c)
        db.commit()
        return c

    def ability(c, effect, slot=1, secondary=None, stat="IP", die="1d6", name=None, aoe=False):
        a = Ability(id=uuid.uuid4(), character_id=c.id, slot_number=slot, ability_type="spell",
                    display_name=name or f"{effect.title()}{slot}", macro_command=f"/{effect}{slot}", power_source=stat,
                    effect_type=effect, die=die, is_aoe=aoe, max_uses=9, uses_remaining=9, secondary_effect=secondary)
        db.add(a)
        db.commit()
        return a

    def target(name, defense_die="1d4", **kw):
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      level=1, pp=1, ip=1, sp=1, dp=500, max_dp=500, edge=0, attack_style="1d4", defense_die=defense_die, **kw)
        db.add(d)
        db.commit()
        return d

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, ability=ability, target=target, tag=tag,
               ActiveEffect=ActiveEffect)
    db.close()


def _cast(world, caster, command, dice):
    from routes import campaign_websocket as cw
    seq = iter(dice)
    asked, sent = [], []

    def fake_roll(die, *_a, **_k):
        asked.append(die)
        return [next(seq)]

    async def fake_broadcast(_cid, m):
        sent.append(m)

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


def _effects(world, c):
    world["db"].expire_all()
    return world["db"].query(world["ActiveEffect"]).filter_by(character_id=c.id).all()


def test_a_debuff_secondary_lands_automatically_on_a_hit_with_no_extra_use_or_roll(world):
    c, t = world["pc"]("Scalelord"), world["target"]("Raider")
    world["ability"](c, "damage", secondary={"kind": "debuff", "stat": "ip", "strength": 2, "note": "the flame carries a dragon's will"})
    card, asked = _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])        # a hit
    assert card["results"][0]["damage"] > 0
    assert asked == ["1d6", "1d4"], "no second roll: only the attack die and the target's defense die"
    assert c.current_uses == 12, "one use for the whole activation"
    fx = _effects(world, t)
    assert [(e.modifier_type, e.modifier, e.duration_rounds) for e in fx] == [("ip", -2, 2)]
    assert "dragon's will" in card["narrative"] and t.dp < 500


def test_a_miss_applies_no_secondary_effect(world):
    c, t = world["pc"]("Misser"), world["target"]("Dodger", defense_die="1d12")
    world["ability"](c, "damage", secondary={"kind": "debuff", "stat": "pp", "strength": 3})
    card, _ = _cast(world, c, f"/damage1 @[{t.name}]", dice=[1, 12])             # 1+3+5 = 9 vs 12+1 = 13: a miss
    assert card["results"][0]["damage"] == 0
    assert _effects(world, t) == []


def test_a_new_secondary_debuff_replaces_the_old_one_on_the_same_stat(world):
    c, t = world["pc"]("Replacer"), world["target"]("Twice")
    world["ability"](c, "damage", secondary={"kind": "debuff", "stat": "sp", "strength": 3})
    _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])
    from backend.models import Ability
    ab = world["db"].query(Ability).filter_by(character_id=c.id).one()
    ab.secondary_effect = {"kind": "debuff", "stat": "sp", "strength": 1}
    world["db"].commit()
    _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])
    assert [(e.modifier_type, e.modifier) for e in _effects(world, t)] == [("sp", -1)], "replaced, not stacked"


def test_a_buff_secondary_goes_to_the_caster_on_an_attack_and_to_the_one_helped_on_a_heal(world):
    c, t = world["pc"]("Buffer"), world["target"]("Foe")
    world["ability"](c, "damage", secondary={"kind": "buff", "stat": "pp", "strength": 2})
    _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])
    assert [(e.modifier_type, e.modifier) for e in _effects(world, c)] == [("pp", 2)] and _effects(world, t) == []

    healer, hurt = world["pc"]("Healer"), world["pc"]("Hurt", dp=5)
    world["ability"](healer, "heal", secondary={"kind": "buff", "stat": "sp", "strength": 1})
    _cast(world, healer, f"/heal1 @[{hurt.name}]", dice=[3])
    assert [(e.modifier_type, e.modifier) for e in _effects(world, hurt)] == [("sp", 1)] and _effects(world, healer) == []


def test_a_note_only_secondary_adds_the_note_to_the_card_and_changes_nothing(world):
    c, t = world["pc"]("Noter"), world["target"]("Plain")
    world["ability"](c, "damage", secondary={"kind": "note", "note": "the target forgets what it was doing", "stat": None, "strength": 0})
    card, _ = _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])
    assert "forgets what it was doing" in card["narrative"] and _effects(world, t) == []


def test_a_secondary_effect_is_ignored_below_its_unlock_level(world):
    c, t = world["pc"]("TooLow", level=10), world["target"]("Foe2")
    world["ability"](c, "damage", secondary={"kind": "debuff", "stat": "ip", "strength": 2})     # slot 1 needs level 11
    _cast(world, c, f"/damage1 @[{t.name}]", dice=[4, 1])
    assert _effects(world, t) == []


def test_editing_an_ability_validates_the_unlock_level_and_the_kind(world):
    from fastapi import HTTPException
    from routes.character_fastapi import patch_ability
    low, high = world["pc"]("Low", level=10), world["pc"]("High", level=11)
    a_low = world["ability"](low, "damage")
    a_high = world["ability"](high, "damage")
    heal = world["ability"](high, "heal", slot=2, name="Mend")
    good = {"secondary_effect": {"kind": "debuff", "stat": "ip", "strength": 2, "note": "fear"}}
    with pytest.raises(HTTPException) as e:
        asyncio.run(patch_ability(str(low.id), str(a_low.id), good, current_user=world["sw"], db=world["db"]))
    assert e.value.status_code == 400 and "level 11" in e.value.detail
    r = asyncio.run(patch_ability(str(high.id), str(a_high.id), good, current_user=world["sw"], db=world["db"]))
    assert r["secondary_effect"]["strength"] == 2
    with pytest.raises(HTTPException):                                  # slot 2 does not unlock until level 12
        asyncio.run(patch_ability(str(high.id), str(heal.id), {"secondary_effect": {"kind": "buff", "stat": "ip"}},
                                  current_user=world["sw"], db=world["db"]))
    high.level = 12
    world["db"].commit()
    with pytest.raises(HTTPException) as e2:                            # a debuff cannot ride a heal
        asyncio.run(patch_ability(str(high.id), str(heal.id), good, current_user=world["sw"], db=world["db"]))
    assert "attack or a debuff" in e2.value.detail
    r = asyncio.run(patch_ability(str(high.id), str(a_high.id), {"secondary_effect": None}, current_user=world["sw"], db=world["db"]))
    assert r["secondary_effect"] is None


def _calling(world, c, player_die, sw_die):
    from routes.character_fastapi import resolve_the_calling
    rolls = iter([player_die, sw_die])
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    with mock.patch("backend.roll_logic.roll_dice", side_effect=lambda *_a, **_k: [next(rolls)]):
        r = asyncio.run(resolve_the_calling(str(c.id), req, {"stat_choice": "ip"}, world["db"], world["player"]))
    world["db"].expire_all()
    return r


@pytest.mark.parametrize("level,bonus", [(10, 0), (11, 0), (12, 0), (13, 1), (14, 1), (15, 2)])
def test_the_callings_difficulty_climbs_at_ascension(world, level, bonus):
    c = world["pc"](f"Calling{level}", level=level, in_calling=True, dp=-10)
    r = _calling(world, c, player_die=1, sw_die=6)
    assert r["sw_total"] == 6 + bonus
    assert r["sw_die"] == ("1d12" if not bonus else f"1d12+{bonus}")


def test_level_caps_players_and_npcs_reach_15_allies_stop_at_10(world):
    from fastapi import HTTPException
    from routes.character_fastapi import level_up_character, set_character_level
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    c = world["pc"]("Climber", level=14, dp=30)
    r = asyncio.run(level_up_character(str(c.id), req, {"weapon_die": "1d12"}, world["db"], world["sw"]))
    assert r["new_level"] == 15 and r["new_max_dp"] == 36 and r["new_edge"] == 7 and r["new_uses_per_encounter"] == 17
    with pytest.raises(HTTPException) as e:
        asyncio.run(level_up_character(str(c.id), req, {"weapon_die": "1d12"}, world["db"], world["sw"]))
    assert "max level (15)" in e.value.detail
    r = asyncio.run(set_character_level(str(c.id), req, {"new_level": 11, "weapon_die": "1d12"}, world["db"], world["sw"]))
    assert r["new_level"] == 11
    with pytest.raises(HTTPException):
        asyncio.run(set_character_level(str(c.id), req, {"new_level": 16}, world["db"], world["sw"]))
    ally = world["pc"]("Wolf", level=10, is_ally=True, parent_character_id=c.id)
    with pytest.raises(HTTPException) as e2:
        asyncio.run(level_up_character(str(ally.id), req, {"weapon_die": "1d12"}, world["db"], world["sw"]))
    assert "max level (10)" in e2.value.detail
