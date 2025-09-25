from flask import Blueprint, request, jsonify
from flasgger import swag_from
from backend.roll_logic import resolve_skill_roll
import os

roll_bp = Blueprint("roll", __name__)

ROLL_SPEC = os.path.join(os.getcwd(), "routes", "docs", "roll_skill.yml")

@roll_bp.route("/roll/skill", methods=["POST"])
#@swag_from(ROLL_SPEC)
def roll_skill():
    try:
        data = request.get_json(force=True)
        print("✅ Received payload:", data)

        actor = data.get("actor")
        if not actor:
            print("❌ Missing 'actor' in payload")
            return jsonify({"error": "Missing actor data"}), 400

        result = resolve_skill_roll(
            actor=actor,
            difficulty_die=data.get("difficulty_die"),
            bap_triggered=data.get("bap", False)
        )
        print("✅ Skill roll result:", result)
        return jsonify(result)

    except Exception as e:
        print("🔥 Skill roll crashed:", str(e))
        return jsonify({"error": "Internal server error"}), 500