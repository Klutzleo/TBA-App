from flask import Blueprint, jsonify, request
from schemas.loader import SCHEMAS
from jsonschema import validate, ValidationError

schemas_bp = Blueprint("schemas", __name__)

# 🧠 Route: List all schema names
@schemas_bp.route("/schemas", methods=["GET"])
def list_schemas():
    return jsonify({ "schemas": list(SCHEMAS.keys()) })

# 📜 Route: Get full schema by name
@schemas_bp.route("/schemas/<name>", methods=["GET"])
def get_schema(name):
    schema = SCHEMAS.get(name)
    if not schema:
        return { "error": "Schema not found" }, 404
    return jsonify(schema)

# ✅ Route: Validate a payload against a schema
@schemas_bp.route("/validate/<schema_name>", methods=["POST"])
def validate_schema(schema_name):
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({
            "valid": False,
            "error": "No JSON payload received.",
            "reaction": "😶"
        }), 400

    schema = SCHEMAS.get(schema_name)
    if not schema:
        return jsonify({
            "valid": False,
            "error": f"Schema '{schema_name}' not found.",
            "reaction": "❓"
        }), 404

    try:
        validate(instance=payload, schema=schema)
        return jsonify({
            "valid": True,
            "message": f"Payload matches schema '{schema_name}'.",
            "reaction": "✅"
        }), 200
    except ValidationError as e:
        return jsonify({
            "valid": False,
            "error": str(e.message),
            "reaction": "⚠️"
        }), 422