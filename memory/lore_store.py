import random
from difflib import get_close_matches

lore_log = []

def add_lore_entry(entry):
    lore_log.append(entry)
    return entry

def fuzzy_match(value, options):
    matches = get_close_matches(value, options, n=1, cutoff=0.6)
    return matches[0] if matches else None

def search_lore(actor=None, location=None, moment=None, encounter_id=None, min_round=None, max_round=None, emotion=None, trigger=None):
    results = lore_log

    if actor:
        actor_names = [entry["actor"] for entry in results]
        matched_actor = fuzzy_match(actor, actor_names)
        if matched_actor:
            results = [entry for entry in results if entry["actor"] == matched_actor]

    if location:
        locations = [entry["location"] for entry in results]
        matched_location = fuzzy_match(location, locations)
        if matched_location:
            results = [entry for entry in results if entry["location"] == matched_location]

    if moment:
        moments = [entry["moment"] for entry in results]
        matched_moment = fuzzy_match(moment, moments)
        if matched_moment:
            results = [entry for entry in results if entry["moment"] == matched_moment]

    if encounter_id:
        results = [entry for entry in results if entry["encounter_id"] == encounter_id]

    if min_round:
        results = [entry for entry in results if entry["round"] >= min_round]
    if max_round:
        results = [entry for entry in results if entry["round"] <= max_round]

    if emotion:
        results = [entry for entry in results if entry.get("emotion") == emotion]

    if trigger:
        results = [entry for entry in results if entry.get("trigger") == trigger]

    return results

def get_random_lore():
    return random.choice(lore_log) if lore_log else None