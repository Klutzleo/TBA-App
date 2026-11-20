"""
Whispers are private. Before this fix, a whisper was broadcast to every connected member and returned to every member by the history
endpoint, and it was stored without recipients. These tests use real connection-manager delivery with fake sockets.
"""
import asyncio
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_whisper_privacy.db")
os.environ.setdefault("API_KEY", "devkey")


class FakeWS:
    def __init__(self):
        self.sent = []

    async def accept(self, subprotocol=None):
        pass

    async def send_json(self, m):
        self.sent.append(m)

    def whispers(self):
        return [m for m in self.sent if m.get("type") == "chat_whisper"]


@pytest.fixture
def room():
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, User
    from routes import campaign_websocket as cw
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    users = {}
    for n in ("sw", "alice", "bob", "carol"):
        u = User(id=uuid.uuid4(), email=f"{n}_{tag}@example.com", username=f"{n}_{tag}", hashed_password="x")
        db.add(u)
        users[n] = u
    db.commit()
    camp = Campaign(id=uuid.uuid4(), name=f"Whisper {tag}", description="x" * 12, created_by_user_id=users["sw"].id,
                    created_by_id=str(users["sw"].id), story_weaver_id=users["sw"].id, join_code=tag[:6].upper())
    db.add(camp)
    db.commit()
    for n, u in users.items():
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role="story_weaver" if n == "sw" else "player"))
    chars = {}
    for n in ("alice", "bob", "carol"):
        c = Character(id=uuid.uuid4(), name=f"{n.title()}Hero{tag}", owner_id=str(users[n].id), user_id=users[n].id, campaign_id=camp.id,
                      level=1, pp=2, ip=2, sp=2, dp=10, max_dp=10, edge=1, attack_style="1d6", defense_die="1d4", status="active")
        db.add(c)
        chars[n] = c
    db.commit()
    mgr = cw.CampaignConnectionManager()
    socks = {}
    for n, u in users.items():
        socks[n] = FakeWS()
        mgr.active_connections.setdefault(camp.id, []).append((socks[n], u.id, n, users[n].username))
    old = cw.manager
    cw.manager = mgr
    yield dict(db=db, camp=camp, users=users, chars=chars, socks=socks, cw=cw, tag=tag)
    cw.manager = old
    db.close()


def _say(r, who, text, targets):
    asyncio.run(r["cw"].handle_legacy_message(r["camp"].id, {"text": text, "chat_mode": "ic", "whisper_targets": targets},
                                              r["users"][who].id, who, r["db"]))


def _history(r, who):
    from routes.campaigns import get_campaign_messages
    return [m["content"] for m in get_campaign_messages(str(r["camp"].id), limit=100, offset=0, tab=None,
                                                        current_user=r["users"][who], db=r["db"])["messages"]]


def test_whisper_reaches_only_sender_and_target_live(room):
    _say(room, "alice", "psst bob", [room["chars"]["bob"].name])
    assert len(room["socks"]["bob"].whispers()) == 1
    assert len(room["socks"]["alice"].whispers()) == 1
    assert room["socks"]["carol"].whispers() == []
    assert room["socks"]["sw"].whispers() == []


def test_whisper_history_is_private(room):
    _say(room, "alice", "secret plan", [room["chars"]["bob"].name])
    _say(room, "alice", "hello everyone", [])
    assert "secret plan" in _history(room, "alice")
    assert "secret plan" in _history(room, "bob")
    assert "secret plan" not in _history(room, "carol")
    assert "secret plan" not in _history(room, "sw")
    assert "hello everyone" in _history(room, "carol")


def test_username_and_story_weaver_targets_resolve(room):
    _say(room, "alice", "to the SW", ["Story Weaver"])
    assert len(room["socks"]["sw"].whispers()) == 1 and room["socks"]["bob"].whispers() == []
    _say(room, "alice", "by username", ["@" + room["users"]["carol"].username])
    assert len(room["socks"]["carol"].whispers()) == 1 and room["socks"]["bob"].whispers() == []


def test_unknown_target_is_not_sent_and_sender_is_told(room):
    _say(room, "alice", "to nobody", ["Nobody Here"])
    assert all(not s.whispers() for s in room["socks"].values())
    assert any("not sent" in m.get("text", "") for m in room["socks"]["alice"].sent)
    assert "to nobody" not in _history(room, "alice")


def test_someone_who_left_cannot_be_whispered(room):
    from datetime import datetime
    from backend.models import CampaignMembership
    m = room["db"].query(CampaignMembership).filter(CampaignMembership.user_id == room["users"]["bob"].id).first()
    m.left_at = datetime.utcnow()
    room["db"].commit()
    _say(room, "alice", "bob is gone", [room["chars"]["bob"].name])
    assert room["socks"]["bob"].whispers() == []


def test_story_weaver_switch_controls_sw_visibility(room):
    from backend import whispers
    _say(room, "alice", "player only", [room["chars"]["bob"].name])
    assert "player only" not in _history(room, "sw")
    whispers.SW_SEES_ALL_WHISPERS = True
    try:
        assert "player only" in _history(room, "sw")
    finally:
        whispers.SW_SEES_ALL_WHISPERS = False
