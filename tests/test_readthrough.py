"""
Fixes from the final read-through of the v3.1 rules against the app.

- Potions: heal a set amount, Tier 5 is 14 (it was 12); buff potions use the +1 to +4 table and last 2 rounds (the old +1 to +6
  and "rounds equal to the modifier" are gone). A potion, like any heal, wakes someone at negative DP: up to 0 first, then it adds.
  The Story Weaver's manual heal does the same.
- Ascension "cleanse" secondary effect (the Guide's own example: a healing ability that also cleanses a debuff).
"""
import asyncio
import os
import re
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_readthrough.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import leveling  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_potion_table_matches_the_core_rules():
    t = leveling.POTION_TIERS
    assert [t[i]["heal"] for i in range(1, 7)] == [6, 8, 10, 12, 14, 16]
    assert [t[i]["modifier"] for i in range(1, 7)] == [1, 2, 2, 3, 3, 4]
    assert [t[i]["die"] for i in range(1, 7)] == ["1d6", "1d8", "1d10", "1d12", "2d6", "2d8"]
    # buff potions follow the same table as spells of that die
    assert all(t[i]["modifier"] == leveling.BUFF_DEBUFF_MODIFIER_BY_DIE[t[i]["die"]] for i in range(1, 7))


def test_backend_and_page_potion_tables_have_not_drifted():
    from routes import character_fastapi as cf
    assert cf.TIER_HEAL == {i: leveling.POTION_TIERS[i]["heal"] for i in range(1, 7)}
    assert cf.TIER_MOD == {i: leveling.POTION_TIERS[i]["modifier"] for i in range(1, 7)}
    page = open(os.path.join(ROOT, "static", "game.html"), encoding="utf-8").read()
    for name, field in (("TIER_HEAL", "heal"), ("TIER_MOD", "modifier")):
        m = re.search(r"const " + name + r"\s*=\s*\{(.*?)\}", page, re.S)
        got = {int(k): int(v) for k, v in re.findall(r"(\d+)\s*:\s*(\d+)", m.group(1))}
        assert got == {i: leveling.POTION_TIERS[i][field] for i in range(1, 7)}, name


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, ActiveEffect, Campaign, CampaignMembership, Character, InventoryItem, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Readthrough test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, **kw):
        kw.setdefault("dp", 10)
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id, campaign_id=camp.id,
                      level=11, pp=2, ip=3, sp=1, max_dp=28, edge=5, bap=6, attack_style="1d12", defense_die="1d12",
                      max_uses_per_encounter=13, current_uses=13, **kw)
        db.add(c)
        db.commit()
        return c

    def potion(c, tier, effect="heal"):
        it = InventoryItem(id=uuid.uuid4(), character_id=c.id, campaign_id=camp.id, name=f"Potion T{tier}",
                           item_type="consumable", quantity=1, tier=tier, effect_type=effect)
        db.add(it)
        db.commit()
        return it

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, potion=potion, tag=tag, Ability=Ability,
               ActiveEffect=ActiveEffect)
    db.close()


def test_a_potion_wakes_someone_at_negative_dp_then_adds_its_amount(world):
    c = world["pc"]("Down", dp=-6)
    it = world["potion"](c, 5)                                       # Tier 5: 14
    from routes.character_fastapi import use_inventory_item
    r = asyncio.run(use_inventory_item(str(c.id), str(it.id), {}, current_user=world["player"], db=world["db"]))
    world["db"].expire_all()
    assert r["value"] == 14 and c.dp == 14, "-6 comes up to 0, then +14 (it used to land on 8)"


def test_a_potion_never_goes_above_max_dp_and_a_buff_potion_lasts_two_rounds(world):
    from routes.character_fastapi import use_inventory_item
    c = world["pc"]("Full", dp=27)
    r = asyncio.run(use_inventory_item(str(c.id), str(world["potion"](c, 6).id), {}, current_user=world["player"], db=world["db"]))
    world["db"].expire_all()
    assert c.dp == 28
    b = asyncio.run(use_inventory_item(str(c.id), str(world["potion"](c, 6, "buff").id), {}, current_user=world["player"], db=world["db"]))
    assert b["effect"] == "buff" and b["value"] == 4 and b["rounds"] == 2     # +4 for 2 rounds (it was +6 for 6)


def test_the_story_weavers_manual_heal_wakes_a_downed_character_too(world):
    from routes.character_fastapi import heal_character
    c = world["pc"]("Manual", dp=-4)
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    asyncio.run(heal_character(str(c.id), req, {"amount": 5}, world["db"], world["sw"]))
    world["db"].expire_all()
    assert c.dp == 5


