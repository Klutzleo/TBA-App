import os
import time
import uuid
import traceback
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, g, request, current_app, redirect
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

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
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

# ✅ OpenAPI 3.0 configuration
app.config.update({
    "API_TITLE": "TBA Combat & Magic API",
    "API_VERSION": "1.0",
    "OPENAPI_VERSION": "3.0.2",
    "OPENAPI_URL_PREFIX": "/api",
    "OPENAPI_REDOC_PATH": "/docs",
    "OPENAPI_REDOC_URL": "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
})

# Initialize Flask-Smorest API
api = Api(app)
print("✅ OpenAPI 3.0 initialized successfully")

# Define API key security scheme
api.spec.components.security_scheme(
    "ApiKeyAuth",
    {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key"
    }
)

# Register your blueprints
print("🔄 Registering blueprints…")

try:
    from routes.schemas.blp import schemas_blp
    api.register_blueprint(schemas_blp)
    print("✅ schemas_bp registered")
except Exception:
    print("❌ Failed to import/register schemas_bp:")
    traceback.print_exc()
    raise

try:
    from routes.roll import roll_blp
    api.register_blueprint(roll_blp)
    print("✅ roll_blp registered")
except Exception:
    print("❌ Failed to import/register roll_blp:")
    traceback.print_exc()
    raise

try:
    from routes.combat import combat_blp
    api.register_blueprint(combat_blp)
    print("✅ combat_blp registered")
except Exception:
    print("❌ Failed to import/register combat_blp:")
    traceback.print_exc()
    raise

try:
    from routes.magic import magic_blp
    api.register_blueprint(magic_blp)
    print("✅ magic_blp registered")
except Exception:
    print("❌ Failed to import/register magic_blp:")
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

    # 🔐 Enforce API key for protected routes
    if request.path.startswith("/api/") and not (
        request.path.startswith("/api/docs") or request.path == "/api/openapi.json"
    ):
        key = request.headers.get("X-API-Key")
        expected = os.getenv("API_KEY")
        if not key or key != expected:
            return jsonify({"error": "Unauthorized"}), 401

    # Optional: log docs access
    if request.path.startswith("/api/docs") or request.path == "/api/openapi.json":
        app.logger.info(f"Docs or spec accessed by {request.remote_addr}")   
    


# Basic health check
@app.route("/")
def home():
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Detailed health check endpoint
@app.route("/health")
def health():
    # Run checks but be tolerant: return 200 with details so hosted platforms
    # relying on a quick health probe (Railway, Heroku) don't block deploys
    # for transient DB or env issues. Errors are surfaced in the JSON body.
    db_check = check_database()
    env_check = check_env()
    app_meta = get_app_metadata(start_time)

    checks = {
        "database": db_check,
        "env": env_check,
        "app": app_meta,
    }

    # Normalize check statuses into a succinct summary
    summary = {
        "database_ok": db_check == "ok",
        "env_ok": env_check == "ok" or isinstance(env_check, dict) and not env_check.get("missing"),
        "app": app_meta,
    }

    # Always return 200 to avoid deployment health-probe failures; include
    # a `healthy` flag for callers that want strict checks.
    healthy = summary["database_ok"] and summary["env_ok"]
    response = {"healthy": healthy, "summary": summary, "checks": checks}
    return jsonify(response), 200

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
@app.errorhandler(Exception)
def debug_exception(e):
    app.logger.exception(f"Exception on {request.method} {request.path}")
    if isinstance(e, HTTPException):
        raise
    return jsonify({"error": "Internal server error", "exception": str(e)}), 500

# Favicon
@app.route("/favicon.ico")
def favicon():
    return "", 204

# WSGI entrypoint
application = app

# Local dev runner (uncomment for local testing)
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)

try:
    from routes.effects import effects_blp
    api.register_blueprint(effects_blp)
    print("✅ effects_blp registered")
except Exception:
    print("❌ Failed to import/register effects_blp:")
    traceback.print_exc()
    raise