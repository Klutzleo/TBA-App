import datetime
import time
from flask import request
from flask_smorest import Blueprint
from jsonschema import validate, ValidationError
from collections import Counter
from schemas.loader import SCHEMAS
from backend.db import SessionLocal
from backend.models import Echo
from backend.utils.storage import store_echo

schemas_blp = Blueprint(
    "schemas",
    "schemas",
    url_prefix="/api/schemas",
    description="Schema validation, playgrounds, and emotional reflection"
)

LOG_HISTORY = []

def log_validation(schema_name, valid, client_ip, duration=None, request_id=None, emotion=None):
    timestamp = datetime.datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "schema": schema_name,
        "valid": valid,
        "ip": client_ip,
        "duration": duration,
        "request_id": request_id,
        "emotion": emotion
    }
    LOG_HISTORY.append(log_entry)

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

def get_reaction(schema_name, payload):
    if schema_name == "memory_echoes":
        emotion = payload.get("emotion", "").lower()
        emoji = {
            "hope": "🌅",
            "grief": "🌧️",
            "joy": "🎉",
            "anger": "🔥",
            "confusion": "🌫️",
            "relief": "💨",
            "nostalgia": "📼"
        }.get(emotion, "🪞")
        print(f"DEBUG: Emotion = {emotion}, Reaction = {emoji}")
        return emoji
    return "✅"

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

@schemas_blp.route("/playground/<schema_name>", methods=["GET"])
@schemas_blp.response(200)
@schemas_blp.alt_response(404, description="No playground available")
def playground(schema_name):
    if schema_name == "memory_echoes":
        sample = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "emotion": "hope",
            "summary": "Reboot succeeded"
        }
        return sample
    return { "error": f"No playground available for schema '{schema_name}'." }, 404

@schemas_blp.route("/logs", methods=["GET"])
@schemas_blp.response(200)
def get_logs():
    try:
        limit = int(request.args.get("limit", 50))
        limit = max(1, min(limit, 100))
    except ValueError:
        limit = 50
    recent_logs = LOG_HISTORY[-limit:]
    return { "logs": recent_logs }

@schemas_blp.route("/reflect", methods=["GET"])
@schemas_blp.response(200)
def reflect():
    if not LOG_HISTORY:
        return { "message": "No logs available to reflect on." }

    total = len(LOG_HISTORY)
    valid_count = sum(1 for log in LOG_HISTORY if log["valid"])
    emotion_counter = Counter(log.get("emotion") for log in LOG_HISTORY if log.get("emotion"))
    schema_counter = Counter(log["schema"] for log in LOG_HISTORY)

    most_common_emotion = emotion_counter.most_common(1)[0][0] if emotion_counter else None
    last_emotion = next((log.get("emotion") for log in reversed(LOG_HISTORY) if log.get("emotion")), None)
    suggestion_rate = sum(1 for log in LOG_HISTORY if not log["valid"]) / total * 100

    summary = {
        "total_validations": total,
        "validation_success_rate": f"{(valid_count / total * 100):.1f}%",
        "schemas_used": list(schema_counter.keys()),
        "emotional_breakdown": dict(emotion_counter),
        "most_common_emotion": most_common_emotion,
        "last_emotion": last_emotion,
        "suggestion_rate": f"{suggestion_rate:.1f}%"
    }

    return summary