"""
Enemy Combos (rules v3.1) and the corrected Combo cancel rule.

- The Story Weaver queues one: an NPC is held, and when a second NPC's turn comes the SW is asked to fire it. Nothing is announced to the
  table (the held slot just skips). It resolves like a players' Combo and fires once per encounter.
- Cancel rule: if EITHER partner drops to 0 DP before it fires, it is cancelled. Getting hit alone does not cancel it. (The app used to
  cancel on any damage to the proposer, and ignored the acceptor.)
"""
import asyncio
import os
import uuid
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_enemy_combos.db")
os.environ.setdefault("API_KEY", "devkey")


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import (Ability, Bond, Campaign, CampaignMembership, Character, Encounter, InitiativeRoll,
                                PendingCombo, User)
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, player = user("sw"), user("pl")
    camp = Campaign(id=uuid.uuid4(), name="Enemy combo test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=sw.id, role="story_weaver"))
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    def char(name, npc=True, **kw):
        kw.setdefault("dp", 20)
        c = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str((sw if npc else player).id),
                      user_id=None if npc else player.id, campaign_id=camp.id, is_npc=npc, level=2, pp=2, ip=3, sp=1,
                      max_dp=20, edge=1, bap=2, attack_style="1d6", defense_die="1d6", max_uses_per_encounter=10,
                      current_uses=10, **kw)
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name="Bolt",
                       macro_command="/bolt", power_source="IP", effect_type="damage", die="1d6", max_uses=9, uses_remaining=9))
        db.commit()
        return c

    def encounter(*rolls):
        for e in db.query(Encounter).filter_by(campaign_id=camp.id, is_active=True).all():
            e.is_active = False
        e = Encounter(id=uuid.uuid4(), campaign_id=camp.id, is_active=True, round_number=1, current_turn_index=0)
        db.add(e)
        db.commit()
        for c, init in rolls:
            db.add(InitiativeRoll(id=uuid.uuid4(), encounter_id=e.id, character_id=c.id, name=c.name, roll_result=init))
        db.commit()
        return e

    yield dict(db=db, camp=camp, sw=sw, player=player, char=char, encounter=encounter, tag=tag, Bond=Bond,
               PendingCombo=PendingCombo, Encounter=Encounter)
    db.close()


class _WS:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)


def _queue(world, a, b, user=None, name="Chain Snap"):
    from routes import campaign_websocket as cw
    ws = _WS()
    asyncio.run(cw._handle_enemy_combo_queue(world["camp"].id, (user or world["sw"]).id,
                                             {"proposer_id": str(a.id), "partner_id": str(b.id), "name": name}, ws, world["db"]))
    world["db"].expire_all()
    return ws.sent


def _advance(world, current_index=None):
    """Advance the turn once. Returns (public broadcasts, private sends to the SW or players)."""
    from routes import campaign_websocket as cw
    pub, priv = [], []

    async def fake_broadcast(_cid, m):
        pub.append(m)

    async def fake_send(_cid, uid, m):
        priv.append((str(uid), m))

    ws = _WS()
    orig_b, orig_s = cw.manager.broadcast, cw.manager.send_to_user
    cw.manager.broadcast, cw.manager.send_to_user = fake_broadcast, fake_send
    try:
        with mock.patch("routes.campaign_websocket.roll_dice", return_value=[3]):
            asyncio.run(cw.advance_turn(world["camp"].id, world["sw"].id, world["db"], ws))
    finally:
        cw.manager.broadcast, cw.manager.send_to_user = orig_b, orig_s
    world["db"].expire_all()
    return pub, priv


def test_only_the_story_weaver_can_queue_and_only_between_two_npcs_in_the_fight(world):
    a, b, pc = world["char"]("Reaver A"), world["char"]("Reaver B"), world["char"]("Hero", npc=False)
    world["encounter"]((a, 20), (b, 10), (pc, 5))
    assert "Only the Story Weaver" in _queue(world, a, b, user=world["player"])[0]["text"]
    assert "two different NPCs" in _queue(world, a, pc)[0]["text"], "a player character is not an enemy"
    assert "two different NPCs" in _queue(world, a, a)[0]["text"]
    outsider = world["char"]("Not In Fight")
    assert "not in this encounter" in _queue(world, a, outsider)[0]["text"]
    ok = _queue(world, a, b)
    assert ok[0]["type"] == "enemy_combo_queued" and ok[0]["status"] == "holding" and ok[0]["name"] == "Chain Snap"
    assert "already committed" in _queue(world, a, b)[0]["text"], "one Combo at a time per NPC"


