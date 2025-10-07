lore_log = []

def add_lore_entry(entry):
    lore_log.append(entry)
    return entry

def search_lore(actor=None, location=None, moment=None, encounter_id=None, min_round=None, max_round=None):
    results = lore_log

    if actor:
        results = [entry for entry in results if actor.lower() in entry["actor"].lower()]
    if location:
        results = [entry for entry in results if location.lower() in entry["location"].lower()]
    if moment:
        results = [entry for entry in results if moment.lower() in entry["moment"].lower()]
    if encounter_id:
        results = [entry for entry in results if entry["encounter_id"] == encounter_id]
    if min_round:
        results = [entry for entry in results if entry["round"] >= min_round]
    if max_round:
        results = [entry for entry in results if entry["round"] <= max_round]

from difflib import get_close_matches

def fuzzy_match(value, options):
    matches = get_close_matches(value, options, n=1, cutoff=0.6)
    return matches[0] if matches else None


    return results