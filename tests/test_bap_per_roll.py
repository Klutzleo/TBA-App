"""
BAP is never banked. The Story Weaver adds it to ONE specific roll (the Boost), and a few things include it automatically
(a stat check the SW approved BAP for, and Combos). These tests pin that down end to end.

An ability cast is made through the real cast handler, so the stored message has exactly the shape the live game stores.
"""
import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bap_per_roll.db")
os.environ.setdefault("API_KEY", "devkey")

BAP = 3            # the caster's BAP
CASTER_STAT = 2    # IP
TARGET_STAT = 1


@pytest.fixture(scope="module")
def client():
    from backend.app import application
    from backend.db import init_db
    init_db()
    with TestClient(application) as c:
        yield c


@pytest.fixture(scope="module")
def world(client):
    from backend.auth.jwt import create_access_token
    from backend.db import SessionLocal
    from backend.models import Campaign, CampaignMembership, Character, User

    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    def bearer(u):
        return {"Authorization": f"Bearer {create_access_token(str(u.id), u.email, u.username)}"}

    sw, player, other_sw = user("sw"), user("pl"), user("osw")

    def campaign(owner):
        c = Campaign(id=uuid.uuid4(), name=f"C {uuid.uuid4().hex[:6]}", description="x" * 12, created_by_user_id=owner.id,
                     created_by_id=str(owner.id), story_weaver_id=owner.id)
        db.add(c)
        db.commit()
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=c.id, user_id=owner.id, role="story_weaver"))
        db.commit()
        return c

    camp, other_camp = campaign(sw), campaign(other_sw)
    db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=player.id, role="player"))
    db.commit()

    counter = {"n": 0}

    def pc(name, campaign_row=None, owner=None, **kw):
        counter["n"] += 1
        c = Character(id=uuid.uuid4(), name=f"{name}{counter['n']}", owner_id=str((owner or player).id), user_id=(owner or player).id,
                      campaign_id=(campaign_row or camp).id, level=2, pp=CASTER_STAT, ip=CASTER_STAT, sp=1, dp=kw.pop("dp", 15),
                      max_dp=15, edge=1, bap=BAP, attack_style="1d6", defense_die="1d6", **kw)
        db.add(c)
        db.commit()
        return c

    def ability(c, effect_type, macro, die="1d6", debuff_stat=None):
        from backend.models import Ability
        a = Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell", display_name=f"Spell {macro}",
                    macro_command=macro, power_source="IP", effect_type=effect_type, die=die, debuff_stat=debuff_stat,
                    max_uses=3, uses_remaining=3)
        db.add(a)
        db.commit()
        return a

    yield dict(db=db, sw=sw, player=player, other_sw=other_sw, camp=camp, other_camp=other_camp, pc=pc, ability=ability,
               h_sw=bearer(sw), h_pl=bearer(player), h_other=bearer(other_sw), user=user)
    db.close()


import contextlib


@contextlib.contextmanager
def dice(fixed):
    """Fix every die roll. `fixed` is a value for all dice, or a dict mapping a die string to its value.
    Some handlers import roll_dice inside the function, so it is patched at its source as well as in the hub."""
    from backend import roll_logic
    from routes import campaign_websocket as cw
    fn = (lambda notation: [fixed[notation]]) if isinstance(fixed, dict) else (lambda notation: [fixed])
    saved = (cw.roll_dice, roll_logic.roll_dice)
    cw.roll_dice = roll_logic.roll_dice = fn
    try:
        yield
    finally:
        cw.roll_dice, roll_logic.roll_dice = saved


def cast(world, caster, macro, target_name, fixed):
    """Cast through the real handler with fixed dice. `fixed` maps a die string to the single value it rolls."""
    from routes import campaign_websocket as cw
    db = world["db"]
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    orig_broadcast = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": f"{macro} @{target_name}", "speaker_id": str(caster.id), "speaker_type": "pc"}
        with dice(fixed):
            asyncio.run(cw.handle_ability_cast(world["camp"].id, payload, None, caster.user_id, db))
    finally:
        cw.manager.broadcast = orig_broadcast
    from backend.models import Message
    db.expire_all()
    msg = db.query(Message).filter_by(campaign_id=str(world["camp"].id), message_type="ability_cast").order_by(Message.created_at.desc()).first()
    return msg


