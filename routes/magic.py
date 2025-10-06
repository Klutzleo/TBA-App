from flask import request
from flask_smorest import Blueprint
from backend.magic_logic import cast_spell, character_from_dict

magic_blp = Blueprint(
    "Magic",
    "magic",
    url_prefix="/api/magic",
    description="Spellcasting and magical effects"
)

@magic_blp.route("/cast", methods=["POST"])
@magic_blp.response(200)
@magic_blp.alt_response(400, description="Missing or invalid input")
@magic_blp.alt_response(500, description="Internal server error")
def post_cast_spell():
    try:
        payload = request.get_json()
        caster = character_from_dict(payload["caster"])
        targets = [character_from_dict(t) for t in payload.get("targets", [])]
        slot = payload["slot"]
        bap_trig = payload.get("bap", False)
        new_enc = payload.get("new_encounter", False)

        if new_enc:
            caster.reset_casts()

        entry = cast_spell(
            caster=caster,
            targets=targets,
            slot=slot,
            bap_triggered=bap_trig
        )

        return entry
    except Exception as e:
        print("Magic cast error:", str(e))
        return {"error": "Magic cast failed"}, 500