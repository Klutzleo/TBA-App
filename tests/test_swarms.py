"""
Swarms (rules v3.1): lots of weak bodies sharing one stat block. The DP being subtracted is the bodies dying, so a swarm cannot be healed
by a spell, a Combo, a potion, the Story Weaver's heal button or an environmental Healing effect.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_swarms.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, Campaign, CampaignMembership, Character, InventoryItem, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Swarm test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str(player.id), user_id=player.id, campaign_id=camp.id,
                      level=3, pp=2, ip=3, sp=1, dp=20, max_dp=20, edge=1, attack_style="1d6", defense_die="1d6",
                      max_uses_per_encounter=10, current_uses=10, **kw)
        db.add(c)
        db.commit()
        return c

    def npc(name, swarm, dp=10):
        n = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=True,
                      is_swarm=swarm, level=1, pp=2, ip=2, sp=2, dp=dp, max_dp=20, edge=0, attack_style="1d4",
                      defense_die="1d4")
        db.add(n)
        db.commit()
        return n

    def healer():
        c = pc("Healer")
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name="Mend",
                       macro_command="/mend", power_source="IP", effect_type="heal", die="1d6", max_uses=9, uses_remaining=9))
        db.commit()
        return c

    def potion(owner):
        it = InventoryItem(id=uuid.uuid4(), character_id=owner.id, campaign_id=camp.id, name="Potion", item_type="consumable",
                           quantity=1, tier=3, effect_type="heal")
        db.add(it)
        db.commit()
        return it

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc, npc=npc, healer=healer, potion=potion, tag=tag, Character=Character)
    db.close()


def _cast_heal(world, caster, target):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, m):
        sent.append(m)

    orig = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": f"/mend @[{target.name}]", "speaker_id": str(caster.id), "speaker_type": "pc"}
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[4]):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, world["player"].id, world["db"]))
    finally:
        cw.manager.broadcast = orig
    world["db"].expire_all()
    return next((m for m in sent if m.get("type") == "ability_cast"), None)


def test_a_swarm_can_be_created_and_toggled(world):
    from routes.character_fastapi import create_npc, update_npc
    from routes.schemas.character import CharacterCreate, CharacterUpdate
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    made = asyncio.run(create_npc(str(world["camp"].id), CharacterCreate(
        name=f"Rat Swarm {world['tag']}", owner_id=str(world["sw"].id), level=1, pp=2, ip=2, sp=2, attack_style="1d4",
        is_swarm=True), req, world["db"], world["sw"]))
    assert made.is_swarm is True
    asyncio.run(update_npc(str(world["camp"].id), str(made.id), CharacterUpdate(is_swarm=False), req, world["db"], world["sw"]))
    world["db"].expire_all()
    assert world["db"].get(world["Character"], made.id).is_swarm is False
    asyncio.run(update_npc(str(world["camp"].id), str(made.id), CharacterUpdate(is_swarm=True), req, world["db"], world["sw"]))
    world["db"].expire_all()
    assert world["db"].get(world["Character"], made.id).is_swarm is True


def test_a_heal_spell_cannot_heal_a_swarm_but_still_heals_an_ordinary_npc(world):
    h, swarm, plain = world["healer"](), world["npc"]("Wasps", True), world["npc"]("Thug", False)
    card = _cast_heal(world, h, swarm)
    r = card["results"][0]
    assert not r["success"] and "swarm" in r["message"] and swarm.dp == 10
    assert h.current_uses == 10, "a heal that landed on nobody costs no use"
    assert _cast_heal(world, h, plain)["results"][0]["success"] and plain.dp > 10


def test_a_potion_cannot_heal_a_swarm(world):
    from fastapi import HTTPException
    from routes.character_fastapi import use_inventory_item
    owner = world["pc"]("Potion Holder")
    swarm = world["npc"]("Beetles", True)
    it = world["potion"](owner)
    with pytest.raises(HTTPException) as e:
        asyncio.run(use_inventory_item(str(owner.id), str(it.id), {"target_id": str(swarm.id)}, current_user=world["player"], db=world["db"]))
    assert "swarm" in e.value.detail
    world["db"].expire_all()
    assert swarm.dp == 10


def test_the_story_weavers_heal_button_refuses_a_swarm(world):
    from fastapi import HTTPException
    from routes.character_fastapi import heal_character
    swarm = world["npc"]("Bats", True)
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    with pytest.raises(HTTPException) as e:
        asyncio.run(heal_character(str(swarm.id), req, {"amount": 5}, world["db"], world["sw"]))
    assert "swarm" in e.value.detail


def test_environmental_healing_does_nothing_for_a_swarm(world):
    from routes import campaign_websocket as cw
    swarm = world["npc"]("Moths", True)

    async def fake_broadcast(_cid, _m):
        pass

    async def fake_send(_cid, _uid, _m):
        pass

    orig_b, orig_s = cw.manager.broadcast, cw.manager.send_to_user
    cw.manager.broadcast, cw.manager.send_to_user = fake_broadcast, fake_send
    try:
        asyncio.run(cw._apply_env_effect_now(world["camp"].id, world["sw"].id, swarm, "healing", 2, "1d8", None, True, world["db"]))
    finally:
        cw.manager.broadcast, cw.manager.send_to_user = orig_b, orig_s
    world["db"].expire_all()
    assert swarm.dp == 10


def test_a_combo_heal_skips_a_swarm(world):
    from routes import campaign_websocket as cw
    h, swarm = world["healer"](), world["npc"]("Flies", True)

    async def fake_broadcast(_cid, _m):
        pass

    orig = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[4]):
            result, _ = asyncio.run(cw._combo_activation(world["camp"].id, world["db"], h, 1, swarm.name))
    finally:
        cw.manager.broadcast = orig
    world["db"].expire_all()
    assert "swarm" in result["summary"] and swarm.dp == 10
