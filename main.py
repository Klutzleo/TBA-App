# main.py — TBA Entry Point

import os
import json
from dotenv import load_dotenv
from backend.db import init_db

SCHEMA_DIR = "schemas"

def load_schemas():
    schemas = {}
    for filename in os.listdir(SCHEMA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(SCHEMA_DIR, filename)
            with open(path, "r") as f:
                schemas[filename] = json.load(f)
    return schemas

if __name__ == "__main__":
    print("🚀 TBA is booting up...")

    # ✅ Load environment variables
    load_dotenv()

    # ✅ Initialize database tables
    init_db()

    # ✅ Load schemas
    schemas = load_schemas()
    print(f"Loaded {len(schemas)} schema files.")