def boost(client, headers, caster, msg, bap=True, tethers=()):
    return client.post(f"/api/characters/{caster.id}/apply-boosts", headers=headers, json={
        "message_id": str(msg.id), "use_bap": bap, "tether_ids": list(tethers), "roll_type": "ability_cast"})


def fresh(world, row):
    world["db"].expire_all()
    return world["db"].get(type(row), row.id)


# ------------------------------------------------------------------ damage

def test_boost_turns_a_missed_damage_cast_into_a_hit_and_updates_the_target(client, world):
    caster, target = world["pc"]("Caster"), world["pc"]("Target")
    world["ability"](caster, "damage", "/zap")
    # attack 1 + IP 2 + Edge 1 = 4 against defense 6 + PP 2 + Edge 1 = 9  ->  a clear miss
    msg = cast(world, caster, "/zap", target.name, {"1d6": 1})
    r = msg.extra_data["results"][0]
    assert r["damage"] == 0 and r["outcome"] == "miss"
    assert fresh(world, target).dp == 15

    # fixed dice: the attack die and the defense die are both 1d6, so use the sequence-free route: boost by BAP and
    # compare with the stored numbers instead of assuming the dice
    resp = boost(client, world["h_sw"], caster, msg)
    assert resp.status_code == 200, resp.text
    after = resp.json()["results"][0]
    expected_attack = r["attack_roll"] + BAP
    assert after["attack_roll"] == expected_attack
    assert after["damage"] == max(0, expected_attack - r["defense_roll"])
    assert after["new_dp"] == 15 - after["damage"] == fresh(world, target).dp
    assert f"BAP(+{BAP})" in after["attack_breakdown"]
    assert resp.json()["old_total"] == r["attack_roll"] and resp.json()["new_total"] == expected_attack

    # the stored card is updated, so a reload shows the boosted result
    stored = fresh(world, msg).extra_data
    assert stored["boost_applied"] is True and stored["results"][0]["damage"] == after["damage"]
    assert target.name in stored["narrative"]


def test_a_cast_can_only_be_boosted_once(client, world):
    caster, target = world["pc"]("Once"), world["pc"]("OnceT")
    world["ability"](caster, "damage", "/once")
    msg = cast(world, caster, "/once", target.name, {"1d6": 1})
    assert boost(client, world["h_sw"], caster, msg).status_code == 200
    dp = fresh(world, target).dp
    again = boost(client, world["h_sw"], caster, msg)
    assert again.status_code == 400 and "already" in again.json()["detail"].lower()
    assert fresh(world, target).dp == dp


def test_damage_never_takes_a_target_below_the_floor_or_heals_it_above_max(client, world):
    caster, target = world["pc"]("Floor"), world["pc"]("FloorT", dp=-8)
    world["ability"](caster, "damage", "/floor", die="1d6")
    msg = cast(world, caster, "/floor", target.name, {"1d6": 6})
    boost(client, world["h_sw"], caster, msg)
    assert -10 <= fresh(world, target).dp <= 15


# ------------------------------------------------------------------ heal and debuff

def test_boost_heals_more_and_never_above_max(client, world):
    caster, target = world["pc"]("Healer"), world["pc"]("Hurt", dp=5)
    world["ability"](caster, "heal", "/mend")
    msg = cast(world, caster, "/mend", target.name, {"1d6": 2})
    healed = msg.extra_data["results"][0]["healing"]
    resp = boost(client, world["h_sw"], caster, msg)
    assert resp.status_code == 200, resp.text
    r = resp.json()["results"][0]
    assert r["healing"] == healed + BAP
    assert fresh(world, target).dp == min(15, 5 + healed + BAP) == r["new_dp"]
    assert f"BAP(+{BAP})" in r["roll_breakdown"]


