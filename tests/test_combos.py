"""
Combos under rules v3.1 (Phase 7): the app now RESOLVES them instead of only rolling two totals.

- Each side rolls its ability with its own BAP added automatically; each costs 1 use; the Triple Combo adds +2 to every roll.
- Damage: the target defends against each activation like any spell (stat-matched), both damages apply.
- Heals add the healer's BAP and follow the once-per-person rule. Buffs and debuffs count one step higher on the buff table.
- Debuffs are resisted with 1d6 + stat + Edge. Two effects on the same stat: the stronger takes over.
- A named Combo fires once per encounter. The Triple Combo needs level 11+.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_combos.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, ActiveEffect, Bond, Campaign, CampaignMembership, Character, Encounter,
                                EncounterHeal, InitiativeRoll, PendingCombo, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, p1, p2, p3 = user("sw"), user("p1"), user("p2"), user("p3")
    camp = Campaign(id=uuid.uuid4(), name="Combo test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player"), (p3, "player")):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role))
    db.commit()

    def pc(owner, name, level=2, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(owner.id), user_id=owner.id,
                      campaign_id=camp.id, level=level, pp=2, ip=3, sp=1, dp=20, max_dp=20, edge=1, bap=2,
                      attack_style="1d6", defense_die="1d6", max_uses_per_encounter=10, current_uses=10, **kw)
        db.add(c)
        db.commit()
        return c

    def ability(c, slot, effect, die="1d6", stat="IP", name=None):
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=slot, ability_type="spell",
                       display_name=name or f"{effect.title()}{slot}", macro_command=f"/{effect}{slot}",
                       power_source=stat, effect_type=effect, die=die, max_uses=9, uses_remaining=9))
        db.commit()

    def target(name, defense_die="1d4", **kw):
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      level=1, pp=2, ip=2, sp=2, dp=100, max_dp=100, edge=0, attack_style="1d4",
                      defense_die=defense_die, **kw)
        db.add(d)
        db.commit()
        return d

    def encounter():
        for e in db.query(Encounter).filter_by(campaign_id=camp.id, is_active=True).all():
            e.is_active = False
        e = Encounter(id=uuid.uuid4(), campaign_id=camp.id, is_active=True)
        db.add(e)
        db.commit()
        return e

    def new_player(name):
        u = user(name)
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role="player"))
        db.commit()
        return u

    yield dict(db=db, camp=camp, sw=sw, p1=p1, p2=p2, p3=p3, pc=pc, ability=ability, target=target, new_player=new_player,
               encounter=encounter, tag=tag, ActiveEffect=ActiveEffect, EncounterHeal=EncounterHeal, Bond=Bond,
               InitiativeRoll=InitiativeRoll, PendingCombo=PendingCombo, Encounter=Encounter)
    db.close()


def _fire(world, a, a_slot, a_target, b, b_slot, b_target, dice, triple_with=None):
    """Resolve a two-person Combo (or a Triple if triple_with=(char, slot, target)) with scripted dice. Returns the result
    dicts of the broadcast card."""
    from routes import campaign_websocket as cw
    seq = iter(dice)
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    combo_id = uuid.uuid4()
    picks = {str(a.id): a_target, str(b.id): b_target}
    if triple_with:
        picks[str(triple_with[0].id)] = triple_with[2]
        combo = SimpleNamespace(id=combo_id, proposer_character_id=a.id, partner_a_character_id=b.id,
                                partner_b_character_id=triple_with[0].id, proposer_ability_slot=a_slot,
                                partner_a_ability_slot=b_slot, partner_b_ability_slot=triple_with[1],
                                status="holding", bond_ab=None, bond=None)
    else:
        combo = SimpleNamespace(id=combo_id, proposer_character_id=a.id, acceptor_character_id=b.id,
                                proposer_ability_slot=a_slot, acceptor_ability_slot=b_slot, status="holding", bond=None)
    cw._combo_targets[str(combo_id)] = picks
    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)]):
            asyncio.run((cw._resolve_triple_combo if triple_with else cw._resolve_combo)(world["camp"].id, combo, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    card = next(m for m in sent if m.get("type") in ("combo_resolved", "triple_combo_resolved"))
    return card


def _effects(world, char):
    world["db"].expire_all()
    return world["db"].query(world["ActiveEffect"]).filter_by(character_id=char.id).all()


def test_two_damage_activations_both_land_with_automatic_bap_and_cost_one_use_each(world):
    a, b, t = world["pc"](world["p1"], "DmgA"), world["pc"](world["p2"], "DmgB"), world["target"]("Dummy1")
    world["ability"](a, 1, "damage"); world["ability"](b, 1, "damage")
    world["encounter"]()
    # A: 4 + IP3 + Edge1 + BAP2 = 10 vs defense 1+IP2 = 3 -> 7.  B: 5 + 3 + 1 + 2 = 11 vs 2+2 = 4 -> 7
    card = _fire(world, a, 1, t.name, b, 1, t.name, dice=[4, 1, 5, 2])
    assert card["proposer"]["total"] == 10 and card["acceptor"]["total"] == 11
    assert card["proposer"]["damage"] == 7 and card["acceptor"]["damage"] == 7
    assert t.dp == 100 - 14, "both damage values apply"
    assert (a.current_uses, b.current_uses) == (9, 9), "1 use per character, from the shared pool"
    assert "7 damage" in card["proposer"]["summary"] and card["proposer"]["bap"] == 2


def test_a_combo_heal_adds_bap_and_follows_the_once_per_person_rule(world):
    a, b = world["pc"](world["p1"], "HealA"), world["pc"](world["p2"], "HealB")
    hurt = world["pc"](world["p3"], "Hurt")
    hurt.dp = 2
    world["db"].commit()
    world["ability"](a, 1, "heal"); world["ability"](b, 1, "heal")
    world["encounter"]()
    card = _fire(world, a, 1, hurt.name, b, 1, hurt.name, dice=[3, 4])
    # A heals 3+3+1+2 = 9 (BAP is in the roll): 2 -> 11. B is blocked: already healed this encounter.
    assert card["proposer"]["healing"] == 9 and hurt.dp == 11
    assert "already healed" in card["acceptor"]["summary"]


def test_a_combo_buff_counts_one_step_higher_and_the_stronger_buff_takes_over(world):
    from backend.leveling import combo_step_modifier
    assert [combo_step_modifier(d) for d in ("1d6", "1d8", "1d10", "1d12", "2d6", "2d8")] == [2, 2, 3, 3, 4, 4]
    a, b, t = world["pc"](world["p1"], "BufA"), world["pc"](world["p2"], "BufB"), world["pc"](world["p3"], "Buffed")
    world["ability"](a, 1, "buff", die="1d6", stat="PP")       # +1 normally, +2 in a Combo
    world["ability"](b, 1, "buff", die="1d12", stat="PP")      # +3 normally, +3 in a Combo
    world["encounter"]()
    card = _fire(world, a, 1, t.name, b, 1, t.name, dice=[1, 1])
    fx = _effects(world, t)
    assert [(e.modifier_type, e.modifier, e.duration_rounds) for e in fx] == [("pp", 3, 2)], "same stat: only the stronger one"
    assert "stronger" in card["proposer"]["summary"]


def test_buffs_on_different_stats_both_apply(world):
    a, b, t = world["pc"](world["p1"], "StA"), world["pc"](world["p2"], "StB"), world["pc"](world["p3"], "TwoStats")
    world["ability"](a, 1, "buff", die="1d6", stat="PP"); world["ability"](b, 1, "buff", die="1d8", stat="IP")
    world["encounter"]()
    _fire(world, a, 1, t.name, b, 1, t.name, dice=[1, 1])
    assert sorted((e.modifier_type, e.modifier) for e in _effects(world, t)) == [("ip", 2), ("pp", 2)]


def test_a_combo_debuff_is_resisted_with_1d6_and_counts_one_step_higher(world):
    from routes import campaign_websocket as cw
    a, b = world["pc"](world["p1"], "DebA"), world["pc"](world["p2"], "DebB")
    t = world["target"]("Armored", defense_die="1d12")
    world["ability"](a, 1, "debuff", die="1d6", stat="IP"); world["ability"](b, 1, "damage")
    world["encounter"]()
    asked = []
    seq = iter([5, 2, 4, 1])

    def fake_roll(die, *_a, **_k):
        asked.append(die)
        return [next(seq)]

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        combo = SimpleNamespace(id=uuid.uuid4(), proposer_character_id=a.id, acceptor_character_id=b.id,
                                proposer_ability_slot=1, acceptor_ability_slot=1, status="holding", bond=None)
        cw._combo_targets[str(combo.id)] = {str(a.id): t.name, str(b.id): t.name}
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=fake_roll):
            asyncio.run(cw._resolve_combo(world["camp"].id, combo, world["db"]))
    finally:
        cw.manager.broadcast = original
    assert asked[:2] == ["1d6", "1d6"], asked                      # the cast die, then 1d6 to resist, NOT the target's 1d12
    assert [(e.modifier_type, e.modifier) for e in _effects(world, t)] == [("ip", -2)]   # 1d6 is -1, a Combo makes it -2


def test_the_triple_combo_adds_two_to_every_roll(world):
    a, b, c = world["pc"](world["p1"], "TriA"), world["pc"](world["p2"], "TriB"), world["pc"](world["p3"], "TriC")
    t = world["target"]("Dummy3")
    for ch in (a, b, c):
        world["ability"](ch, 1, "damage")
    world["encounter"]()
    card = _fire(world, a, 1, t.name, b, 1, t.name, dice=[3, 1, 3, 1, 3, 1], triple_with=(c, 1, t.name))
    # each: 3 + IP3 + Edge1 + BAP2 + 2 = 11   (a normal Combo would be 9)
    assert [card[k]["total"] for k in ("proposer", "partner_a", "partner_b")] == [11, 11, 11]


def test_picking_an_ability_that_needs_a_target_without_one_is_refused(world):
    from routes.campaign_websocket import _combo_pick_error
    a = world["pc"](world["p1"], "Picker")
    world["ability"](a, 1, "damage"); world["ability"](a, 2, "heal")
    assert "needs a target" in _combo_pick_error(world["db"], a, world["camp"].id, 1, None)
    assert "not found" in _combo_pick_error(world["db"], a, world["camp"].id, 1, "Nobody")
    assert _combo_pick_error(world["db"], a, world["camp"].id, 2, None) is None        # a heal defaults to yourself
    a.current_uses = 0
    world["db"].commit()
    assert "no uses" in _combo_pick_error(world["db"], a, world["camp"].id, 2, None)


def test_a_named_combo_fires_only_once_per_encounter_and_the_triple_needs_level_11(world):
    from routes import campaign_websocket as cw
    u1, u2, u3 = (world["new_player"](n) for n in ("once1", "once2", "once3"))   # one character each, so "my character" is unambiguous
    a, b = world["pc"](u1, "OnceA"), world["pc"](u2, "OnceB")
    enc = world["encounter"]()
    world["db"].add(world["InitiativeRoll"](id=uuid.uuid4(), encounter_id=enc.id, character_id=a.id, name=a.name,
                                            roll_result=15))
    bond = world["Bond"](id=uuid.uuid4(), campaign_id=world["camp"].id, character_id_a=a.id, character_id_b=b.id,
                         combo_name="Ember Slam")
    world["db"].add(bond)
    world["db"].add(world["PendingCombo"](id=uuid.uuid4(), encounter_id=enc.id, campaign_id=world["camp"].id,
                                          bond_id=bond.id, proposer_character_id=a.id, acceptor_character_id=b.id,
                                          status="fired"))
    world["db"].commit()
    sent = []

    class WS:
        async def send_json(self, m):
            sent.append(m)

    asyncio.run(cw._handle_combo_propose(world["camp"].id, u1.id, {"partner_character_id": str(b.id)},
                                         WS(), world["db"]))
    assert any("already fired this encounter" in (m.get("message") or "") for m in sent), sent

    # the Triple Combo is an Ascension move (level 11+); these are level 2
    c = world["pc"](u3, "OnceC")
    sent.clear()
    asyncio.run(cw._handle_triple_combo_propose(world["camp"].id, u1.id,
                {"partner_a_character_id": str(b.id), "partner_b_character_id": str(c.id)}, WS(), world["db"]))
    assert any("level 11" in (m.get("message") or "") for m in sent), sent
