# backend/app.py - This is like main.py but for Flask

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify
from routes.schemas import schemas_bp  # ✅ Correct import

app = Flask(__name__)  # Create the Flask app first
app.register_blueprint(schemas_bp)    # Register your blueprint

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)