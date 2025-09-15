# backend/app.py

import time
start_time = time.time()  # Track app start time for uptime reporting

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env before anything else

from flask import Flask, jsonify, g, request
import uuid

from backend.db import Base, engine
from backend.models import Echo
from backend.logging_config import setup_logging
from backend.health_checks import check_database, check_env, get_app_metadata
from backend.error_handlers import register_error_handlers
from backend.metrics import increment_request, get_metrics
from routes.schemas import schemas_bp

# Initialize database schema immediately
Base.metadata.create_all(bind=engine)

# Set up structured JSON logging
setup_logging()

# Initialize Flask app and register blueprints
app = Flask(__name__)
app.register_blueprint(schemas_bp)

# Register global error handlers
register_error_handlers(app)

# Inject a unique request ID and count requests
@app.before_request
def assign_request_id():
    rid = str(uuid.uuid4())
    g.request_id = rid
    request.environ["request_id"] = rid

    for handler in app.logger.handlers:
        handler.addFilter(lambda record: setattr(record, "request_id", rid) or True)

    increment_request()

# Basic health-check route
@app.route("/")
def home():
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Full-spectrum health diagnostics
@app.route("/health")
def health():
    checks = {
        "database": check_database(),
        "env": check_env(),
        "app": get_app_metadata(start_time)
    }
    status_code = 200 if all(v == "ok" or isinstance(v, dict) for v in checks.values()) else 500
    return jsonify(checks), status_code

# Lightweight metrics endpoint
@app.route("/metrics")
def metrics_route():
    return jsonify(get_metrics())

# Local-only entry point for development
if __name__ == "__main__":
    app.run(debug=True)