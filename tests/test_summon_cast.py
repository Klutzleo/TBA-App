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

    def pc(name, summon_name="The Progeny"):
        c = Character(id=uuid.uuid4(), name=name, owner_id=str(player.id), user_id=player.id, campaign_id=camp.id,
                      level=2, pp=2, ip=3, sp=1, dp=15, max_dp=15, edge=1, attack_style="1d6", defense_die="1d8",
                      max_uses_per_encounter=4, current_uses=4)   # level 2: one shared pool of level + 2
        db.add(c)
        db.commit()
        db.add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=1, ability_type="spell",
                       display_name=summon_name, macro_command="/summon", power_source="IP",
                       effect_type="damage", die="1d6", is_summon=True, max_uses=3, uses_remaining=3))
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, player=player, pc=pc)
    db.close()


def cast(world, user, caster, speaker_type=None, command="/summon"):
    from routes import campaign_websocket as cw
    db = world["db"]
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        payload = {"type": "ability_cast", "raw_command": command}
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


def test_calling_a_summon_is_free_and_a_second_cast_commands_the_existing_summon(world):
    caster = world["pc"]("Spender")
    sent = cast(world, world["player"], caster, speaker_type="pc")  # the real client always names the speaker
    world["db"].expire_all()
    assert summon_of(world, caster) is not None, [m.get("text") or m.get("message") for m in sent]
    assert caster.current_uses == 4, "calling a summon costs no use (rules v3.1); its upkeep is paid when it acts"
    # casting again with no target does not create a second summon
    cast(world, world["player"], caster, speaker_type="pc")
    from backend.models import Character
    assert world["db"].query(Character).filter_by(summoner_id=caster.id, is_summon=True).count() == 1


def _dummy(world, name, dp=30):
    from backend.models import Character
    d = Character(id=uuid.uuid4(), name=name, owner_id=str(world["sw"].id), campaign_id=world["camp"].id, is_npc=True,
                  level=1, pp=1, ip=1, sp=1, dp=dp, max_dp=dp, edge=0, attack_style="1d4", defense_die="1d4")
    world["db"].add(d)
    world["db"].commit()
    return d


def _fixed_dice(values):
    """Patch both places the cast code rolls from: attack die first, then the defender's die."""
    import contextlib
    from unittest import mock
    seq = iter(values)
    return contextlib.ExitStack(), mock.patch("routes.campaign_websocket.roll_dice", side_effect=lambda *_a, **_k: [next(seq)])


def test_a_summon_that_is_out_acts_like_a_real_attack_and_costs_one_use(world):
    """The reported bug: with the summon out, '/summon @Target' produced a card with no roll and nothing happened."""
    from backend.models import Ability, Message
    caster = world["pc"]("Actor")
    cast(world, world["player"], caster, speaker_type="pc")                      # summons it (free)
    target = _dummy(world, "Scarecrow")
    _, patch = _fixed_dice([5, 2])                                                # attack 5+IP3+Edge1=9, defense 2+1+0=3
    with patch:
        sent = cast(world, world["player"], caster, speaker_type="pc", command="/summon @[Scarecrow]")
    world["db"].expire_all()
    card = next(m for m in sent if m.get("type") == "ability_cast")
    assert card["acting_summon"] == "The Progeny"
    assert card["results"][0]["damage"] == 6 and card["results"][0]["new_dp"] == 24
    assert "attack_breakdown" in card["results"][0]
    assert card["message_id"]                                                     # saved, so it survives a refresh and can be Boosted
    saved = world["db"].query(Message).filter_by(id=card["message_id"]).one()
    assert saved.extra_data["caster_char_id"] == str(caster.id)
    assert caster.current_uses == 3, "calling it was free; acting this round is its upkeep: 1 use from the pool (4 -> 3)"


def test_commanding_a_summon_with_no_target_asks_for_one_and_does_nothing(world):
    caster = world["pc"]("Aimless")
    cast(world, world["player"], caster, speaker_type="pc")
    sent = cast(world, world["player"], caster, speaker_type="pc")
    assert not any(m.get("type") == "ability_cast" for m in sent)
    assert any("Pick a target" in (m.get("text") or "") for m in sent)


def test_a_summon_fades_when_its_summoner_is_out_of_uses(world):
    caster = world["pc"]("Spent")
    cast(world, world["player"], caster, speaker_type="pc")
    assert summon_of(world, caster) is not None
    caster.current_uses = 0                                        # the shared pool is empty
    world["db"].commit()
    _dummy(world, "Straw Man")
    sent = cast(world, world["player"], caster, speaker_type="pc", command="/summon @[Straw Man]")
    assert not any(m.get("type") == "ability_cast" for m in sent), "no upkeep paid, so it does not act"
    assert any(m.get("type") == "summon_dismissed" and m.get("reason") == "out_of_uses" for m in sent)
    assert summon_of(world, caster) is None


