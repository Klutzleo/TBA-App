import os
import json
from backend.db import SessionLocal  # ✅
from backend.models import Echo

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