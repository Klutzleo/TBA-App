from flask import request, jsonify
from flask_smorest import Blueprint

effects_blp = Blueprint(
    "effects", "effects",
    url_prefix="/api/effect",
    description="Endpoints for effect simulation, resolution, and rollback"
)

@effects_blp.route("/preview", methods=["POST"])
def preview_effect():
    data = request.get_json()
    simulated_outcome = {
        "HP_change": -8,
        "status": "burned",
        "area_damage": True
    }
    narration = "Thorne hurls a fireball into the trees, scorching goblins and igniting the underbrush."
    return jsonify({
        "status": "success",
        "actor": data.get("actor"),
        "simulated_outcome": simulated_outcome,
        "narration": narration if data.get("narrate") else None
    })