def test_the_hold_is_silent_and_the_sw_is_asked_to_fire_on_the_partners_turn(world):
    a, b, pc = world["char"]("Reaver C"), world["char"]("Reaver D"), world["char"]("Hero2", npc=False)
    enc = world["encounter"]((a, 20), (b, 10), (pc, 5))
    enc.current_turn_index = 2                     # it is the hero's turn; the order wraps to A (held) and lands on B
    world["db"].commit()
    assert _queue(world, a, b)[0]["type"] == "enemy_combo_queued"
    pub, priv = _advance(world)
    assert not any(m.get("skipped_holding") for m in pub if m.get("type") == "turn_advance"), "the table is not told who is holding"
    assert not any(m.get("type") in ("combo_holding", "combo_fire_ready", "enemy_combo_fire_ready") for m in pub)
    ready = [(uid, m) for uid, m in priv if m.get("type") == "enemy_combo_fire_ready"]
    assert len(ready) == 1 and ready[0][0] == str(world["sw"].id), "only the Story Weaver is asked"
    assert [x["name"] for x in ready[0][1]["proposer"]["abilities"]] == ["Bolt"]
    assert not any(uid == str(world["player"].id) for uid, _ in priv)
    world["db"].expire_all()
    combo = world["db"].query(world["PendingCombo"]).filter_by(proposer_character_id=a.id).one()
    assert combo.status == "ready"


def _fire(world, combo, picks, dice):
    from routes import campaign_websocket as cw
    ws = _WS()
    pub = []

    async def fake_broadcast(_cid, m):
        pub.append(m)

    orig = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        seq = iter(dice)
        with mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)]):
            asyncio.run(cw._handle_enemy_combo_fire(world["camp"].id, world["sw"].id,
                                                    {"combo_id": str(combo.id), **picks}, ws, world["db"]))
    finally:
        cw.manager.broadcast = orig
    world["db"].expire_all()
    return ws.sent, pub


def test_firing_resolves_like_a_players_combo_and_only_once_per_encounter(world):
    a, b, pc = world["char"]("Reaver E"), world["char"]("Reaver F"), world["char"]("Hero3", npc=False, dp=20)
    enc = world["encounter"]((a, 20), (b, 10), (pc, 5))
    enc.current_turn_index = 2
    world["db"].commit()
    _queue(world, a, b)
    _advance(world)
    combo = world["db"].query(world["PendingCombo"]).filter_by(proposer_character_id=a.id).one()
    # a pick with no target for a damage ability is refused and nothing is spent
    sent, _ = _fire(world, combo, {"proposer": {"slot": 1, "target": ""}, "acceptor": {"slot": 1, "target": pc.name}}, dice=[])
    assert sent[0]["type"] == "enemy_combo_pick_rejected" and (a.current_uses, b.current_uses) == (10, 10)
    # both hit the hero: each 4 + IP3 + Edge1 + BAP2 = 10 vs the hero's 1 + IP3 + Edge1 = 5, so 5 damage each
    sent, pub = _fire(world, combo, {"proposer": {"slot": 1, "target": pc.name}, "acceptor": {"slot": 1, "target": pc.name}},
                      dice=[4, 1, 4, 1])
    card = next(m for m in pub if m.get("type") == "combo_resolved")
    assert card["bond_name"] == "Chain Snap" and card["proposer"]["damage"] == 5 and card["acceptor"]["damage"] == 5
    assert pc.dp == 10 and (a.current_uses, b.current_uses) == (9, 9)
    assert world["db"].get(world["PendingCombo"], combo.id).status == "fired"
    # once per encounter: the same pair cannot be queued again
    assert "already fired this encounter" in _queue(world, a, b)[0]["text"]


