# main.py — TBA Entry Point

import os
import json

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
    schemas = load_schemas()
    print(f"Loaded {len(schemas)} schema files.")