def test_calling_a_summon_works_even_with_no_uses_left(world):
    caster = world["pc"]("Empty")
    caster.current_uses = 0
    world["db"].commit()
    cast(world, world["player"], caster, speaker_type="pc")
    assert summon_of(world, caster) is not None, "calling is free, so an empty pool does not stop it"


def test_initiative_rows_remember_they_are_summons(world):
    """After a reload or re-sort the row used to turn into a plain NPC (no pips, Dismiss or Act)."""
    from routes.campaign_websocket import summon_order_fields
    caster = world["pc"]("Remembered")
    cast(world, world["player"], caster, speaker_type="pc")
    s = summon_of(world, caster)
    f = summon_order_fields(s, world["db"])
    assert f["is_summon"] and f["summon_id"] == str(s.id) and f["summoner_name"] == "Remembered"
    assert summon_order_fields(caster, world["db"]) == {}



# ---- rules v3.1 summons: hits, durability, the summoner going down, no DP drain -----------------------------------

def _striker(world, name="Striker", dp=20):
    """A PC with a damage spell, to attack a summon or its summoner."""
    from backend.models import Ability
    c = world["pc"](name)
    c.dp = dp
    world["db"].add(Ability(id=uuid.uuid4(), character_id=c.id, slot_number=2, ability_type="spell",
                            display_name="Bolt", macro_command="/bolt", power_source="IP", effect_type="damage",
                            die="1d6", max_uses=9, uses_remaining=9))
    world["db"].commit()
    return c


def test_summon_durability_by_level():
    from routes.campaign_websocket import summon_durability
    assert [summon_durability(l) for l in range(1, 11)] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 4]
    assert summon_durability(12) == 4


def test_an_attack_only_hits_a_summon_if_it_beats_the_summons_defense(world):
    """Summon defense = summoner's Defense Die (1d8) + the summoning stat (IP 3) + Edge (1). An attack that merely
    ties does not hit. Before, any attack that targeted a summon hit it automatically."""
    caster, striker = world["pc"]("Owner", summon_name="Spirit One"), _striker(world)
    cast(world, world["player"], caster, speaker_type="pc")
    summon = summon_of(world, caster)
    _, patch = _fixed_dice([3, 3])                                  # attack 3+IP3+Edge1 = 7, defense 3+3+1 = 7: a tie
    with patch:
        sent = cast(world, world["player"], striker, speaker_type="pc", command=f"/bolt @[{summon.name}]")
    card = next(m for m in sent if m.get("type") == "ability_cast")
    assert card["results"][0]["outcome"] == "miss" and "attack_breakdown" in card["results"][0]
    assert summon_of(world, caster) is not None and summon_of(world, caster).dp == 1
    _, patch = _fixed_dice([4, 3])                                  # attack 8 beats defense 7: a hit
    with patch:
        sent = cast(world, world["player"], striker, speaker_type="pc", command=f"/bolt @[{summon.name}]")
    assert any(m.get("type") == "summon_dismissed" and m.get("reason") == "defeated" for m in sent)
    assert summon_of(world, caster) is None                         # level 2 summon: 1 hit


def test_a_buff_on_the_summon_changes_its_defense(world):
    from backend.buffs import add_effect
    caster, striker = world["pc"]("Owner2", summon_name="Spirit Two"), _striker(world, "Striker2")
    cast(world, world["player"], caster, speaker_type="pc")
    summon = summon_of(world, caster)
    add_effect(world["db"], campaign_id=world["camp"].id, character_id=summon.id, name="Ward", modifier=2,
               modifier_type="ip", duration_rounds=2, applied_by="t")
    world["db"].commit()
    _, patch = _fixed_dice([4, 3])                                  # 8 vs 7+2 = 9: now a miss
    with patch:
        sent = cast(world, world["player"], striker, speaker_type="pc", command=f"/bolt @[{summon.name}]")
    r = next(m for m in sent if m.get("type") == "ability_cast")["results"][0]
    assert r["outcome"] == "miss" and "Effects(+2)" in r["defense_breakdown"]


def test_the_summon_vanishes_when_its_summoner_drops_to_zero_and_stays_gone(world):
    caster, striker = world["pc"]("Doomed"), _striker(world, "Striker3")
    cast(world, world["player"], caster, speaker_type="pc")
    assert summon_of(world, caster) is not None
    caster.dp = 1
    world["db"].commit()
    _, patch = _fixed_dice([6, 1])                                  # a big hit on the summoner
    with patch:
        sent = cast(world, world["player"], striker, speaker_type="pc", command=f"/bolt @[{caster.name}]")
    world["db"].expire_all()
    assert caster.dp <= 0
    assert summon_of(world, caster) is None
    assert any(m.get("type") == "summon_dismissed" and m.get("reason") == "summoner_down" for m in sent)
    caster.dp = 10                                                  # healing them does not bring it back
    world["db"].commit()
    assert summon_of(world, caster) is None