def test_boost_can_turn_a_resisted_debuff_into_one_that_lands(client, world):
    from backend.models import ActiveEffect
    caster, target = world["pc"]("Hexer"), world["pc"]("Hexed")
    world["ability"](caster, "debuff", "/hex", debuff_stat="IP")
    msg = cast(world, caster, "/hex", target.name, {"1d6": 1})
    r = msg.extra_data["results"][0]
    assert r["success"] is False
    world["db"].expire_all()
    assert world["db"].query(ActiveEffect).filter_by(character_id=target.id).count() == 0
    # make sure the boost is big enough to flip it
    need = r["defense_roll"] - r["caster_roll"] + 1
    assert BAP >= 0
    resp = boost(client, world["h_sw"], caster, msg)
    assert resp.status_code == 200, resp.text
    landed = resp.json()["results"][0]["success"]
    world["db"].expire_all()
    effects = world["db"].query(ActiveEffect).filter_by(character_id=target.id).all()
    assert landed == (BAP >= need)
    assert len(effects) == (1 if landed else 0)
    if landed:
        assert effects[0].modifier < 0 and effects[0].applied_by == caster.name


def test_a_buff_has_no_roll_to_boost(client, world):
    caster = world["pc"]("Buffer")
    world["ability"](caster, "buff", "/bless")
    msg = cast(world, caster, "/bless", caster.name, {"1d6": 1})
    resp = boost(client, world["h_sw"], caster, msg)
    assert resp.status_code == 400 and "no roll" in resp.json()["detail"]


# ------------------------------------------------------------------ who may boost what

def test_only_the_sw_of_that_campaign_can_boost(client, world):
    caster, target = world["pc"]("Auth"), world["pc"]("AuthT")
    world["ability"](caster, "damage", "/auth")
    msg = cast(world, caster, "/auth", target.name, {"1d6": 1})
    assert boost(client, world["h_pl"], caster, msg).status_code == 403
    assert boost(client, world["h_other"], caster, msg).status_code == 403
    assert fresh(world, msg).extra_data.get("boost_applied") is None


def test_a_roll_from_another_campaign_or_another_character_cannot_be_boosted(client, world):
    caster, target, bystander = world["pc"]("Own"), world["pc"]("OwnT"), world["pc"]("Other")
    world["ability"](caster, "damage", "/own")
    msg = cast(world, caster, "/own", target.name, {"1d6": 1})
    # boosting it "as" a different character in the same campaign is refused
    assert boost(client, world["h_sw"], bystander, msg).status_code == 400
    # a different campaign's SW and character cannot reach it at all
    foreign = world["pc"]("Foreign", campaign_row=world["other_camp"], owner=world["other_sw"])
    assert boost(client, world["h_other"], foreign, msg).status_code == 404
    assert fresh(world, msg).extra_data.get("boost_applied") is None


# ------------------------------------------------------------------ nothing is banked any more

def test_the_token_endpoints_and_token_state_are_gone(client, world):
    c = world["pc"]("Gone")
    for path in ("grant-bap-token", "revoke-bap-token"):
        assert client.post(f"/api/characters/{c.id}/{path}", headers=world["h_sw"], json={"token_type": "encounter"}).status_code in (404, 405)
    members = client.get(f"/api/campaigns/{world['camp'].id}/members", headers=world["h_sw"]).json()
    for m in members:
        assert "bap_token_active" not in (m.get("character") or {}) and "bap_token_type" not in (m.get("character") or {})


def test_a_leftover_token_flag_does_nothing_to_a_self_roll(world):
    """Beef-style leftover: the flag may still sit in the database, but nothing reads it."""
    from routes import campaign_websocket as cw
    c = world["pc"]("Leftover", bap_token_active=True, bap_token_type="encounter")
    db = world["db"]
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    orig_broadcast = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with dice(4):
            asyncio.run(cw.handle_stat_check(world["camp"].id, {"stat": "IP", "character_id": str(c.id), "use_bap": True}, world["sw"].id, None, db))
    finally:
        cw.manager.broadcast = orig_broadcast
    roll = next(m for m in sent if m.get("type") == "stat_roll")
    assert roll["bap_bonus"] == 0 and roll["total"] == 4 + CASTER_STAT + 1  # die + IP + Edge, no BAP
    assert "bap_token_consumed" not in roll


