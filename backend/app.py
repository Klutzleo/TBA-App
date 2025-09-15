# backend/app.py

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

# Set up structured JSON logging
setup_logging()

# Initialize Flask app and register your blueprints
app = Flask(__name__)
app.register_blueprint(schemas_bp)

# Inject a unique request ID into each incoming request for traceable logs
import uuid

@app.before_request
def assign_request_id():
    rid = str(uuid.uuid4())
    g.request_id = rid
    request.environ["request_id"] = rid

    # Attach request_id to all log records for this request
    for handler in app.logger.handlers:
        handler.addFilter(lambda record: setattr(record, "request_id", rid) or True)

@app.route("/")
def home():
    """Health-check endpoint."""
    app.logger.info("Health check hit")
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    # Only use Flask's built-in server in debug mode locally
    app.run(debug=True)