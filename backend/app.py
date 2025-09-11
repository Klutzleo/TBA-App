# backend/app.py - This is like main.py but for Flask

import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, jsonify
from routes.schemas import schemas_bp  # ✅ Direct import

app = Flask(__name__)
app.register_blueprint(schemas_bp)

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)