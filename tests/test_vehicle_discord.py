"""
Vehicles and the Discord mirror: adding a vehicle or seating crew is table setup and must never be posted to the public Discord
channel. NPCs have never broadcast on creation, and a test below keeps it that way. Real story events (a vehicle disabled in a
fight) still mirror.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from backend import discord_mirror as dm


@pytest.fixture
def mirror(monkeypatch):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setattr(dm, "DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(dm, "_outbound_queue", asyncio.Queue())
    monkeypatch.setattr(dm, "_get_channel_id", lambda campaign_id: "1234567890")
    yield dm
    loop.close()


def _posted(mirror_mod):
    q = mirror_mod._outbound_queue
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_the_refresh_ping_and_flagged_setup_text_are_never_posted(mirror):
    mirror.enqueue_outbound("c1", {"type": "vehicles_changed", "campaign_id": "c1"})
    mirror.enqueue_outbound("c1", {"type": "system", "text": "🚀 The Rusty Comet (level 3) joins the campaign", "no_mirror": True})
    assert _posted(mirror) == []


def test_a_real_story_event_still_posts(mirror):
    mirror.enqueue_outbound("c1", {"type": "system", "text": "💥 The Rusty Comet is disabled! (DP: -1)"})
    posted = _posted(mirror)
    assert len(posted) == 1 and "disabled" in posted[0]["text"]


@pytest.fixture
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
    camp = Campaign(id=uuid.uuid4(), name="Discord vehicles", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=pl.id, role="player"))
    db.commit()
    pc = Character(id=uuid.uuid4(), name=f"Hero {tag}", owner_id=str(pl.id), user_id=pl.id, campaign_id=camp.id, level=2, pp=3, ip=2,
                   sp=2, dp=20, max_dp=20, edge=1, attack_style="1d6", defense_die="1d4")
    db.add(pc)
    db.commit()
    yield dict(db=db, camp=camp, sw=sw, pl=pl, pc=pc)
    db.close()


def test_creating_a_vehicle_and_seating_crew_post_nothing_to_discord(mirror, world):
    from routes.vehicles import CrewAssign, VehicleCreate, create_vehicle, leave_station, take_station
    made = asyncio.run(create_vehicle(str(world["camp"].id), VehicleCreate(name="The Rusty Comet", level=3), world["db"], world["sw"]))
    asyncio.run(take_station(str(world["camp"].id), made["id"], "gunner", CrewAssign(character_id=str(world["pc"].id)), world["db"], world["pl"]))
    asyncio.run(leave_station(str(world["camp"].id), made["id"], "gunner", world["db"], world["pl"]))
    assert _posted(mirror) == []


def test_creating_an_npc_posts_nothing_to_discord(mirror, world):
    from routes.character_fastapi import create_npc
    from routes.schemas.character import CharacterCreate
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    asyncio.run(create_npc(str(world["camp"].id), CharacterCreate(name="Guard Captain", owner_id=str(world["sw"].id), level=1, pp=2, ip=2, sp=2,
                                                                 attack_style="1d4"), req, world["db"], world["sw"]))
    assert _posted(mirror) == []
