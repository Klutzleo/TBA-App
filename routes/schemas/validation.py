import time
import datetime
from flask import request
from jsonschema import validate, ValidationError
from routes.schemas.blp import schemas_blp
from routes.schemas.utils import LOG_HISTORY, log_validation, get_reaction
from schemas.loader import SCHEMAS

@schemas_blp.route("/validate/<schema_name>", methods=["POST"])
@schemas_blp.response(200)
@schemas_blp.alt_response(400, description="Missing payload")
@schemas_blp.alt_response(404, description="Schema not found")
@schemas_blp.alt_response(422, description="Validation failed")
def validate_schema(schema_name):
    payload = request.get_json(force=True, silent=True)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    request_id = request.headers.get("X-Request-Id")

    if not payload:
        log_validation(schema_name, False, client_ip, request_id=request_id)
        return {
            "valid": False,
            "error": "No JSON payload received.",
            "reaction": "😶"
        }, 400

    schema = SCHEMAS.get(schema_name)
    if not schema:
        log_validation(schema_name, False, client_ip, request_id=request_id)
        return {
            "valid": False,
            "error": f"Schema '{schema_name}' not found.",
            "reaction": "❓"
        }, 404

    try:
        start = time.time()
        validate(instance=payload, schema=schema)
        duration = round((time.time() - start) * 1000)
        reaction = get_reaction(schema_name, payload)
        emotion = payload.get("emotion") if schema_name == "memory_echoes" else None
        log_validation(schema_name, True, client_ip, duration, request_id, emotion)
        return {
            "valid": True,
            "message": f"Payload matches schema '{schema_name}'.",
            "reaction": reaction
        }, 200

    except ValidationError as e:
        duration = round((time.time() - start) * 1000)
        suggestion = None
        if "summary" in str(e.message):
            suggestion = "Try including a 'summary' field with a brief reflection."
        elif "emotion" in str(e.message):
            suggestion = "Make sure 'emotion' is a string like 'hope' or 'grief'."
        elif "timestamp" in str(e.message):
            suggestion = "Use ISO format like '2025-09-11T21:00:00Z'."

        emotion = payload.get("emotion") if payload else None
        log_validation(schema_name, False, client_ip, duration, request_id, emotion)
        return {
            "valid": False,
            "error": str(e.message),
            "reaction": "⚠️",
            "suggestion": suggestion
        }, 422