from flask_smorest import Blueprint
from routes.schemas.effect import EffectPreviewSchema, EffectPreviewResponseSchema

effects_blp = Blueprint("effects", "effects", url_prefix="/api/effect")

@effects_blp.route("/preview", methods=["POST"])
@effects_blp.arguments(EffectPreviewSchema)
@effects_blp.response(200, EffectPreviewResponseSchema)
def preview_effect(data):
    simulated_outcome = {
        "HP_change": -8,
        "status": "burned",
        "area_damage": True
    }
    narration = "Thorne hurls a fireball into the trees, scorching goblins and igniting the underbrush."
    return {
        "status": "success",
        "actor": data["actor"],
        "simulated_outcome": simulated_outcome,
        "narration": narration if data.get("narrate") else None
    }