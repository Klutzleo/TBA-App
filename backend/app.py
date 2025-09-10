# backend/app.py - This is like main.py but for Flask
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)