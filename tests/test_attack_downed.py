"""
A player character at 0 to -9 DP is unconscious, not safe (rules v3.1): a weapon attack can still hit them, and -10 starts The Calling.
Someone already in The Calling is waiting on their roll, and an NPC at 0 DP is simply out of the fight, so those are still refused.
"""
import asyncio
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_attack_downed.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    sw = User(id=uuid.uuid4(), email=f"sw_{tag}@example.com", username=f"sw_{tag}", hashed_password="x")
    pl = User(id=uuid.uuid4(), email=f"pl_{tag}@example.com", username=f"pl_{tag}", hashed_password="x")
    db.add_all([sw, pl])
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name="Downed test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=pl.id, role="player"))
    db.commit()

    def char(name, owner, npc=False, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str(owner.id), user_id=None if npc else owner.id,
                      campaign_id=camp.id, is_npc=npc, level=2, pp=3, ip=1, sp=2, max_dp=20, edge=1,
                      attack_style="1d6", defense_die="1d4", **kw)
        db.add(c)
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, pl=pl, char=char, tag=tag)
    db.close()


def _attack(world, attacker, target, atk=6, defense=1):
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
        with mock.patch("backend.roll_logic.roll_dice", return_value=[atk]), \
                mock.patch("backend.roll_logic.roll_die", return_value=defense):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command",
                        "raw_command": f"/attack @[{target.name}]", "attacker_id": str(attacker.id)}, WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent


def test_a_downed_player_character_can_still_be_hit(world):
    foe, hero = world["char"]("Raider", world["sw"], npc=True, dp=20), world["char"]("Fallen", world["pl"], dp=0)
    sent = _attack(world, foe, hero)                               # 6 + PP3 + Edge1 = 10 vs 1 + PP3 + Edge1 = 5: 5 damage
    assert hero.dp == -5 and not hero.in_calling
    assert not any("already unconscious" in (m.get("text") or "") for m in sent)


def test_enough_hits_on_a_downed_hero_start_the_calling(world):
    foe, hero = world["char"]("Raider2", world["sw"], npc=True, dp=20), world["char"]("Fallen2", world["pl"], dp=-7)
    sent = _attack(world, foe, hero)                               # 5 more damage: -12, past -10
    assert hero.dp == -12 and hero.in_calling is True
    assert any(m.get("type") == "calling_triggered" for m in sent)


def test_someone_already_in_the_calling_cannot_be_attacked(world):
    foe, hero = world["char"]("Raider3", world["sw"], npc=True, dp=20), world["char"]("Waiting", world["pl"], dp=-12, in_calling=True)
    sent = _attack(world, foe, hero)
    assert hero.dp == -12 and any("in The Calling" in (m.get("text") or "") for m in sent)


def test_an_npc_at_zero_dp_is_still_out_of_the_fight(world):
    foe, down = world["char"]("Raider4", world["sw"], npc=True, dp=20), world["char"]("Beaten", world["sw"], npc=True, dp=0)
    sent = _attack(world, foe, down)
    assert down.dp == 0 and any("already unconscious" in (m.get("text") or "") for m in sent)
