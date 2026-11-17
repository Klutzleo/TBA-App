"""
Tethers under rules v3.1 (Phase 8).

- Scale -4 to +4 (Grief and Emptiness -3 to +3). Up to 3 STORY Tethers; Marked by Death, Grief and Emptiness are extra.
- Only the strongest bonus and the strongest penalty count, and you take the difference.
- A Marked-by-Death scar or fear becomes a Tether; a limitation just stays.
- An active Tether rides The Calling roll. An Ally's death gives its player Emptiness, anyone else Bonded Grief, and
  every Combo with it is lost. Grief runs -1 to -3.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tethers.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import tethers as T  # noqa: E402


def test_scale_and_net_rule():
    assert T.clamp_tether_modifier(9) == 4 and T.clamp_tether_modifier(-9) == -4
    assert T.clamp_tether_modifier(9, "grief") == 3 and T.clamp_tether_modifier(-9, "emptiness") == -3
    assert T.clamp_tether_modifier("junk") == 0
    assert T.net_modifier([3, -4]) == -1                      # the book's example
    assert T.net_modifier([1, 3, -1, -2]) == 3 + -2           # only the strongest of each
    assert T.net_modifier([]) == 0
    net, rows = T.active_net([{"is_active": True, "modifier": 2, "description": "a"},
                              {"is_active": True, "modifier": 3, "description": "b"},
                              {"is_active": False, "modifier": 4, "description": "off"},
                              {"is_active": True, "modifier": -1, "description": "c"}])
    assert net == 3 - 1 and len(rows) == 3


def test_extra_tethers_do_not_use_story_slots():
    mixed = [{"source": "marked"}, {"source": "grief"}, {"source": "emptiness"}, {"description": "story"}, {"source": "story"}]
    assert T.story_tether_count(mixed) == 2


@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Bond, Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, p1, p2 = user("sw"), user("p1"), user("p2")
    camp = Campaign(id=uuid.uuid4(), name="Tether test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player")):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role))
    db.commit()

    def pc(owner, name, **kw):
        kw.setdefault("dp", -10)
        c = Character(id=uuid.uuid4(), name=f"{name}_{tag}", owner_id=str(owner.id), user_id=owner.id,
                      campaign_id=camp.id, level=2, pp=2, ip=3, sp=1, max_dp=10, edge=1,
                      attack_style="1d4", defense_die="1d4", **kw)
        db.add(c)
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, p1=p1, p2=p2, pc=pc, Bond=Bond, tag=tag)
    db.close()


def _req(body):
    async def _json():
        return body
    return SimpleNamespace(json=_json, state=SimpleNamespace(request_id="t"))


def test_three_story_tethers_then_the_fourth_is_refused_but_extras_still_fit(world):
    from fastapi import HTTPException
    from routes.character_fastapi import add_tether
    c = world["pc"](world["p1"], "Slots", dp=5)
    for i in range(3):
        r = asyncio.run(add_tether(str(c.id), _req({"description": f"belief {i}", "modifier": 9}), world["db"], world["sw"]))
    assert all(t["modifier"] == 4 for t in r["tethers"]), "clamped to the -4..+4 scale"
    with pytest.raises(HTTPException) as e:
        asyncio.run(add_tether(str(c.id), _req({"description": "a fourth", "modifier": 1}), world["db"], world["sw"]))
    assert e.value.status_code == 400
    r = asyncio.run(add_tether(str(c.id), _req({"description": "Marked", "modifier": -2, "source": "marked"}),
                               world["db"], world["sw"]))
    assert len(r["tethers"]) == 4, "an extra Tether does not use a story slot"
    # a player cannot smuggle in an extra Tether to dodge the limit
    with pytest.raises(HTTPException):
        asyncio.run(add_tether(str(c.id), _req({"description": "sneaky", "modifier": 1, "source": "grief"}),
                               world["db"], world["p1"]))


def test_editing_a_tether_stays_on_the_scale_and_the_cache_is_the_net(world):
    from routes.character_fastapi import add_tether, update_tether
    c = world["pc"](world["p1"], "Edit", dp=5)
    a = asyncio.run(add_tether(str(c.id), _req({"description": "a", "modifier": 1}), world["db"], world["sw"]))["tethers"][0]["id"]
    b = asyncio.run(add_tether(str(c.id), _req({"description": "b", "modifier": -1}), world["db"], world["sw"]))["tethers"][1]["id"]
    asyncio.run(update_tether(str(c.id), a, _req({"is_active": True, "modifier": 99}), world["db"], world["sw"]))
    r = asyncio.run(update_tether(str(c.id), b, _req({"is_active": True, "modifier": -99}), world["db"], world["sw"]))
    assert [t["modifier"] for t in r["tethers"]] == [4, -4]
    assert r["active_tether_modifier"] == 0, "+4 and -4 leave 0"


def test_a_scar_or_fear_becomes_a_tether_and_a_limitation_does_not(world):
    from routes.character_fastapi import add_battle_scar
    c = world["pc"](world["p1"], "Marked", dp=1)
    scar = asyncio.run(add_battle_scar(str(c.id), _req({}), {"scar": "A burn across the arm", "kind": "scar", "modifier": -2},
                                       world["db"], world["sw"]))
    assert scar["tether"]["source"] == "marked" and scar["tether"]["modifier"] == -2 and scar["tether"]["is_active"] is False
    fear = asyncio.run(add_battle_scar(str(c.id), _req({}), {"scar": "Afraid of the dark", "kind": "fear"},
                                       world["db"], world["sw"]))
    assert fear["tether"]["modifier"] == -1                      # the default strength
    lim = asyncio.run(add_battle_scar(str(c.id), _req({}), {"scar": "Cannot use Blink", "kind": "limitation"},
                                      world["db"], world["sw"]))
    assert lim["tether"] is None
    world["db"].expire_all()
    assert [t["source"] for t in c.tethers] == ["marked", "marked"]
    assert [s["kind"] for s in c.battle_scars] == ["scar", "fear", "limitation"]


def _calling(world, c, player_die, sw_die):
    from routes.character_fastapi import resolve_the_calling
    rolls = iter([player_die, sw_die])
    with mock.patch("backend.roll_logic.roll_dice", side_effect=lambda *_a, **_k: [next(rolls)]):
        r = asyncio.run(resolve_the_calling(str(c.id), _req({}), {"stat_choice": "ip"}, world["db"], world["p1"]))
    world["db"].expire_all()
    return r


def test_an_active_tether_rides_the_calling_roll_and_only_the_strongest_counts(world):
    c = world["pc"](world["p1"], "Calling1", in_calling=True, tethers=[
        {"id": "a", "description": "for her", "is_active": True, "modifier": 3, "source": "story"},
        {"id": "b", "description": "small", "is_active": True, "modifier": 1, "source": "story"},
        {"id": "c", "description": "fear", "is_active": True, "modifier": -2, "source": "marked"},
        {"id": "d", "description": "off", "is_active": False, "modifier": 4, "source": "story"}])
    r = _calling(world, c, player_die=3, sw_die=6)     # 3 + IP3 + Edge1 + (3 - 2) = 8 vs 6
    assert r["tether_bonus"] == 1 and r["player_total"] == 8 and r["margin"] == 2


def test_an_allys_death_gives_emptiness_to_its_player_and_grief_to_the_bonded(world):
    owner, friend = world["pc"](world["p1"], "Owner", dp=5), world["pc"](world["p2"], "Friend", dp=5)
    ally = world["pc"](world["p1"], "Wolf", is_ally=True, parent_character_id=owner.id, in_calling=True)
    db = world["db"]
    b_owner = world["Bond"](id=uuid.uuid4(), campaign_id=world["camp"].id, character_id_a=owner.id, character_id_b=ally.id)
    b_friend = world["Bond"](id=uuid.uuid4(), campaign_id=world["camp"].id, character_id_a=friend.id, character_id_b=ally.id)
    db.add_all([b_owner, b_friend])
    db.commit()
    r = _calling(world, ally, player_die=1, sw_die=6)           # the Ally loses The Calling
    assert r["outcome"] == "dead"
    db.expire_all()
    assert ally.status == "archived"
    assert [(t["source"], t["modifier"]) for t in owner.tethers] == [("emptiness", -1)]
    assert [(t["source"], t["modifier"]) for t in friend.tethers] == [("grief", -1)]
    assert db.get(world["Bond"], b_owner.id).broken_at is not None and db.get(world["Bond"], b_friend.id).broken_at is not None


def test_a_player_character_dying_does_not_trigger_the_ally_rules(world):
    pcx = world["pc"](world["p1"], "Plain", in_calling=True)
    r = _calling(world, pcx, player_die=1, sw_die=6)
    assert r["outcome"] == "dead" and not (pcx.tethers or [])


def test_breaking_a_bond_applies_grief_between_minus_one_and_minus_three(world):
    from routes.bonds import break_bond
    a, b = world["pc"](world["p1"], "GriefA", dp=5), world["pc"](world["p2"], "GriefB", dp=5)
    bond = world["Bond"](id=uuid.uuid4(), campaign_id=world["camp"].id, character_id_a=a.id, character_id_b=b.id)
    world["db"].add(bond)
    world["db"].commit()
    asyncio.run(break_bond(world["camp"].id, bond.id, -5, world["sw"], world["db"]))   # a -5 request is clamped
    world["db"].expire_all()
    assert [t["modifier"] for t in a.tethers] == [-3] and [t["modifier"] for t in b.tethers] == [-3]
