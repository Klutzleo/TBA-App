# backend/app.py

import time
start_time = time.time()  # Track app start time for uptime reporting

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env before anything else

from flask import Flask, jsonify, g, request
import uuid
from flasgger import Swagger


from backend.db import Base, engine
from backend.models import Echo
from backend.logging_config import setup_logging
from backend.health_checks import check_database, check_env, get_app_metadata
from backend.error_handlers import register_error_handlers
from backend.metrics import increment_request, get_metrics

# Debugging to see if routes/docs to yml working
print("📂 Working directory:", os.getcwd())
try:
    print("📄 Files in routes/docs:", os.listdir("routes/docs"))
except Exception as e:
    print("⚠️ Could not list routes/docs:", str(e))

# Initialize database schema immediately
Base.metadata.create_all(bind=engine)

# Set up structured JSON logging
setup_logging()

# Initialize Flask app
app = Flask(__name__)

# Configure Flasgger with explicit spec and UI routes
#swagger = Swagger(
 #   app,
  #  config={
   #     "headers": [],
    #    "specs": [
     #       {
      #          "endpoint": "apispec_1",
       #         "route": "/apispec_1.json",
        #        "rule_filter": lambda rule: True,
         #       "model_filter": lambda tag: True,
          #  }
#        ],
 #       "static_url_path": "/flasgger_static",
  #      "swagger_ui": True,
   #     "specs_route": "/apidocs",
    #},
#    template={
 #       "info": {
  #          "title": "TBA API",
#            "version": "dev"
 #       }
#    }
#)
swagger = Swagger(app)

from routes.schemas import schemas_bp
from routes.roll import roll_bp
app.register_blueprint(schemas_bp)
app.register_blueprint(roll_bp, url_prefix="/api")

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
    """
    Basic Health Check
    ---
    get:
      summary: Confirm backend is running
      responses:
        200:
          description: Alive message
          content:
            application/json:
              example:
                message: "TBA backend is alive!"
    """
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

# Full-spectrum health diagnostics
@app.route("/health")
def health():
    """
    Full Health Diagnostics
    ---
    get:
      summary: Check database, environment, and uptime
      responses:
        200:
          description: Health status
          content:
            application/json:
              example:
                database: "ok"
                env: "ok"
                app:
                  status: "running"
                  version: "dev"
                  uptime: "42s"
    """
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
    """
    Request Metrics
    ---
    get:
      summary: View request and error counts
      responses:
        200:
          description: Metrics snapshot
          content:
            application/json:
              example:
                requests: 42
                errors: 0
    """
    return jsonify(get_metrics())

# Local-only entry point for development
#if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8080, debug=True)

application = app