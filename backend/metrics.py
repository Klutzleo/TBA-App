# backend/metrics.py

metrics = {
    "requests": 0,
    "errors": 0
}

def increment_request():
    metrics["requests"] += 1

def get_metrics():
    return metrics