def test_orphan_cleanup_removes_summons_whose_summoner_is_down(world):
    from routes import campaign_websocket as cw
    caster = world["pc"]("Orphaner")
    cast(world, world["player"], caster, speaker_type="pc")
    caster.dp = 0                                                   # downed by some path that has no summon hook
    world["db"].commit()
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        asyncio.run(cw._cleanup_orphan_summons(world["camp"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    assert summon_of(world, caster) is None and any(m.get("type") == "summon_dismissed" for m in sent)


def test_a_new_round_no_longer_drains_the_summoner(world):
    """v3.1: upkeep is a use each time the summon acts, not 1 DP every round."""
    from backend.models import Encounter, InitiativeRoll
    from routes import campaign_websocket as cw
    caster = world["pc"]("Undrained")
    cast(world, world["player"], caster, speaker_type="pc")
    enc = Encounter(id=uuid.uuid4(), campaign_id=world["camp"].id, is_active=True, round_number=1, current_turn_index=0)
    world["db"].add(enc)
    world["db"].commit()
    world["db"].add(InitiativeRoll(id=uuid.uuid4(), encounter_id=enc.id, character_id=caster.id, name=caster.name,
                                   roll_result=10))
    world["db"].commit()

    class WS:
        async def send_json(self, _m):
            pass

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        for _ in range(3):                                          # a lone combatant: every turn is a new round
            asyncio.run(cw.advance_turn(world["camp"].id, world["sw"].id, world["db"], WS()))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert caster.dp == 15, "the summoner keeps their DP"
    enc.is_active = False
    world["db"].commit()


def _basic_attack(world, attacker, target_name, atk_die, def_die):
    from routes import campaign_websocket as cw
    sent = []

    async def fake_broadcast(_cid, msg):
        sent.append(msg)

    class WS:
        async def send_json(self, m):
            sent.append(m)

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        from unittest import mock
        with mock.patch("backend.roll_logic.roll_dice", return_value=[atk_die]), \
                mock.patch("backend.roll_logic.roll_die", return_value=def_die):
            asyncio.run(cw.handle_combat_command(world["camp"].id, {"type": "combat_command",
                        "raw_command": f"/attack @[{target_name}]", "attacker_id": str(attacker.id)},
                        WS(), world["sw"].id, world["db"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    return sent


def test_a_weapon_attack_on_a_summon_must_also_beat_its_defense(world):
    """Weapon attacks use the same summon defense (summoner's Defense Die + IP + Edge) and count hits, not damage."""
    from backend.models import Character
    caster = world["pc"]("Owner3", summon_name="Spirit Three")
    cast(world, world["player"], caster, speaker_type="pc")
    att = Character(id=uuid.uuid4(), name=f"Swordsman_{uuid.uuid4().hex[:6]}", owner_id=str(world["sw"].id),
                    campaign_id=world["camp"].id, is_npc=True, level=2, pp=3, ip=1, sp=2, dp=20, max_dp=20, edge=1,
                    attack_style="1d4", defense_die="1d4")
    world["db"].add(att)
    world["db"].commit()
    sent = _basic_attack(world, att, "Spirit Three", atk_die=3, def_die=3)      # 3+PP3+1 = 7 vs 3+IP3+1 = 7: a tie
    assert summon_of(world, caster) is not None and summon_of(world, caster).dp == 1
    sent = _basic_attack(world, att, "Spirit Three", atk_die=4, def_die=3)      # 8 vs 7: a hit
    assert summon_of(world, caster) is None
    assert any(m.get("type") == "summon_dismissed" and m.get("reason") == "defeated" for m in sent), sent


def test_a_boost_that_turns_a_miss_into_a_hit_defeats_the_summon_by_one_hit_not_by_margin(world):
    from backend.models import Message
    from routes import campaign_websocket as cw
    from routes.character_fastapi import _boost_ability_cast
    caster, striker = world["pc"]("Owner4", summon_name="Spirit Four"), _striker(world, "Striker4")
    cast(world, world["player"], caster, speaker_type="pc")
    summon = summon_of(world, caster)
    summon.dp = 3                                                    # durability 3, so one hit must not kill it
    summon.max_dp = 3
    world["db"].commit()
    _, patch = _fixed_dice([3, 3])                                  # a tie: a miss
    with patch:
        sent = cast(world, world["player"], striker, speaker_type="pc", command=f"/bolt @[{summon.name}]")
    card = next(m for m in sent if m.get("type") == "ability_cast")
    assert card["results"][0]["outcome"] == "miss"
    msg = world["db"].query(Message).filter_by(id=card["message_id"]).one()

    async def fake_broadcast(_cid, _m):
        pass

    original = cw.manager.broadcast
    cw.manager.broadcast = fake_broadcast
    try:
        # +5 BAP-sized bonus: the margin becomes 5, but against a summon that is still exactly ONE hit
        asyncio.run(_boost_ability_cast(world["db"], striker, msg, dict(msg.extra_data), [{"type": "bap", "bonus": 5}],
                                        5, str(msg.id), world["player"]))
    finally:
        cw.manager.broadcast = original
    world["db"].expire_all()
    assert summon_of(world, caster) is not None and summon_of(world, caster).dp == 2
