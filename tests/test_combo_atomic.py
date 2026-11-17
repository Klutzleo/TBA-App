"""
A Combo is saved all together or not at all.

Before this, each half of a Combo (the damage, the heal, a Calling starting, a summon vanishing) was saved as it happened, and only
the result card, the uses and the "fired" flag were saved at the end. A failure in between left half a Combo behind. Now every
save inside a Combo is held in one transaction and everything that would be broadcast waits for the commit.
"""
import asyncio
import os
import uuid
from unittest import mock
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_combo_atomic.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, Campaign, CampaignMembership, Character, Encounter, Message, PendingCombo, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, p1, p2 = user("sw"), user("p1"), user("p2")
    camp = Campaign(id=uuid.uuid4(), name="Atomic test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player")):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role))
    db.commit()

    def pc(owner, name, **kw):
        kw.setdefault("dp", 20)
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(owner.id), user_id=owner.id, campaign_id=camp.id,
                      level=2, pp=2, ip=3, sp=1, max_dp=20, edge=1, bap=2, attack_style="1d6", defense_die="1d6",
                      max_uses_per_encounter=10, current_uses=10, **kw)
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name="Bolt",
                       macro_command="/bolt", power_source="IP", effect_type="damage", die="1d6", max_uses=9, uses_remaining=9))
        db.commit()
        return c

    def target(name, **kw):
        kw.setdefault("dp", 100)
        d = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(sw.id), campaign_id=camp.id, is_npc=kw.pop("is_npc", True),
                      level=1, pp=1, ip=1, sp=1, max_dp=100, edge=0, attack_style="1d4", defense_die="1d4", **kw)
        db.add(d)
        db.commit()
        return d

    def pending(a, b):
        e = Encounter(id=uuid.uuid4(), campaign_id=camp.id, is_active=True)
        db.add(e)
        db.commit()
        pcb = PendingCombo(id=uuid.uuid4(), encounter_id=e.id, campaign_id=camp.id, proposer_character_id=a.id,
                           acceptor_character_id=b.id, status="ready", proposer_ability_slot=1, acceptor_ability_slot=1)
        db.add(pcb)
        db.commit()
        return pcb

    yield dict(db=db, camp=camp, sw=sw, p1=p1, p2=p2, pc=pc, target=target, pending=pending, tag=tag,
               SessionLocal=SessionLocal, Message=Message, PendingCombo=PendingCombo)
    db.close()


def _resolve(world, combo, a, b, t, dice, activation_wrapper=None, watch=None):
    """Resolve with scripted dice. Returns (broadcasts, sends)."""
    from routes import campaign_websocket as cw
    seq = iter(dice)
    out, sends = [], []

    async def real_broadcast(_cid, m):
        out.append(m)
        if watch:
            watch("broadcast", m)

    async def real_send(_cid, _uid, m):
        sends.append(m)

    cw._combo_targets[str(combo.id)] = {str(a.id): t.name, str(b.id): t.name}
    orig_b, orig_s = cw.manager.broadcast, cw.manager.send_to_user
    cw.manager.broadcast, cw.manager.send_to_user = real_broadcast, real_send
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)]):
            if activation_wrapper:
                original = cw._combo_activation
                with mock.patch.object(cw, "_combo_activation", side_effect=activation_wrapper(original)):
                    asyncio.run(cw._resolve_combo(world["camp"].id, combo, world["db"]))
            else:
                asyncio.run(cw._resolve_combo(world["camp"].id, combo, world["db"]))
    finally:
        cw.manager.broadcast, cw.manager.send_to_user = orig_b, orig_s
    world["db"].expire_all()
    return out, sends


def _other_session_dp(world, character):
    """What a different connection to the database can see right now (only committed data)."""
    from backend.models import Character
    s = world["SessionLocal"]()
    try:
        return s.query(Character).filter(Character.id == character.id).one().dp
    finally:
        s.close()


def test_a_failure_halfway_leaves_no_trace(world):
    a, b = world["pc"](world["p1"], "AtomA"), world["pc"](world["p2"], "AtomB")
    t = world["target"]("Victim", dp=-5, is_npc=False)           # a PC: a big hit sends them into The Calling
    t.user_id = world["p1"].id
    t.owner_id = str(world["p1"].id)
    world["db"].commit()
    combo = world["pending"](a, b)
    seen_mid_flight = {}

    def failing_second(original):
        calls = {"n": 0}

        async def wrapper(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                # The first half has already hit the target, but nothing is permanent yet: another connection still sees -5
                seen_mid_flight["dp"] = _other_session_dp(world, t)
                raise RuntimeError("something broke halfway")
            return await original(*args, **kwargs)
        return wrapper

    out, sends = _resolve(world, combo, a, b, t, dice=[6, 1, 6, 1], activation_wrapper=failing_second)
    assert seen_mid_flight["dp"] == -5, "not committed early"
    world["db"].expire_all()
    assert t.dp == -5 and t.in_calling is False, "the first hit and the Calling it caused were rolled back"
    assert (a.current_uses, b.current_uses) == (10, 10), "no use was spent"
    assert world["db"].get(world["PendingCombo"], combo.id).status == "ready", "not marked fired"
    assert not any(m.get("type") in ("combo_resolved", "calling_triggered") for m in out), "nobody saw half a Combo"
    assert world["db"].query(world["Message"]).filter_by(message_type="combo_resolved", campaign_id=world["camp"].id).count() == 0
    prompts = [m for m in sends if m.get("type") == "combo_fire_ready"]
    assert len(prompts) == 2 and all("Something went wrong" in m["notice"] for m in prompts)
    pcb = world["db"].get(world["PendingCombo"], combo.id)
    assert pcb.proposer_ability_slot is None and pcb.acceptor_ability_slot is None


def test_on_success_everything_is_committed_before_anyone_is_told(world):
    a, b, t = world["pc"](world["p1"], "OkA"), world["pc"](world["p2"], "OkB"), world["target"]("Dummy")
    combo = world["pending"](a, b)
    checks = []

    def watch(kind, message):
        if message.get("type") == "combo_resolved":
            # by the time the card is broadcast, the damage is permanent for every other connection
            checks.append(_other_session_dp(world, t))

    out, _ = _resolve(world, combo, a, b, t, dice=[4, 1, 4, 1], watch=watch)
    assert any(m.get("type") == "combo_resolved" for m in out)
    assert checks and checks[0] < 100, "committed before the card went out"
    assert t.dp < 100 and (a.current_uses, b.current_uses) == (9, 9)
    assert world["db"].get(world["PendingCombo"], combo.id).status == "fired"
    assert world["db"].query(world["Message"]).filter_by(message_type="combo_resolved", campaign_id=world["camp"].id).count() == 1


def test_the_session_is_back_to_normal_afterwards(world):
    """After a Combo (success or failure) commit is the real commit again and broadcasts go out immediately."""
    from routes import campaign_websocket as cw
    db = world["db"]
    assert "commit" not in vars(db), "the temporary commit override is gone"
    assert cw.manager.broadcast.__name__ == "broadcast" and cw.manager.send_to_user.__name__ == "send_to_user"
