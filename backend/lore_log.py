# backend/lore_log.py

lore_entries = []

def add_lore_entry(entry: dict):
    lore_entries.append(entry)
    return entry

def get_lore_by_actor(actor_name: str):
    return [entry for entry in lore_entries if entry["actor"] == actor_name]

def get_lore_by_round(round_number: int):
    return [entry for entry in lore_entries if entry.get("round") == round_number]

def get_all_lore():
    return lore_entries