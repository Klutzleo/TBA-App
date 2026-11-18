"""
Vehicles V1 (rules v3.1.1): the numbers come from the Core's Vehicle Leveling Table, the Story Weaver creates a vehicle, players take
stations on it, and a vehicle never shows up as an NPC.
"""
import asyncio
import os
import re
import uuid

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_vehicles_v1.db")
os.environ.setdefault("API_KEY", "devkey")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- the numbers, checked against the Rulebook text itself
def _rulebook_vehicle_table():
    text = open(os.path.join(ROOT, "Rulebook.md"), encoding="utf-8").read()
    block = text[text.index("### Vehicle Leveling Table"):]
    rows = {}
    for line in block.splitlines()[1:40]:
        if line.startswith("|") and not line.startswith("|:"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[re.sub(r"[* ]", "", cells[0]).lower()] = cells[1:]
        elif line.startswith("#") and rows:
            break
    return rows


def test_vehicle_table_matches_the_rulebook():
    from backend import leveling
    rows = _rulebook_vehicle_table()
    assert len(rows["level"]) == 10, rows.keys()
    keys = list(rows.keys())
    assert "damagepoints" in keys and "edge" in keys
    for i in range(10):
        lvl = i + 1
        v = leveling.vehicle_stats(lvl)
        assert v["max_dp"] == int(rows["damagepoints"][i].split()[0]), lvl
        assert v["edge"] == int(rows["edge"][i]), lvl
        assert v["defense_die"] == rows["maxdefensedie"][i], lvl
        weapon_key = next(k for k in keys if k.startswith("maxweapondie"))
        assert " or ".join(v["weapon_options"]) == rows[weapon_key][i], lvl
        uses_key = next(k for k in keys if k.startswith("usesperencounter"))
        assert str(v["uses_per_encounter"]) == rows[uses_key][i].split()[0], lvl
        for n in range(1, 6):
            key = next(k for k in keys if k.startswith(("1st", "2nd", "3rd", "4th", "5th")[n - 1]))
            assert (v[f"slot_{n}_die"] or "") == rows[key][i], (lvl, n)


def test_vehicle_dp_matches_the_character_row_and_edge_runs_to_ten():
    from backend import leveling
    for lvl in range(1, 11):
        assert leveling.vehicle_stats(lvl)["max_dp"] == leveling.level_stats(lvl)["max_dp"]
    assert leveling.vehicle_stats(10)["edge"] == 10
    with pytest.raises(ValueError):
        leveling.vehicle_stats(11)


# ---------------------------------------------------------------- the world
@pytest.fixture(scope="module")
def world():
    from backend.db import SessionLocal, init_db
    from backend.models import Campaign, CampaignMembership, Character, User
    init_db()
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    def user(name):
        u = User(id=uuid.uuid4(), email=f"{name}_{tag}@example.com", username=f"{name}_{tag}", hashed_password="x")
        db.add(u)
        db.commit()
        return u

    sw, p1, p2, outsider = user("sw"), user("p1"), user("p2"), user("out")
    camp = Campaign(id=uuid.uuid4(), name="Vehicle test", description="x" * 12, created_by_user_id=sw.id,
                    created_by_id=str(sw.id), story_weaver_id=sw.id)
    db.add(camp)
    db.commit()
    for u, role in ((sw, "story_weaver"), (p1, "player"), (p2, "player")):
        db.add(CampaignMembership(id=uuid.uuid4(), campaign_id=camp.id, user_id=u.id, role=role))
    db.commit()

    def pc(name, owner, **kw):
        c = Character(id=uuid.uuid4(), name=f"{name} {tag}", owner_id=str(owner.id), user_id=owner.id, campaign_id=camp.id, level=3,
                      pp=2, ip=3, sp=1, dp=20, max_dp=20, edge=1, attack_style="1d6", defense_die="1d6", **kw)
        db.add(c)
        db.commit()
        return c

    yield dict(db=db, camp=camp, sw=sw, p1=p1, p2=p2, outsider=outsider, pc=pc, tag=tag, Character=Character)
    db.close()


def _create(world, **kw):
    from routes.vehicles import VehicleCreate, create_vehicle
    body = dict(name=f"Ship {uuid.uuid4().hex[:6]}", level=3)
    body.update(kw)
    return _run(create_vehicle(str(world["camp"].id), VehicleCreate(**body), world["db"], world["sw"]))


def test_the_story_weaver_creates_a_vehicle_with_table_numbers(world):
    v = _create(world, level=5, kind="open")
    assert (v["level"], v["max_dp"], v["dp"], v["edge"], v["defense_die"]) == (5, 16, 16, 5, "1d8")
    assert v["weapon_die"] == "1d8" and v["weapon_options"] == ["1d8", "2d6"]
    assert v["uses"] == v["max_uses"] == 7 and v["kind"] == "open" and v["state"] == "active"
    assert [s["die"] for s in v["systems"]] == ["1d10", "1d8", "1d6"]
    row = world["db"].get(world["Character"], uuid.UUID(v["id"]))
    assert row.is_vehicle and row.is_npc and row.user_id is None


def test_a_player_cannot_create_edit_or_delete_a_vehicle(world):
    from routes.vehicles import VehicleCreate, VehicleUpdate, create_vehicle, delete_vehicle, update_vehicle
    with pytest.raises(HTTPException) as e:
        _run(create_vehicle(str(world["camp"].id), VehicleCreate(name="Stolen", level=1), world["db"], world["p1"]))
    assert e.value.status_code == 403
    v = _create(world)
    with pytest.raises(HTTPException) as e:
        _run(update_vehicle(str(world["camp"].id), v["id"], VehicleUpdate(level=10), world["db"], world["p1"]))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        _run(delete_vehicle(str(world["camp"].id), v["id"], world["db"], world["p1"]))
    assert e.value.status_code == 403


def test_a_non_member_cannot_list(world):
    from routes.vehicles import list_vehicles
    with pytest.raises(HTTPException) as e:
        _run(list_vehicles(str(world["camp"].id), world["db"], world["outsider"]))
    assert e.value.status_code == 403


def test_a_weapon_die_must_be_one_the_level_allows(world):
    from routes.vehicles import VehicleCreate, create_vehicle
    with pytest.raises(HTTPException) as e:
        _run(create_vehicle(str(world["camp"].id), VehicleCreate(name="Bad", level=1, weapon_die="1d12"), world["db"], world["sw"]))
    assert e.value.status_code == 400
    assert _create(world, level=7, weapon_die="2d8")["weapon_die"] == "2d8"


def test_levelling_a_vehicle_follows_the_table_and_keeps_a_still_legal_weapon(world):
    from routes.vehicles import VehicleUpdate, update_vehicle
    v = _create(world, level=7, weapon_die="3d6")
    out = _run(update_vehicle(str(world["camp"].id), v["id"], VehicleUpdate(level=9), world["db"], world["sw"]))
    assert (out["level"], out["max_dp"], out["edge"], out["max_uses"]) == (9, 24, 9, 11)
    assert out["dp"] == 24, "a vehicle at full DP that levels up is still at full DP"
    assert out["weapon_die"] == "1d12", "3d6 is not a level 9 weapon, so it falls back to the plain single die"
    down = _run(update_vehicle(str(world["camp"].id), v["id"], VehicleUpdate(level=2), world["db"], world["sw"]))
    assert down["max_dp"] == 10 and down["dp"] == 10 and down["weapon_die"] == "1d4"


def test_players_only_see_vehicles_the_sw_has_revealed(world):
    from routes.vehicles import list_vehicles
    hidden = _create(world, visible_to_players=False)
    shown = _create(world)
    sw_ids = {v["id"] for v in _run(list_vehicles(str(world["camp"].id), world["db"], world["sw"]))}
    pl_ids = {v["id"] for v in _run(list_vehicles(str(world["camp"].id), world["db"], world["p1"]))}
    assert {hidden["id"], shown["id"]} <= sw_ids
    assert shown["id"] in pl_ids and hidden["id"] not in pl_ids


def test_a_vehicle_is_never_listed_as_an_npc(world):
    from types import SimpleNamespace
    from routes.character_fastapi import list_npcs
    v = _create(world)
    req = SimpleNamespace(state=SimpleNamespace(request_id="t"))
    npcs = _run(list_npcs(str(world["camp"].id), req, world["db"], world["sw"]))
    assert v["id"] not in {str(n.id) for n in npcs}


def _take(world, user, vid, station, char):
    from routes.vehicles import CrewAssign, take_station
    return _run(take_station(str(world["camp"].id), vid, station, CrewAssign(character_id=str(char.id)), world["db"], user))


def test_a_player_takes_and_leaves_their_own_station(world):
    from routes.vehicles import leave_station
    v = _create(world)
    me = world["pc"]("Gunner", world["p1"])
    out = _take(world, world["p1"], v["id"], "gunner", me)
    assert out["crew"]["gunner"]["character_id"] == str(me.id)
    out = _run(leave_station(str(world["camp"].id), v["id"], "gunner", world["db"], world["p1"]))
    assert "gunner" not in out["crew"]


def test_a_player_cannot_crew_someone_elses_character_or_kick_them(world):
    from routes.vehicles import leave_station
    v = _create(world)
    theirs = world["pc"]("Theirs", world["p2"])
    with pytest.raises(HTTPException) as e:
        _take(world, world["p1"], v["id"], "pilot", theirs)
    assert e.value.status_code == 403
    _take(world, world["sw"], v["id"], "pilot", theirs)        # the SW can
    with pytest.raises(HTTPException) as e:
        _run(leave_station(str(world["camp"].id), v["id"], "pilot", world["db"], world["p1"]))
    assert e.value.status_code == 403


def test_a_station_holds_one_person_and_a_person_holds_one_station(world):
    v = _create(world)
    a, b = world["pc"]("A", world["p1"]), world["pc"]("B", world["p2"])
    _take(world, world["p1"], v["id"], "engineer", a)
    with pytest.raises(HTTPException) as e:
        _take(world, world["p2"], v["id"], "engineer", b)
    assert e.value.status_code == 409
    out = _take(world, world["p1"], v["id"], "captain", a)     # moving: leaves engineer
    assert "engineer" not in out["crew"] and out["crew"]["captain"]["character_id"] == str(a.id)


def test_one_character_cannot_crew_two_vehicles(world):
    from routes.vehicles import list_vehicles
    v1, v2 = _create(world), _create(world)
    a = world["pc"]("Solo", world["p1"])
    _take(world, world["p1"], v1["id"], "gunner", a)
    _take(world, world["p1"], v2["id"], "gunner", a)
    by_id = {v["id"]: v for v in _run(list_vehicles(str(world["camp"].id), world["db"], world["sw"]))}
    assert "gunner" not in by_id[v1["id"]]["crew"] and by_id[v2["id"]]["crew"]["gunner"]["character_id"] == str(a.id)


def test_a_single_operator_and_station_crew_do_not_mix(world):
    v = _create(world)
    a, b = world["pc"]("Op", world["p1"]), world["pc"]("Gun", world["p2"])
    _take(world, world["p1"], v["id"], "operator", a)
    with pytest.raises(HTTPException) as e:
        _take(world, world["p2"], v["id"], "gunner", b)
    assert e.value.status_code == 409


def test_an_npc_can_be_crewed_by_the_story_weaver(world):
    v = _create(world)
    npc = world["Character"](id=uuid.uuid4(), name=f"Pirate {world['tag']}", owner_id=str(world["sw"].id), campaign_id=world["camp"].id,
                             is_npc=True, level=3, pp=2, ip=2, sp=2, dp=12, max_dp=12, edge=1, attack_style="1d6", defense_die="1d6")
    world["db"].add(npc)
    world["db"].commit()
    out = _take(world, world["sw"], v["id"], "gunner", npc)
    assert out["crew"]["gunner"]["is_npc"] is True


def test_unknown_station_and_a_vehicle_as_crew_are_refused(world):
    v, other = _create(world), _create(world)
    me = world["pc"]("Crew", world["p1"])
    with pytest.raises(HTTPException) as e:
        _take(world, world["p1"], v["id"], "cook", me)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _take(world, world["sw"], v["id"], "gunner", world["db"].get(world["Character"], uuid.UUID(other["id"])))
    assert e.value.status_code == 404


def test_deleting_a_vehicle_frees_its_crew(world):
    from routes.vehicles import delete_vehicle
    from backend.models import VehicleCrew
    v = _create(world)
    me = world["pc"]("Freed", world["p1"])
    _take(world, world["p1"], v["id"], "gunner", me)
    _run(delete_vehicle(str(world["camp"].id), v["id"], world["db"], world["sw"]))
    assert world["db"].query(VehicleCrew).filter(VehicleCrew.character_id == me.id).count() == 0
    assert world["db"].get(world["Character"], me.id) is not None, "the crew member is not deleted with the vehicle"


def test_the_story_weavers_notes_never_reach_players(world):
    from routes.vehicles import list_vehicles
    v = _create(world, notes="secret: the reactor is cracked")
    assert v["notes"] == "secret: the reactor is cracked"
    sw_view = {x["id"]: x for x in _run(list_vehicles(str(world["camp"].id), world["db"], world["sw"]))}
    pl_view = {x["id"]: x for x in _run(list_vehicles(str(world["camp"].id), world["db"], world["p1"]))}
    assert sw_view[v["id"]]["notes"] and pl_view[v["id"]]["notes"] is None
    me = world["pc"]("NoteReader", world["p1"])
    assert _take(world, world["p1"], v["id"], "gunner", me)["notes"] is None


def test_the_vehicle_table_endpoint_serves_the_rules_numbers(world):
    from backend import leveling
    from routes.vehicles import vehicle_table
    out = _run(vehicle_table(str(world["camp"].id), world["db"], world["p1"]))
    assert out["levels"]["7"] == leveling.vehicle_stats(7) and len(out["levels"]) == 10
    assert [s["key"] for s in out["stations"]] == ["operator", "gunner", "defense_officer", "captain", "pilot", "engineer"]
    with pytest.raises(HTTPException) as e:
        _run(vehicle_table(str(world["camp"].id), world["db"], world["outsider"]))
    assert e.value.status_code == 403


def test_the_game_page_has_the_vehicles_modal_and_no_typed_table():
    html = open(os.path.join(ROOT, "static", "game.html"), encoding="utf-8").read()
    for needle in ('id="vehiclesModal"', "function openVehiclesModal", "vehicles_changed", "/vehicle-table"):
        assert needle in html, needle
    assert "max_dp: 26" not in html and '"26"' not in html[html.index("function loadVehicles"):html.index("function openVehiclesModal")], \
        "the page must read the vehicle numbers from the server, not carry its own copy"
