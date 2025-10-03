from flask import request
from flask_smorest import Blueprint
from backend.roll_logic import resolve_skill_roll, resolve_combat_roll

roll_blp = Blueprint(
    "Roll",
    "roll",
    url_prefix="/api/roll",
    description="Skill and combat roll resolution"
)

VALID_STATS = {"PP", "SP", "IP"}

@roll_blp.route("/skill", methods=["POST"])
@roll_blp.response(200)
@roll_blp.alt_response(400, description="Missing or invalid input")
@roll_blp.alt_response(500, description="Internal server error")
def roll_skill():
    try:
        data = request.get_json(force=True)
        print("✅ Received payload:", data)

        actor = data.get("actor")
        if not actor:
            print("❌ Missing 'actor' in payload")
            return {"error": "Missing actor data"}, 400

        stat = actor.get("stat")
        if stat not in VALID_STATS:
            print(f"❌ Invalid stat: {stat}")
            return {
                "error": f"Invalid stat '{stat}'. Must be one of {sorted(VALID_STATS)}"
            }, 400

        result = resolve_skill_roll(
            actor=actor,
            difficulty_die=data.get("difficulty_die"),
            bap_triggered=data.get("bap", False)
        )
        print("✅ Skill roll result:", result)
        return result

    except Exception as e:
        print("🔥 Skill roll crashed:", str(e))
        return {
            "error": "Internal server error",
            "exception": str(e)
        }, 500

@roll_blp.route("/combat", methods=["POST"])
@roll_blp.response(200)
@roll_blp.alt_response(400, description="Missing or invalid input")
@roll_blp.alt_response(500, description="Internal server error")
def roll_combat():
    try:
        data = request.get_json(force=True)
        print("✅ Received combat payload:", data)

        attacker = data.get("attacker")
        defender = data.get("defender")
        weapon_die = data.get("weapon_die")
        defense_die = data.get("defense_die")
        bap = data.get("bap", False)

        if not attacker or not defender:
            return {"error": "Missing attacker or defender"}, 400
        if not weapon_die or not defense_die:
            return {"error": "Missing weapon_die or defense_die"}, 400

        result = resolve_combat_roll(
            attacker=attacker,
            defender=defender,
            weapon_die=weapon_die,
            defense_die=defense_die,
            bap_triggered=bap
        )
        print("✅ Combat roll result:", result)
        return result

    except Exception as e:
        print("🔥 Combat roll crashed:", str(e))
        return {
            "error": "Internal server error",
            "exception": str(e)
        }, 500