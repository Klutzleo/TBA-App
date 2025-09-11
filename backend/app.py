# backend/app.py - This is like main.py but for Flask

from flask import Flask, jsonify
from backend.routes.schemas import schemas_bp

app = Flask(__name__)  # Create the Flask app first
app.register_blueprint(schemas_bp)  # Then register your blueprint

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)