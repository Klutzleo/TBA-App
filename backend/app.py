from flask import Flask, jsonify
from routes.schemas import schemas_bp
import os
from dotenv import load_dotenv
from backend.db import Base, engine
from backend.models import Echo

# Load environment variables from .env
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.register_blueprint(schemas_bp)

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

# Ensure tables are created once, right before the server starts handling requests
@app.before_serving
def initialize_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    app.run(debug=True)