# ---- the cleanse secondary effect ------------------------------------------------------------------------------

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


def _add_debuff(world, c, modifier, stat, name):
    from backend.buffs import add_effect
    add_effect(world["db"], campaign_id=world["camp"].id, character_id=c.id, name=name, modifier=modifier,
               modifier_type=stat, duration_rounds=2, applied_by="x")
    world["db"].commit()


def _healer(world, secondary):
    h = world["pc"]("Healer")
    world["db"].add(world["Ability"](id=uuid.uuid4(), character_id=h.id, slot_number=1, ability_type="spell",
                                     display_name="Mend", macro_command="/mend", power_source="IP", effect_type="heal",
                                     die="1d6", max_uses=9, uses_remaining=9, secondary_effect=secondary))
    world["db"].commit()
    return h


def test_a_cleanse_removes_the_strongest_debuff_from_the_one_healed(world):
    h, t = _healer(world, {"kind": "cleanse", "stat": None, "strength": 0, "note": "the light burns it away"}), world["pc"]("Afflicted", dp=5)
    _add_debuff(world, t, -1, "pp", "Weak"); _add_debuff(world, t, -3, "ip", "Fear"); _add_debuff(world, t, +2, "sp", "Blessed")
    card = _cast(world, h, f"/mend @[{t.name}]", dice=[3])
    left = sorted((e.name, e.modifier) for e in world["db"].query(world["ActiveEffect"]).filter_by(character_id=t.id).all())
    assert left == [("Blessed", 2), ("Weak", -1)], "the strongest debuff (-3) is gone; the buff is untouched"
    assert "cleansed of Fear" in card["narrative"]


def test_a_cleanse_can_be_aimed_at_one_stat(world):
    h = _healer(world, {"kind": "cleanse", "stat": "pp", "strength": 0, "note": ""})
    t = world["pc"]("Afflicted2", dp=5)
    _add_debuff(world, t, -1, "pp", "Weak"); _add_debuff(world, t, -3, "ip", "Fear")
    _cast(world, h, f"/mend @[{t.name}]", dice=[3])
    left = [(e.name, e.modifier) for e in world["db"].query(world["ActiveEffect"]).filter_by(character_id=t.id).all()]
    assert left == [("Fear", -3)], "only the Physical debuff was cleansed"


def test_a_cleanse_only_rides_a_heal_or_a_buff(world):
    from fastapi import HTTPException
    from routes.character_fastapi import patch_ability
    c = world["pc"]("Attacker")
    ab = world["Ability"](id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name="Bolt",
                          macro_command="/bolt", power_source="IP", effect_type="damage", die="1d6", max_uses=9, uses_remaining=9)
    world["db"].add(ab)
    world["db"].commit()
    with pytest.raises(HTTPException) as e:
        asyncio.run(patch_ability(str(c.id), str(ab.id), {"secondary_effect": {"kind": "cleanse"}},
                                  current_user=world["sw"], db=world["db"]))
    assert "heal or a buff" in e.value.detail


# ---- unconscious characters cannot act; a potion cannot reach someone in The Calling -------------------------------------

def test_a_character_at_zero_dp_cannot_cast_until_healed(world):
    c, t = world["pc"]("Downed", dp=0), world["pc"]("Bystander", dp=10)
    world["db"].add(world["Ability"](id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell",
                                     display_name="Bolt", macro_command="/bolt", power_source="IP", effect_type="damage",
                                     die="1d6", max_uses=9, uses_remaining=9))
    world["db"].commit()
    card = _cast(world, c, f"/bolt @[{t.name}]", dice=[4, 1])
    assert card is None, "no spell went off"
    assert t.dp == 10 and c.current_uses == 13, "nothing hit, nothing spent"
    c.dp = 1                                                     # healed back to 1 DP: they can act again
    world["db"].commit()
    assert _cast(world, c, f"/bolt @[{t.name}]", dice=[4, 1]) is not None


def test_a_potion_cannot_heal_someone_already_in_the_calling(world):
    from fastapi import HTTPException
    from routes.character_fastapi import use_inventory_item
    c = world["pc"]("Dying", dp=-12, in_calling=True)
    it = world["potion"](c, 6)
    with pytest.raises(HTTPException) as e:
        asyncio.run(use_inventory_item(str(c.id), str(it.id), {}, current_user=world["player"], db=world["db"]))
    assert "Calling" in e.value.detail
    world["db"].expire_all()
    assert c.dp == -12
