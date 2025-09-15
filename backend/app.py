# backend/app.py

import os
from dotenv import load_dotenv

# Load environment variables from .env before anything else
load_dotenv()

from backend.db import Base, engine

# Create all tables immediately upon module import.
# This guarantees the schema is initialized regardless of which Flask hooks exist
Base.metadata.create_all(bind=engine)

from flask import Flask, jsonify
from routes.schemas import schemas_bp
from backend.models import Echo

# Initialize Flask app and register your blueprints
app = Flask(__name__)
app.register_blueprint(schemas_bp)

@app.route("/")
def home():
    """Health-check endpoint."""
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    # Only use Flask's built-in server in debug mode locally
    app.run(debug=True)