# ------------------------------------------------------------------ a stat check the SW approved BAP for

def _stat_check(world, character, bap_granted):
    from backend.models import StatCheckRequest
    req = StatCheckRequest(id=uuid.uuid4(), campaign_id=world["camp"].id, character_id=character.id, kind="stat", mode="character",
                           stat="IP", difficulty_die="1d6", difficulty_label="Easy", sw_roll=3, bap_granted=bap_granted,
                           status="pending", sw_user_id=world["sw"].id)
    world["db"].add(req)
    world["db"].commit()
    return req


def _roll_check(world, req, character):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    orig_broadcast = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with dice(4):
            asyncio.run(cw._handle_stat_check_roll(world["camp"].id, character.user_id, {"request_id": str(req.id)}, world["db"]))
    finally:
        cw.manager.broadcast = orig_broadcast
    return next(m for m in sent if m.get("type") == "stat_check_result")


def test_a_stat_check_granted_bap_includes_it_in_the_roll_and_banks_nothing(client, world):
    c = world["pc"]("Checked")
    result = _roll_check(world, _stat_check(world, c, bap_granted=True), c)
    assert result["bap_applied"] == BAP
    assert result["player_total"] == 4 + CASTER_STAT + 1 + BAP     # die + IP + Edge + BAP
    assert fresh(world, c).bap_token_active in (False, None)       # nothing banked


def test_a_stat_check_without_the_tickbox_has_no_bap(client, world):
    c = world["pc"]("Plain")
    result = _roll_check(world, _stat_check(world, c, bap_granted=False), c)
    assert result["bap_applied"] == 0 and result["player_total"] == 4 + CASTER_STAT + 1


def test_a_later_boost_cannot_add_bap_a_second_time_to_a_check_that_already_has_it(client, world):
    from backend.models import Message
    c = world["pc"]("Twice")
    req = _stat_check(world, c, bap_granted=True)
    _roll_check(world, req, c)
    world["db"].expire_all()
    msg = world["db"].query(Message).filter_by(campaign_id=str(world["camp"].id), message_type="stat_check_result").order_by(Message.created_at.desc()).first()
    resp = client.post(f"/api/characters/{c.id}/apply-boosts", headers=world["h_sw"], json={
        "message_id": str(msg.id), "use_bap": True, "tether_ids": [], "roll_type": "stat_check"})
    assert resp.status_code == 400 and "already" in resp.json()["detail"].lower()


# ------------------------------------------------------------------ Combos: full BAP on the roll, nothing banked

def test_a_fired_combo_adds_bap_to_both_rolls_and_banks_nothing(world):
    from types import SimpleNamespace
    from routes import campaign_websocket as cw
    a, b = world["pc"]("ComboA"), world["pc"]("ComboB")
    world["ability"](a, "damage", "/ca")
    world["ability"](b, "damage", "/cb")
    combo = SimpleNamespace(id=uuid.uuid4(), proposer_character_id=a.id, acceptor_character_id=b.id, proposer_ability_slot=1,
                            acceptor_ability_slot=1, bond=SimpleNamespace(combo_name="The Test", combo_description=""), status="locked")
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    orig_broadcast = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        with dice(4):
            asyncio.run(cw._resolve_combo(world["camp"].id, combo, world["db"]))
    finally:
        cw.manager.broadcast = orig_broadcast

    resolved = next(m for m in sent if m.get("type") == "combo_resolved")
    for who in ("proposer", "acceptor"):
        r = resolved[who]
        assert r["bap"] == BAP
        assert r["total"] == 4 + CASTER_STAT + 1 + BAP      # die + IP + Edge + full BAP, automatically
    assert fresh(world, a).bap_token_active in (False, None) and fresh(world, b).bap_token_active in (False, None)
