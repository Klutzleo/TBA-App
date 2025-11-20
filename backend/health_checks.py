# backend/health_checks.py

from sqlalchemy import text
import os, time
from backend.db import engine

def check_database():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return f"error: {str(e)}"

def check_env(required=None):
    # Default required envs: DATABASE_URL only. FLASK_ENV is optional in hosted
    # environments like Railway. Return a dict when values are missing so the
    # caller (health endpoint) can include details without treating it as a
    # hard failure.
    if required is None:
        required = ["DATABASE_URL"]
    missing = [var for var in required if not os.getenv(var)]
    return "ok" if not missing else {"missing": missing}

def get_app_metadata(start_time):
    uptime = int(time.time() - start_time)
    return {
        "status": "running",
        "version": os.getenv("APP_VERSION", "dev"),
        "uptime": f"{uptime}s"
    }