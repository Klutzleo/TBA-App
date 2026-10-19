"""
Casting a Summon ability (routes/campaign_websocket.py _handle_summon_cast).

A summon is a real Character row. The database requires attack_style and defense_die on every character, and the summon
code used to leave both empty, so casting a summon on Postgres failed with a NotNullViolation and the player only saw
"Something went wrong casting that ability."
"""
import asyncio
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_summon_cast.db")
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
    camp = Campaign(id=uuid.uuid4(), name="Summon test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def pc(name):
        c = Character(id=uuid.uuid4(), name=name, owner_id=str(player.id), user_id=player.id, campaign_id=camp.id,
                      level=2, pp=2, ip=3, sp=1, dp=15, max_dp=15, edge=1, attack_style="1d6", defense_die="1d8")
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell",
                       display_name="The Progeny", macro_command="/summon", power_source="IP",
                       effect_type="damage", die="1d6", is_summon=True, max_uses=3, uses_remaining=3))
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc)
    db.close()


def cast(world, user, caster, speaker_type=None):
    from routes import campaign_websocket as cw
    db = world["db"]
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": "/summon"}
        if speaker_type:
            payload.update(speaker_id=str(caster.id), speaker_type=speaker_type)
        asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, user.id, db))
    finally:
        cw.manager.broadcast = original
    return sent


def summon_of(world, caster):
    from backend.models import Character
    world["db"].expire_all()
    return world["db"].query(Character).filter_by(summoner_id=caster.id, is_summon=True).first()


def test_player_can_summon_and_the_summon_is_a_complete_character(world):
    caster = world["pc"]("Lazarus")
    sent = cast(world, world["player"], caster, speaker_type="pc")
    s = summon_of(world, caster)
    assert s is not None, [m.get("text") or m.get("message") for m in sent]
    assert s.name == "The Progeny" and s.is_npc and s.is_summon
    assert s.attack_style and s.defense_die            # the two columns the database requires
    assert s.defense_die == caster.defense_die         # a summon defends with the caster's Defense Die
    assert s.dp == s.max_dp == 1                       # level 2: disappears after 1 hit


def test_sw_can_summon_for_a_puppeted_pc(world):
    caster = world["pc"]("Puppeted")
    sent = cast(world, world["sw"], caster, speaker_type="puppet")
    s = summon_of(world, caster)
    assert s is not None, [m.get("text") or m.get("message") for m in sent]
    assert s.attack_style and s.defense_die


def test_summoning_spends_one_use_and_a_second_cast_commands_the_existing_summon(world):
    from backend.models import Ability
    caster = world["pc"]("Spender")
    sent = cast(world, world["player"], caster, speaker_type="pc")  # the real client always names the speaker
    world["db"].expire_all()
    ability = world["db"].query(Ability).filter_by(character_id=caster.id).one()
    assert ability.uses_remaining == 2, [m.get("text") or m.get("message") for m in sent]
    # casting again with no target does not create a second summon
    cast(world, world["player"], caster, speaker_type="pc")
    from backend.models import Character
    assert world["db"].query(Character).filter_by(summoner_id=caster.id, is_summon=True).count() == 1
