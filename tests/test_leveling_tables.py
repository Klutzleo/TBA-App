"""
Rules v3.1 numbers have one source: schemas/leveling_v3_1.json (read by backend/leveling.py).

The backend derives everything from it. The front-end pages are static files with no build step, so they carry
copies; these tests fail if any copy drifts from the JSON. When you change a number, change the JSON and the
copies together.
"""
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_leveling_tables.db")
os.environ.setdefault("API_KEY", "devkey")

from backend import leveling  # noqa: E402

LEVELS = range(1, 11)


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _block(text, name):
    """The `{ ... }` literal assigned to a JS const (nested braces are not used in these tables)."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*\{(.*?)\}\s*;", text, re.S)
    assert m, f"const {name} not found"
    return m.group(1)


def _numbers(text, name):
    return {int(k): int(v) for k, v in re.findall(r"(\d+)\s*:\s*(\d+)", _block(text, name))}


def _strings(text, name):
    return {int(k): v for k, v in re.findall(r"(\d+)\s*:\s*'([^']*)'", _block(text, name))}


def _lists(text, name):
    out = {}
    for k, body in re.findall(r"(\d+)\s*:\s*\[([^\]]*)\]", _block(text, name)):
        out[int(k)] = re.findall(r"'([^']*)'", body)
    return out


# ---- the JSON itself matches the v3.1 Core Rules ---------------------------------------------------------

def test_dp_is_8_plus_2_per_level():
    assert [leveling.level_stats(l)["max_dp"] for l in LEVELS] == [8, 10, 12, 14, 16, 18, 20, 22, 24, 26]


def test_uses_are_level_plus_two():
    assert [leveling.uses_for_level(l) for l in LEVELS] == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def test_the_four_trap_weapon_dice_are_gone():
    allowed = {die for l in LEVELS for die in leveling.weapon_options(l)}
    assert not allowed & {"3d4", "4d4", "5d4", "4d6"}
    assert leveling.weapon_options(9) == ["1d12", "2d10", "3d8"]
    assert leveling.weapon_options(5) == ["1d8", "2d6"]


def test_buff_table_and_duration():
    assert leveling.BUFF_DEBUFF_MODIFIER_BY_DIE == {"1d6": 1, "1d8": 2, "1d10": 2, "1d12": 3, "2d6": 3, "2d8": 4}
    assert leveling.BUFF_DEBUFF_DURATION_ROUNDS == 2


def test_core_ruleset_edge_and_bap_agree_with_the_leveling_file():
    """roll_logic still reads Edge and BAP from core_ruleset.json."""
    core = json.load(open(os.path.join(ROOT, "schemas", "core_ruleset.json"), encoding="utf-8"))["character_leveling"]
    for l in LEVELS:
        assert core[str(l)]["Edge"] == leveling.level_stats(l)["edge"], l
        assert core[str(l)]["BAP"] == leveling.level_stats(l)["bap"], l


# ---- the backend derives from it -------------------------------------------------------------------------

def test_backend_modules_use_the_file():
    from backend.character_utils import DP_BY_LEVEL, calculate_level_stats, get_available_attack_styles, get_defense_die
    from routes import campaign_websocket as cw
    from routes import character_fastapi as cf
    for l in LEVELS:
        row = leveling.level_stats(l)
        assert DP_BY_LEVEL[l] == row["max_dp"]
        assert calculate_level_stats(l) == {"edge": row["edge"], "bap": row["bap"], "max_dp": row["max_dp"]}
        assert get_available_attack_styles(l) == row["weapon_options"]
        assert get_defense_die(l) == row["defense_die"]
        assert cf.LEVEL_TABLE[l]["max_dp"] == row["max_dp"] and cf.LEVEL_TABLE[l]["uses_per_encounter"] == l + 2
        assert cf.WEAPON_OPTIONS_BY_LEVEL[l] == row["weapon_options"]
    assert cw.BUFF_DEBUFF_TABLE == leveling.BUFF_DEBUFF_MODIFIER_BY_DIE and cw.BUFF_DURATION == 2


# ---- the front-end copies have not drifted ---------------------------------------------------------------

def _expected(field):
    return {l: leveling.level_stats(l)[field] for l in LEVELS}


@pytest.mark.parametrize("page", ["static/create-character.html", "static/create-ally.html"])
def test_create_pages_match(page):
    t = _read(page)
    assert _numbers(t, "DP_BY_LEVEL") == _expected("max_dp")
    assert _numbers(t, "USES_BY_LEVEL") == _expected("uses_per_encounter")
    assert _numbers(t, "EDGE_BY_LEVEL") == _expected("edge")
    assert _numbers(t, "BAP_BY_LEVEL") == _expected("bap")
    assert _strings(t, "DEFENSE_DIE_BY_LEVEL") == _expected("defense_die")
    assert _lists(t, "WEAPON_OPTIONS_BY_LEVEL") == _expected("weapon_options")


def test_game_page_matches():
    t = _read("static/game.html")
    assert _numbers(t, "PC_DP_BY_LEVEL") == _expected("max_dp")
    assert _numbers(t, "PC_USES_BY_LEVEL") == _expected("uses_per_encounter")
    assert _numbers(t, "PC_EDGE_BY_LEVEL") == _expected("edge")
    assert _numbers(t, "PC_BAP_BY_LEVEL") == _expected("bap")
    assert _strings(t, "PC_DEFENSE_BY_LEVEL") == _expected("defense_die")
    assert _lists(t, "NPC_WEAPON_OPTIONS_BY_LEVEL") == _expected("weapon_options")
    buff = dict(re.findall(r"'(\dd\d+)'\s*:\s*(\d)", _block(t, "_BUFF_DEBUFF_TABLE")))
    assert {k: int(v) for k, v in buff.items()} == leveling.BUFF_DEBUFF_MODIFIER_BY_DIE


def test_no_page_still_offers_a_removed_weapon_die_as_a_choice():
    for page in ("static/game.html", "static/create-character.html", "static/create-ally.html"):
        t = _read(page)
        for die in ("3d4", "4d4", "5d4", "4d6"):
            # allowed only as the "no longer in the rules" legacy placeholder in the attack-style editor
            for m in re.finditer(r"<option value=\"" + die + r"\"[^>]*>([^<]*)<", t):
                assert "no longer in the rules" in m.group(1) or page == "static/game.html" and "(Balanced)" in m.group(1), (page, die)


def test_game_page_inline_copies_match():
    """The SW set-level popup and the in-game help table each carry their own hand-typed rows."""
    t = _read("static/game.html")
    popup = re.findall(r"(\d+):\s*\{ max_dp:(\d+), edge:(\d+), uses:(\d+),\s+defense:'([^']+)' \}", t)
    assert len(popup) == 10
    for lvl, dp, edge, uses, die in popup:
        row = leveling.level_stats(int(lvl))
        assert (int(dp), int(edge), int(uses), die) == (row["max_dp"], row["edge"], row["uses_per_encounter"], row["defense_die"]), lvl
    cell = r'<td style="padding:3px 8px;text-align:center;">'
    help_rows = re.findall(r'color:var\(--primary\);">(\d+)</td>' + cell + r"(\d+)</td>" + cell + r"(\d+)</td>" + cell
                           + r"(\d+)</td>" + cell + r"(\d+)</td>" + cell + r"(1d\d+)</td>", t)
    assert len(help_rows) == 10
    for lvl, dp, edge, bap, uses, die in help_rows:
        row = leveling.level_stats(int(lvl))
        assert (int(dp), int(edge), int(bap), int(uses), die) == (
            row["max_dp"], row["edge"], row["bap"], row["uses_per_encounter"], row["defense_die"]), lvl
