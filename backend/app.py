# backend/app.py

import time
import os
import uuid
import traceback

from dotenv import load_dotenv
from flask import Flask, jsonify, g, request
from flasgger import Swagger

from backend.db import Base, engine
from backend.models import Echo
from backend.logging_config import setup_logging
from backend.health_checks import check_database, check_env, get_app_metadata
from backend.error_handlers import register_error_handlers
from backend.metrics import increment_request, get_metrics

# Track app uptime
start_time = time.time()

# Load environment variables
load_dotenv()

# Debug: show CWD and specs folder
print("📂 Working directory:", os.getcwd())
try:
    print("📄 Files in routes/docs:", os.listdir("routes/docs"))
except Exception as e:
    print("⚠️ Could not list routes/docs:", e)

# Initialize database
Base.metadata.create_all(bind=engine)

# Set up logging
setup_logging()

# Create Flask app
app = Flask(__name__)
app.config["SWAGGER"] = {"title": "TBA API", "uiversion": 3}

# Configure Flasgger
try:
    swagger = Swagger(
        app,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec_1",
                    "route": "/apispec_1.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/apidocs",
        },
        template={"info": {"title": "TBA API", "version": "dev"}},
    )
    print("✅ Swagger initialized successfully")
except Exception:
    print("❌ Swagger initialization failed:")
    traceback.print_exc()
    raise

# Register blueprints with error wrappers
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

# Global error handlers
register_error_handlers(app)

# Request ID injector
@app.before_request
def assign_request_id():
    rid = str(uuid.uuid4())
    g.request_id = rid
    request.environ["request_id"] = rid
    for handler in app.logger.handlers:
        handler.addFilter(lambda record: setattr(record, "request_id", rid) or True)
    increment_request()

# Health check
@app.route("/")
def home():
    """Basic Health Check"""
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Detailed health
@app.route("/health")
def health():
    """Full Health Diagnostics"""
    checks = {
        "database": check_database(),
        "env": check_env(),
        "app": get_app_metadata(start_time),
    }
    status = 200 if all(v == "ok" or isinstance(v, dict) for v in checks.values()) else 500
    return jsonify(checks), status

# Metrics endpoint
@app.route("/metrics")
def metrics_route():
    """Request Metrics"""
    return jsonify(get_metrics())

# Local-only dev server
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)

application = app