from routes.schemas.effect import EffectResolveSchema, EffectResolveResponseSchema

@effects_blp.route("/resolve", methods=["POST"])
@effects_blp.arguments(EffectResolveSchema)
@effects_blp.response(200, EffectResolveResponseSchema)
def resolve_effect(data):
    # TODO: Apply effect logic and update actor state
    outcome = {
        "HP_change": -10,
        "status": "burned",
        "area_damage": True
    }
    narration = f"{data['actor']} is engulfed in flames, suffering damage and igniting nearby terrain."
    return {
        "status": "success",
        "actor": data["actor"],
        "applied_effect": data["effect"],
        "outcome": outcome,
        "narration": narration
    }