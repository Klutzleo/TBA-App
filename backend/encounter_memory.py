# backend/encounter_memory.py

encounter_state = {
    "actors": [],
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

def advance_round():
    encounter_state["round"] += 1
    return encounter_state["round"]

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