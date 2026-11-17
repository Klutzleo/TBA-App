"""
Rules v3.1: uses per encounter are ONE shared pool per character (level + 2), spent by every spell, technique,
summon call and Combo. Before this, every ability carried its own counter at the full level total.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_uses_pool.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Ability, Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Pool test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, level=2):
        pool = level + 2
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(player.id), user_id=player.id,
                      campaign_id=camp.id, level=level, pp=2, ip=3, sp=1, dp=20, max_dp=20, edge=1,
                      attack_style="1d6", defense_die="1d6", max_uses_per_encounter=pool, current_uses=pool)
        db.add(c)
        db.commit()
        for slot, macro, nm in ((1, "/fire", "Fire"), (2, "/frost", "Frost")):
            # each ability still carries the OLD per-ability counters, deliberately full: they must not matter
            db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=slot, ability_type="spell",
                           display_name=nm, macro_command=macro, power_source="IP", effect_type="damage",
                           die="1d6", max_uses=99, uses_remaining=99))
        db.commit()
        return c

    def dummy(name):
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      level=1, pp=1, ip=1, sp=1, dp=500, max_dp=500, edge=0, attack_style="1d4", defense_die="1d4")
        db.add(d)
        db.commit()
        return d

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, dummy=dummy, tag=tag, Ability=Ability)
    db.close()


def _cast(world, caster, command):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command, "speaker_id": str(caster.id), "speaker_type": "pc"}
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[3]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, world["player"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent


def test_every_cast_spends_the_same_pool_whichever_ability_it_is(world):
    caster, target = world["pc"]("Caster"), world["dummy"]("Target0")
    for macro in ("/fire", "/frost", "/fire", "/frost"):             # level 2 pool is 4
        sent = _cast(world, caster, f"{macro} @[{target.name}]")
        assert any(m.get("type") == "ability_cast" for m in sent), [m.get("text") for m in sent]
    assert caster.current_uses == 0
    # the fifth cast is refused, even though each ability's own (old) counter still says 99
    sent = _cast(world, caster, f"/fire @[{target.name}]")
    assert not any(m.get("type") == "ability_cast" for m in sent)
    assert any("no uses remaining" in (m.get("text") or "") for m in sent)
    assert caster.current_uses == 0


def test_the_cast_card_shows_the_pool_not_the_ability(world):
    caster, target = world["pc"]("Shower"), world["dummy"]("Target1")
    sent = _cast(world, caster, f"/frost @[{target.name}]")
    card = next(m for m in sent if m.get("type") == "ability_cast")
    assert (card["uses_remaining"], card["max_uses"]) == (3, 4)


def test_the_pool_is_capped_and_floored():
    from backend.uses import pool_max, pool_remaining, refill, restore, spend
    c = SimpleNamespace(level=3, max_uses_per_encounter=5, current_uses=2)
    assert (pool_max(c), pool_remaining(c)) == (5, 2)
    assert spend(c, 9) == 0 and pool_remaining(c) == 0           # never below 0
    assert restore(c, 2) == 2 and restore(c, 99) == 5            # never above the pool
    c.current_uses = 1
    assert refill(c) == 5
    c.current_uses = None
    c.max_uses_per_encounter = None
    assert pool_max(c) == 5 and pool_remaining(c) == 5           # missing values fall back to level + 2


def test_the_sw_restore_endpoint_works_on_the_pool(world):
    from routes.character_fastapi import restore_ability_uses
    caster = world["pc"]("Restorable")
    caster.current_uses = 1
    world["db"].commit()
    request = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    r = asyncio.run(restore_ability_uses(str(caster.id), request, {"amount": 2}, world["db"], world["sw"]))
    assert (r["restored"], r["total_remaining"]) == (2, 3)
    r = asyncio.run(restore_ability_uses(str(caster.id), request, {"restore_all": True}, world["db"], world["sw"]))
    assert r["total_remaining"] == 4 == r["max_uses"]
    r = asyncio.run(restore_ability_uses(str(caster.id), request, {"amount": 5}, world["db"], world["sw"]))
    assert r["restored"] == 0 and r["total_remaining"] == 4      # already full: nothing to add


def test_a_combo_costs_one_use_per_character_from_the_pool(world):
    from routes import campaign_websocket as cw
    a, b = world["pc"]("ComboA"), world["pc"]("ComboB", level=3)    # pools 4 and 5
    combo = SimpleNamespace(id=uuid.uuid4(), proposer_character_id=a.id, acceptor_character_id=b.id,
                            proposer_ability_slot=1, acceptor_ability_slot=2, status="holding", bond=None)
    cw._combo_targets[str(combo.id)] = {str(a.id): None, str(b.id): None}   # picks made when the Combo fired
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("backend.roll_logic.roll_dice", return_value=[3]):
            asyncio.run(cw._resolve_combo(world["camp"].id, combo, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert (a.current_uses, b.current_uses) == (3, 4)               # it used to cost 2 per character


def test_ending_an_encounter_refills_every_pool(world):
    """/initiative end: every character in the campaign, PCs and NPCs, gets a full pool back."""
    from backend.models import Encounter
    from routes import campaign_websocket as cw
    pc, npc = world["pc"]("Tired"), world["dummy"]("TiredNpc")
    pc.current_uses = 0
    npc.max_uses_per_encounter, npc.current_uses = 3, 0
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True)
    world["db"].add(enc)
    world["db"].commit()

    class FakeWS:
        async def send_json(self, _msg):
            pass

    async def fake_broadcast(_cid, _msg):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(cw.end_encounter(world["camp"].id, world["sw"].id, world["db"], FakeWS()))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert (pc.current_uses, npc.current_uses) == (4, 3)
