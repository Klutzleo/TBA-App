# backend/app.py

import os
import time
import uuid
import traceback
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, g, request, current_app, redirect
from flasgger import Swagger

from backend.db import Base, engine
from backend.models import Echo
from backend.logging_config import setup_logging
from backend.health_checks import check_database, check_env, get_app_metadata
from backend.error_handlers import register_error_handlers
from backend.metrics import increment_request, get_metrics

# Track uptime
start_time = time.time()

# Load .env vars
load_dotenv()

# Show current working dir and docs folder
print("📂 Working directory:", os.getcwd())
try:
    print("📄 Files in routes/docs:", os.listdir("routes/docs"))
except Exception as e:
    print("⚠️ Could not list routes/docs:", e)

# Initialize DB
Base.metadata.create_all(bind=engine)

# Setup your custom logging
setup_logging()

# Also enable Flask’s built-in logger at DEBUG
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

# ✅ Required for Flasgger to register /apidocs
app.config["SWAGGER"] = {
    "title": "TBA API",
    "uiversion": 3,
}

# Prepare absolute paths to your Swagger bundle
PROJECT_ROOT  = os.getcwd()                          # e.g., "/app"
DOCS_DIR      = os.path.join(PROJECT_ROOT, "routes", "docs")
BUNDLE_FILE   = os.path.join(DOCS_DIR, "combat_bundle.yml")

# Configure Flasgger to load the full Swagger 2.0 spec (paths + definitions)
swagger = Swagger(
    app,
    config={
        "headers": [],
        "specs": [
            {
                "endpoint":     "apispec_1",
                "route":        "/apispec_1.json",
                "rule_filter":  lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui":      True,
        "specs_route":     "/apidocs",
    },
    template_file="routes/docs/combat_bundle.yml"
)

print("✅ Swagger initialized successfully")

# Register your blueprints
print("🔄 Registering blueprints…")

try:
    from routes.schemas import schemas_bp
    app.register_blueprint(schemas_bp)
    print("✅ schemas_bp registered")
except Exception:
    print("❌ Failed to import/register schemas_bp:")
    traceback.print_exc()
    raise

try:
    from routes.roll import roll_bp
    app.register_blueprint(roll_bp, url_prefix="/api")
    print("✅ roll_bp registered")
except Exception:
    print("❌ Failed to import/register roll_bp:")
    traceback.print_exc()
    raise

try:
    from routes.combat import combat_bp
    app.register_blueprint(combat_bp, url_prefix="/api")
    print("✅ combat_bp registered")
except Exception:
    print("❌ Failed to import/register combat_bp:")
    traceback.print_exc()
    raise

# Global error handlers
register_error_handlers(app)

# Assign a request ID to every incoming request
@app.before_request
def assign_request_id():
    rid = str(uuid.uuid4())
    g.request_id = rid
    request.environ["request_id"] = rid
    for handler in app.logger.handlers:
        handler.addFilter(lambda record: setattr(record, "request_id", rid) or True)
    increment_request()

# Basic health check
@app.route("/")
def home():
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Detailed health check endpoint
@app.route("/health")
def health():
    checks = {
        "database": check_database(),
        "env":      check_env(),
        "app":      get_app_metadata(start_time),
    }
    status = 200 if all(v == "ok" or isinstance(v, dict) for v in checks.values()) else 500
    return jsonify(checks), status

# Metrics endpoint
@app.route("/metrics")
def metrics_route():
    return jsonify(get_metrics())

# Debug endpoint: list all routes
@app.route("/__routes__")
def list_routes():
    routes = []
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda r: r.rule):
        routes.append({"rule": rule.rule, "methods": sorted(rule.methods)})
    return jsonify(routes)

# Exception handler that re-raises HTTPExceptions
from werkzeug.exceptions import HTTPException

@app.errorhandler(Exception)
def debug_exception(e):
    app.logger.exception(f"Exception on {request.method} {request.path}")
    if isinstance(e, HTTPException):
        raise
    return jsonify({"error": "Internal server error", "exception": str(e)}), 500

# Favicon and docs redirect
@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/apidocs/")
def redirect_apidocs_slash():
    return redirect("/apidocs", code=301)

# WSGI entrypoint
application = app

# Local dev runner (uncomment for local testing)
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)