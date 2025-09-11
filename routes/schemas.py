from flask import Blueprint, jsonify
from schemas.loader import SCHEMAS

schemas_bp = Blueprint("schemas", __name__)

@schemas_bp.route("/schemas", methods=["GET"])
def list_schemas():
    return jsonify({ "schemas": list(SCHEMAS.keys()) })

@schemas_bp.route("/schemas/<name>", methods=["GET"])
def get_schema(name):
    schema = SCHEMAS.get(name)
    if not schema:
        return { "error": "Schema not found" }, 404
    return jsonify(schema)