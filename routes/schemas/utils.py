import datetime

# 🧾 In-memory log store
LOG_HISTORY = []

# 🧠 Logger: Tracks schema, validity, IP, and duration
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

# 🎭 Reaction helper based on schema and emotion
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