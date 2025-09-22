from flask import Blueprint, request, jsonify
from backend.roll_logic import resolve_skill_roll

roll_bp = Blueprint("roll", __name__)

@roll_bp.route("/roll/skill", methods=["POST"])
def roll_skill():
    """
    Perform a skill check using actor stats and level
    ---
    tags:
      - Skill Rolls
    parameters: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              actor:
                type: object
                description: Actor stats and level
                example:
                  level: 3
                  stat: "PP"
                  IP: 1
                  PP: 3
                  SP: 2
              difficulty_die:
                type: string
                description: Optional difficulty die
                example: "1d4"
              bap:
                type: boolean
                description: Whether BAP is triggered
                example: true
    responses:
      200:
        description: Skill roll result
        content:
          application/json:
            example:
              type: "skill"
              actor_roll: 11
              opponent_roll: 3
              outcome: "critical success"
              narrative: "You ace it with flair."
              details:
                die: 6
                stat: 3
                edge: 1
                bap: 2
    """
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