def test_getting_hit_alone_does_not_cancel_but_dropping_to_zero_does(world):
    from routes import campaign_websocket as cw
    a, b, pc = world["char"]("Reaver G"), world["char"]("Reaver H"), world["char"]("Hero4", npc=False)
    world["encounter"]((a, 20), (b, 10), (pc, 5))
    _queue(world, a, b)
    sw_msgs, pub = [], []

    async def fake_broadcast(_cid, m):
        pub.append(m)

    async def fake_send(_cid, uid, m):
        sw_msgs.append(m)

    orig_b, orig_s = cw.manager.broadcast, cw.manager.send_to_user
    cw.manager.broadcast, cw.manager.send_to_user = fake_broadcast, fake_send
    try:
        a.dp = 8                                                      # hurt, still standing
        world["db"].commit()
        asyncio.run(cw.cancel_holding_combos_on_damage(world["camp"].id, a.id, world["db"]))
        combo = world["db"].query(world["PendingCombo"]).filter_by(proposer_character_id=a.id).one()
        assert combo.status == "holding", "a hit alone does not cancel it"
        b.dp = 0                                                      # the ACCEPTOR drops to 0: that cancels it
        world["db"].commit()
        asyncio.run(cw.cancel_holding_combos_on_damage(world["camp"].id, b.id, world["db"]))
    finally:
        cw.manager.broadcast, cw.manager.send_to_user = orig_b, orig_s
    world["db"].expire_all()
    assert world["db"].get(world["PendingCombo"], combo.id).status == "cancelled"
    assert pub == [], "an enemy Combo's cancellation is not announced to the table"
    assert any(m.get("type") == "combo_cancelled" and m.get("enemy") for m in sw_msgs), "the Story Weaver is told"


def test_a_players_combo_is_also_cancelled_by_the_acceptor_dropping_not_by_a_hit(world):
    from routes import campaign_websocket as cw
    p1, p2 = world["char"]("PlayerA", npc=False), world["char"]("PlayerB", npc=False)
    enc = world["encounter"]((p1, 20), (p2, 10))
    world["db"].add(world["PendingCombo"](id=uuid.uuid4(), encounter_id=enc.id, campaign_id=world["camp"].id,
                                          proposer_character_id=p1.id, acceptor_character_id=p2.id, status="holding"))
    world["db"].commit()
    pub = []

    async def fake_broadcast(_cid, m):
        pub.append(m)

    orig = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        p1.dp = 3
        world["db"].commit()
        asyncio.run(cw.cancel_holding_combos_on_damage(world["camp"].id, p1.id, world["db"]))
        assert pub == [], "the proposer was hit but is still up: the Combo holds (it used to cancel)"
        p2.dp = -2
        world["db"].commit()
        asyncio.run(cw.cancel_holding_combos_on_damage(world["camp"].id, p2.id, world["db"]))
    finally:
        cw.manager.broadcast = orig
    assert any(m.get("type") == "combo_cancelled" and m.get("reason") == "partner_down" for m in pub)


def test_the_sw_can_call_off_a_queued_enemy_combo_for_free(world):
    from routes import campaign_websocket as cw
    a, b = world["char"]("Reaver I"), world["char"]("Reaver J")
    world["encounter"]((a, 20), (b, 10))
    _queue(world, a, b)
    combo = world["db"].query(world["PendingCombo"]).filter_by(proposer_character_id=a.id).one()
    ws = _WS()
    asyncio.run(cw._handle_enemy_combo_cancel(world["camp"].id, world["sw"].id, {"combo_id": str(combo.id)}, ws, world["db"]))
    world["db"].expire_all()
    assert world["db"].get(world["PendingCombo"], combo.id).status == "cancelled" and ws.sent[0]["type"] == "enemy_combo_cancelled"
    assert (a.current_uses, b.current_uses) == (10, 10)
    assert _queue(world, a, b)[0]["type"] == "enemy_combo_queued", "a cancelled Combo does not count as fired"


def test_the_sw_can_get_the_fire_prompt_again(world):
    from routes import campaign_websocket as cw
    a, b, pc = world["char"]("Reaver K"), world["char"]("Reaver L"), world["char"]("Hero5", npc=False)
    enc = world["encounter"]((a, 20), (b, 10), (pc, 5))
    enc.current_turn_index = 2
    world["db"].commit()
    _queue(world, a, b)
    _advance(world)                                     # the prompt goes out once (and could have been lost)
    combo = world["db"].query(world["PendingCombo"]).filter_by(proposer_character_id=a.id).one()
    priv = []

    async def fake_send(_cid, uid, m):
        priv.append((str(uid), m))

    orig = cw.manager.send_to_user
    cw.manager.send_to_user = fake_send
    try:
        asyncio.run(cw._handle_enemy_combo_resend(world["camp"].id, world["player"].id, {"combo_id": str(combo.id)}, _WS(), world["db"]))
        assert priv == [], "a player cannot ask for it"
        asyncio.run(cw._handle_enemy_combo_resend(world["camp"].id, world["sw"].id, {"combo_id": str(combo.id)}, _WS(), world["db"]))
    finally:
        cw.manager.send_to_user = orig
    assert len(priv) == 1 and priv[0][0] == str(world["sw"].id) and priv[0][1]["type"] == "enemy_combo_fire_ready"
