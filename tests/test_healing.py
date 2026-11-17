"""
Healing under rules v3.1 (Phase 5).

- A heal rolls spell die + stat + Edge (+ any buff or debuff on that stat), like any other spell. It used to skip Edge.
- Once per person per encounter. Outside an encounter healing is free: no use spent, no limit.
- A heal always wakes you: at negative DP it brings you to 0 first, then adds the roll. Never above max DP.
- Nobody can be healed once they are in The Calling. A summon cannot be healed (it has hits, not DP).
- The "already healed" record is cleared when the encounter ends.
"""
import asyncio
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_healing.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, Campaign, CampaignMembership, Character, Encounter, EncounterHeal, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Heal test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, dp=10, max_dp=20, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id,
                      campaign_id=camp.id, level=2, pp=2, ip=3, sp=1, dp=dp, max_dp=max_dp, edge=1,
                      attack_style="1d6", defense_die="1d6", max_uses_per_encounter=4, current_uses=4, **kw)
        db.add(c)
        db.commit()
        return c

    def healer(name="Healer", aoe=False):
        c = pc(name, dp=20)
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell",
                       display_name="Mend", macro_command="/mend", power_source="IP", effect_type="heal",
                       die="1d6", is_aoe=aoe, max_uses=9, uses_remaining=9))
        db.commit()
        return c

    def start_encounter():
        e = Encounter(id=uuid.uuid4(), campaign_id=camp.id, is_active=True)
        db.add(e)
        db.commit()
        return e

    def end_all_encounters():
        for e in db.query(Encounter).filter_by(campaign_id=camp.id, is_active=True).all():
            e.is_active = False
        db.commit()

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, healer=healer, start=start_encounter,
               end_all=end_all_encounters, tag=tag, EncounterHeal=EncounterHeal, Encounter=Encounter)
    db.close()


@pytest.fixture(autouse=True)
def _no_encounter_unless_started(world):
    world["end_all"]()
    yield
    world["end_all"]()


def _cast(world, caster, command, die_roll=4, aoe_approved=False):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command, "speaker_id": str(caster.id), "speaker_type": "pc"}
        if aoe_approved:
            payload["_aoe_approved"] = True      # the SW has approved the area cast
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[die_roll]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, world["player"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return next((m for m in sent if m.get("type") == "ability_cast"), None), sent


def test_a_heal_adds_edge_like_any_spell(world):
    h, t = world["healer"]("H1"), world["pc"]("T1", dp=5)
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{t.name}]", die_roll=4)       # 4 + IP 3 + Edge 1 = 8
    r = card["results"][0]
    assert r["healing"] == 8 and (t.dp, r["new_dp"]) == (13, 13)
    assert "Edge(1)" in r["roll_breakdown"]


def test_a_buff_on_the_casting_stat_adds_to_the_heal(world):
    from backend.buffs import add_effect
    h, t = world["healer"]("H2"), world["pc"]("T2", dp=5)
    add_effect(world["db"], campaign_id=world["camp"].id, character_id=h.id, name="Focus", modifier=2,
               modifier_type="ip", duration_rounds=2, applied_by="test")
    world["db"].commit()
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{t.name}]", die_roll=4)       # 8 + 2
    assert card["results"][0]["healing"] == 10 and "Effects(+2)" in card["results"][0]["roll_breakdown"]


def test_the_same_person_cannot_be_healed_twice_in_an_encounter(world):
    h, t = world["healer"]("H3"), world["pc"]("T3", dp=2)
    world["start"]()
    _cast(world, h, f"/mend @[{t.name}]")
    first_dp, uses_after_first = t.dp, h.current_uses
    card, _ = _cast(world, h, f"/mend @[{t.name}]")
    r = card["results"][0]
    assert not r["success"] and "already healed" in r["message"]
    assert t.dp == first_dp, "a blocked heal must not change DP"
    assert h.current_uses == uses_after_first, "a heal that healed nobody must not cost a use"


def test_the_record_is_per_encounter_and_clears_when_it_ends(world):
    h, t = world["healer"]("H4"), world["pc"]("T4", dp=2)
    enc = world["start"]()
    _cast(world, h, f"/mend @[{t.name}]")
    assert world["db"].query(world["EncounterHeal"]).filter_by(encounter_id=enc.id).count() == 1
    world["end_all"]()
    world["start"]()                                                  # a new encounter: a fresh slate
    dp_before = t.dp
    card, _ = _cast(world, h, f"/mend @[{t.name}]")
    assert card["results"][0]["success"] and t.dp > dp_before


def test_outside_an_encounter_healing_is_free_and_unlimited(world):
    h, t = world["healer"]("H5"), world["pc"]("T5", dp=1, max_dp=40)
    uses = h.current_uses
    for _ in range(3):
        card, _ = _cast(world, h, f"/mend @[{t.name}]")
        assert card["results"][0]["success"]
    assert h.current_uses == uses, "healing between encounters costs no uses"
    assert world["db"].query(world["EncounterHeal"]).filter_by(target_character_id=t.id).count() == 0
    assert t.dp == 1 + 3 * 8


def test_during_an_encounter_a_heal_costs_a_use(world):
    h, t = world["healer"]("H6"), world["pc"]("T6", dp=5)
    world["start"]()
    _cast(world, h, f"/mend @[{t.name}]")
    assert h.current_uses == 3


def test_a_heal_at_negative_dp_goes_to_zero_first_then_adds_the_roll(world):
    h, t = world["healer"]("H7"), world["pc"]("T7", dp=-6)
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{t.name}]", die_roll=4)       # roll 8: -6 -> 0 -> 8
    assert t.dp == 8 and card["results"][0]["healing"] == 14 and card["results"][0]["heal_roll"] == 8


def test_a_heal_never_goes_above_max_dp(world):
    h, t = world["healer"]("H8"), world["pc"]("T8", dp=18, max_dp=20)
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{t.name}]", die_roll=6)
    assert t.dp == 20 and card["results"][0]["healing"] == 2


def test_nobody_in_the_calling_can_be_healed(world):
    h = world["healer"]("H9")
    t = world["pc"]("T9", dp=-12, in_calling=True)
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{t.name}]")
    r = card["results"][0]
    assert not r["success"] and "Calling" in r["message"] and t.dp == -12


def test_a_summon_cannot_be_healed(world):
    h = world["healer"]("H10")
    s = world["pc"]("Spirit", dp=1, max_dp=4, is_summon=True, is_npc=True)
    world["start"]()
    card, _ = _cast(world, h, f"/mend @[{s.name}]")
    assert not card["results"][0]["success"] and "summon" in card["results"][0]["message"] and s.dp == 1


def test_an_area_heal_rolls_once_and_skips_anyone_already_healed(world):
    h = world["healer"]("H11", aoe=True)
    a, b = world["pc"]("A", dp=2), world["pc"]("B", dp=2)
    world["start"]()
    _cast(world, h, f"/mend @[{a.name}]", aoe_approved=True)           # A is healed first
    card, _ = _cast(world, h, f"/mend @[{a.name}] @[{b.name}]", aoe_approved=True)
    by = {r["target"]: r for r in card["results"]}
    assert not by[a.name]["success"] and by[b.name]["success"]
    assert by[b.name]["heal_roll"] == 8


def test_a_boost_cannot_heal_a_target_that_was_blocked(world):
    """The Boost code reads results; a blocked target has no 'healing' and must be skipped, not healed by the bonus."""
    from routes.character_fastapi import _boost_skips_target
    assert _boost_skips_target({"target": "X", "success": False, "message": "was already healed this encounter"})
    assert not _boost_skips_target({"target": "X", "success": True, "healing": 5})
