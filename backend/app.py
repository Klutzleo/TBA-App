from flask import Flask, jsonify
from routes.schemas import schemas_bp

app = Flask(__name__)
app.register_blueprint(schemas_bp)

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)