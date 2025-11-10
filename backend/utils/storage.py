import os
import json
from backend.db import SessionLocal  # ✅
from backend.models import Echo, RollLog

### 🧠 Echo Storage (Database) ###
def store_echo(schema_type, payload):
    session = SessionLocal()
    echo = Echo(schema_type=schema_type, payload=payload)
    session.add(echo)
    session.commit()
    session.close()

### 📦 Character Sheet Storage (File-based) ###
CHARACTER_DIR = "schemas/characters"

def load_character(character_id):
    """
    Loads a character sheet from JSON file.
    """
    path = os.path.join(CHARACTER_DIR, f"{character_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)

def save_character(character_id, data):
    """
    Saves a character sheet to JSON file.
    """
    os.makedirs(CHARACTER_DIR, exist_ok=True)
    path = os.path.join(CHARACTER_DIR, f"{character_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def store_roll(actor, target, roll_type, roll_mode, triggered_by, result, modifiers, session_id=None, encounter_id=None):
    session = SessionLocal()
    log = RollLog(
        actor=actor,
        target=target,
        roll_type=roll_type,
        roll_mode=roll_mode,
        triggered_by=triggered_by,
        result=result,
        modifiers=modifiers,
        session_id=session_id,
        encounter_id=encounter_id
    )
    session.add(log)
    session.commit()
    session.close()
