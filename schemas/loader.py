import os
import json
from jsonschema import validate, ValidationError

SCHEMA_DIR = os.path.dirname(__file__)
SCHEMAS = {}

def load_schemas():
    for filename in os.listdir(SCHEMA_DIR):
        if filename.endswith(".json") and filename != "loader.py":
            path = os.path.join(SCHEMA_DIR, filename)
            with open(path, "r") as f:
                schema_name = filename.replace(".json", "")
                SCHEMAS[schema_name] = json.load(f)

def validate_data(data, schema_name):
    if schema_name not in SCHEMAS:
        raise ValueError(f"Schema '{schema_name}' not found.")
    try:
        validate(instance=data, schema=SCHEMAS[schema_name])
        return True
    except ValidationError as e:
        return str(e)

# Load schemas on import
load_schemas()