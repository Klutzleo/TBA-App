from flask import Flask, request, jsonify

app = Flask(__name__)
lore_log = []

@app.route("/lore/entry", methods=["POST"])
def lore_entry():
    data = request.json
    required_fields = ["actor", "moment", "description", "effect", "location", "round", "encounter_id"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    lore_log.append(data)
    return jsonify({"message": "Lore entry saved", "entry": data}), 201

def add_lore_entry(entry):
    lore_log.append(entry)
    return entry