import datetime
import time
from flask import Blueprint, jsonify, request
from schemas.loader import SCHEMAS
from jsonschema import validate, ValidationError

schemas_bp = Blueprint("schemas", __name__)

# 🧠 Logger: Tracks schema, validity, IP, and duration
def log_validation(schema_name, valid, client_ip, duration=None, request_id=None):
    timestamp = datetime.datetime.utcnow().isoformat()
    log_parts = [
        f"[{timestamp}]",
        f"Schema: {schema_name}",
        f"Valid: {valid}",
        f"IP: {client_ip}"
    ]
    if duration is not None:
        log_parts.append(f"Duration: {duration}ms")
    if request_id:
        log_parts.append(f"RequestID: {request_id}")
    print(" | ".join(log_parts))

# ✅ Route: Validate a payload against a schema
@schemas_bp.route("/validate/<schema_name>", methods=["POST"])
def validate_schema(schema_name):
    payload = request.get_json(force=True, silent=True)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    request_id = request.headers.get("X-Request-Id")  # Optional, if Railway passes it

    if not payload:
        log_validation(schema_name, False, client_ip, request_id=request_id)
        return jsonify({
            "valid": False,
            "error": "No JSON payload received.",
            "reaction": "😶"
        }), 400

    schema = SCHEMAS.get(schema_name)
    if not schema:
        log_validation(schema_name, False, client_ip, request_id=request_id)
        return jsonify({
            "valid": False,
            "error": f"Schema '{schema_name}' not found.",
            "reaction": "❓"
        }), 404

    try:
        start = time.time()
        validate(instance=payload, schema=schema)
        duration = round((time.time() - start) * 1000)  # in ms
        log_validation(schema_name, True, client_ip, duration, request_id)
        return jsonify({
            "valid": True,
            "message": f"Payload matches schema '{schema_name}'.",
            "reaction": "✅"
        }), 200
    except ValidationError as e:
        duration = round((time.time() - start) * 1000)
        log_validation(schema_name, False, client_ip, duration, request_id)
        return jsonify({
            "valid": False,
            "error": str(e.message),
            "reaction": "⚠️"
        }), 422