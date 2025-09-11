# backend/app.py - This is like main.py but for Flask

import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, jsonify
from schemas import schemas_bp  # ✅ Correct import

app = Flask(__name__)  # Create the Flask app first
app.register_blueprint(schemas_bp)    # Register your blueprint

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)