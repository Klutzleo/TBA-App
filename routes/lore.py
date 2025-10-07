from flask import Flask, request, jsonify
from memory.lore_store import add_lore_entry, search_lore

app = Flask(__name__)

@app.route("/lore/entry", methods=["POST"])
def lore_entry():
    data = request.json
    required_fields = ["actor", "moment", "description", "effect", "location", "round", "encounter_id"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    entry = add_lore_entry(data)
    return jsonify({"message": "Lore entry saved", "entry": entry}), 201

@app.route("/lore/search", methods=["GET"])
def lore_search():
    actor = request.args.get("actor")
    location = request.args.get("location")
    moment = request.args.get("moment")
    encounter_id = request.args.get("encounter_id")

    results = search_lore(actor, location, moment, encounter_id)
    return jsonify({"results": results})