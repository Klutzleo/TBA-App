from flask import Blueprint, request, jsonify

effects_bp = Blueprint('effects', __name__)

@effects_bp.route('/effect/preview', methods=['POST'])
def preview_effect():
    data = request.get_json()
    # TODO: Simulate effect outcome without applying it
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