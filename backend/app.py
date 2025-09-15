# backend/app.py

import time
start_time = time.time()  # Track app start time for uptime reporting

import os
from dotenv import load_dotenv

# Load environment variables from .env before anything else
load_dotenv()

from backend.db import Base, engine

# Create all tables immediately upon module import.
# This guarantees the schema is initialized regardless of which Flask hooks exist
Base.metadata.create_all(bind=engine)

from flask import Flask, jsonify, g, request
from routes.schemas import schemas_bp
from backend.models import Echo
from backend.logging_config import setup_logging
from sqlalchemy import text


# Set up structured JSON logging (includes request_id injection)
setup_logging()

# Initialize Flask app and register your blueprints
app = Flask(__name__)
app.register_blueprint(schemas_bp)

# Inject a unique request ID into each incoming request for traceable logs
import uuid

@app.before_request
def assign_request_id():
    rid = str(uuid.uuid4())  # Generate a unique ID for this request
    g.request_id = rid       # Store in Flask's global context
    request.environ["request_id"] = rid  # Make it accessible to log filters

    # Attach request_id to all log records for this request
    for handler in app.logger.handlers:
        handler.addFilter(lambda record: setattr(record, "request_id", rid) or True)

# Basic health-check route for external probes or browser hits
@app.route("/")
def home():
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Full-spectrum health diagnostics route
@app.route("/health")
def health():
    checks = {}

    # ✅ Check DB connectivity
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")  # Simple query to confirm DB is reachable
        checks["database"] = "ok"
    except Exception as e:
        app.logger.error("Database health check failed", exc_info=e)
        checks["database"] = f"error: {str(e)}"

    # ✅ Check required environment variables
    required_env = ["DATABASE_URL", "FLASK_ENV"]
    missing = [var for var in required_env if not os.getenv(var)]
    checks["env"] = "ok" if not missing else f"missing: {missing}"

    # ✅ Calculate uptime since app start
    uptime_seconds = int(time.time() - start_time)

    # ✅ Include app metadata
    checks["app"] = {
        "status": "running",
        "version": os.getenv("APP_VERSION", "dev"),
        "uptime": f"{uptime_seconds}s"
    }

    # ✅ Determine overall health status
    status_code = 200 if all(v == "ok" or isinstance(v, dict) for v in checks.values()) else 500
    return jsonify(checks), status_code

# Local-only entry point for development
if __name__ == "__main__":
    app.run(debug=True)