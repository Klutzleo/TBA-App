from flask import request, jsonify
from flask_smorest import Blueprint
from backend.utils.storage import load_character, save_character

character_blp = Blueprint("Character", "character", url_prefix="/api/character")

@character_blp.route("/sheet/<character_id>", methods=["GET"])
@character_blp.response(200)
@character_blp.alt_response(404, description="Character not found")
def get_character_sheet(character_id):
    character = load_character(character_id)
    if not character:
        return {"error": "Character not found"}, 404
    return jsonify(character)

@character_blp.route("/sheet/<character_id>", methods=["PATCH"])
@character_blp.response(200)
@character_blp.alt_response(404, description="Character not found")
@character_blp.alt_response(400, description="Invalid update payload")
def update_character_sheet(character_id):
    updates = request.get_json(force=True)
    character = load_character(character_id)
    if not character:
        return {"error": "Character not found"}, 404

    character.update(updates)
    save_character(character_id, character)
    return jsonify(character)