"""
The public-facing copy keeps up with what shipped: the TBA Updates window (campaigns.html) and the home page (index.html).
House rules from Jason: no em-dashes in user-facing copy, and no player or campaign counts on the logged-out page.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    return open(os.path.join(ROOT, "static", name), encoding="utf-8").read()


def _whats_new():
    html = _read("campaigns.html")
    return html[html.index('<div id="whatsNewModal"'):html.index("<!-- Boast Bar -->")], html


def test_the_updates_window_covers_the_v3_1_1_release_and_vehicles():
    block, html = _whats_new()
    for needle in ("Vehicles", "Ascension, levels 11 to 15", "Rules v3.1.1", "The Calling, rebuilt", "Combos run themselves",
                   "Damage Effects and Swarms"):
        assert needle in block, needle
    new_part = block[:block.index("Earlier")]
    assert "Discord" not in new_part, "the Discord bot is still in testing, so it is not announced as new"


def test_shipped_features_are_no_longer_listed_as_coming_soon():
    block, _ = _whats_new()
    nxt = block[block.index("What's Next"):]
    for shipped in ("Ascension", "Triple Combo", "Combo cancellation"):
        assert shipped not in nxt, shipped


def test_the_updates_window_reshows_once_with_a_new_version():
    _, html = _whats_new()
    version = re.search(r"WHATS_NEW_VERSION = '([^']+)'", html).group(1)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", version) and version >= "2026-11-18"


def test_no_em_dashes_in_the_updates_window_or_the_home_page_features():
    block, _ = _whats_new()
    assert "\u2014" not in block
    home = _read("index.html")
    features = home[home.index('<div class="features">'):home.index("Getting started")]
    assert "\u2014" not in features


def test_the_home_page_features_are_current():
    home = _read("index.html")
    features = home[home.index('<div class="features">'):home.index("Getting started")]
    assert "<h4>Vehicles</h4>" in features and "Levels 1 to 15" in features
    assert "Bonds &amp; Combos</h4>" in features
    assert features.count("Coming soon") == 1 and "Discord mirror <span" in features, "Combos are live; the Discord mirror is still in testing"
    assert features.count('class="feat"') == 12, "the grid is four across, so keep it to full rows"
    assert "on to +8 in Ascension" in home


def test_the_logged_out_home_page_still_shows_no_usage_numbers():
    home = _read("index.html").lower()
    assert not re.search(r"\b\d[\d,]*\+?\s+(players|campaigns|adventurers|sessions)\b", home)


def test_the_home_page_says_it_runs_the_v3_1_1_rules():
    home = _read("index.html")
    assert "Now running the v3.1.1 rules" in home
    note = home[home.index('class="ver-note"'):home.index('<div class="features">')]
    assert "v3.1.1" in note and "—" not in note
