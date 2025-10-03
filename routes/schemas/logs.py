from flask import request
from collections import Counter
from routes.schemas.blp import schemas_blp
from routes.schemas.utils import LOG_HISTORY

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