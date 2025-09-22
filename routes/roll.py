from flask import Blueprint, request, jsonify
from backend.roll_logic import resolve_skill_roll

roll_bp = Blueprint("roll", __name__)

@roll_bp.route("/roll/skill", methods=["POST"])
def roll_skill():
    data = request.get_json()

    result = resolve_skill_roll(
        actor=data["actor"],
        difficulty_die=data.get("difficulty_die"),
        bap_triggered=data.get("bap", False)
    )

    return jsonify(result)