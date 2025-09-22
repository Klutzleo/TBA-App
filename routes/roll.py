from flask import Blueprint, request, jsonify
from backend.roll_logic import resolve_skill_roll

roll_bp = Blueprint("roll", __name__)

# Roll Skill
@roll_bp.route("/roll/skill", methods=["POST"])
def roll_skill():
    """
    Skill Roll vs Difficulty
    ---
    post:
      summary: Perform a skill check using actor stats and level
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
                  description: Optional difficulty die (e.g. "1d4")
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
    data = request.get_json()
    result = resolve_skill_roll(
        actor=data["actor"],
        difficulty_die=data.get("difficulty_die"),
        bap_triggered=data.get("bap", False)
    )
    return jsonify(result)