"""
handle_ability_cast speaker rules.

The client sends speaker_id for whoever is the active speaker, which for a normal
player is their OWN character. That must be allowed; casting as anyone else is
Story Weaver only, and the character must belong to the campaign.

Every ability here has 0 uses left, so a cast that passes the caster gate ends at
the harmless "has no uses remaining" message instead of rolling anything.
"""
import asyncio
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ability_cast.db")
os.environ.setdefault("API_KEY", "devkey")

SW_ERROR = "Only the Story Weaver can cast abilities as another character"


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

    sw, p1, p2, p3 = user("sw"), user("p1"), user("p2"), user("p3")
    camp = Campaign(id=uuid.uuid4(), name="Cast test", description="x", created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    other = Campaign(id=uuid.uuid4(), name="Elsewhere", description="x", created_by_user_id=sw.id,
                     created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add_all([camp, other])
    db.commit()
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player"), (p3, "player")):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role))
    db.commit()

    def pc(owner, campaign, name):
        c = Character(id=uuid.uuid4(), name=name, owner_id=str(owner.id), user_id=owner.id,
                      campaign_id=campaign.id, pp=2, ip=2, sp=2, dp=10, max_dp=10,
                      attack_style="melee", defense_die="1d6")
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="technique",
                       display_name="Hammer", macro_command="/hammer", power_source="PP",
                       effect_type="damage", die="2d6", max_uses=3, uses_remaining=0))
        db.commit()
        return c

    data = dict(camp=camp, sw=sw, p1=p1, p2=p2, p3=p3,
                p3_elsewhere_pc=pc(p3, other, "P3 Elsewhere"),
                p1_pc=pc(p1, camp, "Beef"), p2_pc=pc(p2, camp, "Giy"),
                foreign_pc=pc(p2, other, "Elsewhere PC"))
    yield data, db
    db.close()


def cast(world, user, speaker_id, speaker_type, command="/hammer"):
    from routes import campaign_websocket as cw
    data, db = world
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg.get("text", ""))

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command}
        if speaker_id:
            payload.update(speaker_id=str(speaker_id), speaker_type=speaker_type)
        asyncio.run(cw.handle_ability_cast(data["camp"].id, payload, None, user.id, db))
    finally:
        cw.manager.broadcast = original
    return " | ".join(sent)


def test_player_casting_as_their_own_character_is_allowed(world):
    data, _ = world
    out = cast(world, data["p1"], data["p1_pc"].id, "pc")
    assert SW_ERROR not in out
    assert "no uses remaining" in out


def test_player_cannot_cast_as_another_players_character(world):
    data, _ = world
    out = cast(world, data["p1"], data["p2_pc"].id, "pc")
    assert SW_ERROR in out


def test_sw_can_puppet_a_players_character(world):
    data, _ = world
    out = cast(world, data["sw"], data["p1_pc"].id, "puppet")
    assert SW_ERROR not in out
    assert "no uses remaining" in out


def test_character_from_another_campaign_is_not_castable_even_by_the_sw(world):
    data, _ = world
    out = cast(world, data["sw"], data["foreign_pc"].id, "pc")
    assert "no uses remaining" not in out
    assert "need a character" in out


def test_cast_without_speaker_id_ignores_characters_from_other_campaigns(world):
    """p3's only character lives in another campaign. Casting here with no speaker_id must
    say they have no character, not quietly cast as the one from elsewhere."""
    data, _ = world
    out = cast(world, data["p3"], None, None)
    assert "need a character" in out, out
