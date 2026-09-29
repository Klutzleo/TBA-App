# backend/encounter_memory.py
from typing import Optional

encounter_state = {
    "actors": [],
    # NOT the combat round counter — that's Encounter.round_number in the DB
    # (routes/campaign_websocket.py's advance_turn/next_round_number), shown in the
    # initiative tracker and broadcast to clients. This "round" is only a fallback
    # default for add_lore_entry() below when an effect is logged without an
    # explicit round — nothing ever advances it (the old advance_round() that did
    # was dead code, removed), so treat it as always 1, not a live value.
    "round": 1,
    "location": None,
    "initiative_order": [],
    "encounter_id": None,
    "effects": []
}

def add_actor(actor: dict):
    encounter_state["actors"].append(actor)
    return actor

def get_actors():
    return encounter_state["actors"]

def set_location(location: str):
    encounter_state["location"] = location

def resolve_initiative():
    # Sort actors by initiative descending
    sorted_actors = sorted(encounter_state["actors"], key=lambda a: a.get("initiative", 0), reverse=True)
    encounter_state["initiative_order"] = [a["name"] for a in sorted_actors]
    return encounter_state["initiative_order"]

def set_encounter_id(encounter_id: str):
    encounter_state["encounter_id"] = encounter_id

def get_encounter_id():
    return encounter_state["encounter_id"]

def add_effect(effect: dict):
    if "effects" not in encounter_state:
        encounter_state["effects"] = []
    encounter_state["effects"].append(effect)
    return effect

def get_effects():
    return encounter_state["effects"]

def clear_effects():
    encounter_state["effects"] = []

def remove_effect(actor_name: str, tag: Optional[str] = None):
    encounter_state["effects"] = [
        e for e in encounter_state["effects"]
        if not (e["actor"] == actor_name and (tag is None or e.get("tag") == tag))
    ]

def resolve_effects(round: int):
    return [e for e in encounter_state["effects"] if e.get("round") == round]

def reset_encounter():
    encounter_state["actors"] = []
    encounter_state["round"] = 1
    encounter_state["location"] = None
    encounter_state["initiative_order"] = []
    encounter_state["encounter_id"] = None  # ✅ Reset here
    encounter_state["effects"] = []  # ✅ Reset effects

def add_lore_entry(actor: str, round: Optional[int], tag: str, effect: str, duration: int, encounter_id: Optional[str]):
    entry = {
        "actor": actor,
        "round": round if round is not None else encounter_state["round"],
        "tag": tag,
        "effect": effect,
        "duration": duration,
        "encounter_id": encounter_id or encounter_state["encounter_id"]
    }
    return add_effect(entry)