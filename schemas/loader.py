import os
import json
import logging
from jsonschema import validate, ValidationError
from schemas.loader import CORE_RULESET

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEMA_DIR = os.path.dirname(__file__)
SCHEMAS = {}

def load_schemas():
    logger.info("Loading schemas from %s", SCHEMA_DIR)
    for filename in os.listdir(SCHEMA_DIR):
        if filename.endswith(".json") and filename != "loader.py":
            path = os.path.join(SCHEMA_DIR, filename)
            try:
                with open(path, "r") as f:
                    schema_name = filename.replace(".json", "")
                    SCHEMAS[schema_name] = json.load(f)
                    logger.info("Loaded schema: %s", schema_name)
            except Exception as e:
                logger.error("Failed to load %s: %s", filename, str(e))

def validate_data(data, schema_name):
    if schema_name not in SCHEMAS:
        logger.warning("Schema '%s' not found", schema_name)
        raise ValueError(f"Schema '{schema_name}' not found.")
    try:
        validate(instance=data, schema=SCHEMAS[schema_name])
        logger.info("Validation passed for schema: %s", schema_name)
        return True
    except ValidationError as e:
        logger.warning("Validation failed for schema '%s': %s", schema_name, str(e))
        return str(e)

# Load schemas on import
load_schemas()
CORE_RULESET = SCHEMAS.get("core_ruleset", {})