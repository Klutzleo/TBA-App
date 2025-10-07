from flask import request, jsonify
from flask_smorest import Blueprint
from backend.roll_logic import resolve_combat_roll, simulate_combat
from backend.magic_logic import cast_spell, character_from_dict
from backend.combat_utils import resolve_initiative
from backend.encounter_memory import add_actor, resolve_initiative, get_actors
from backend.encounter_memory import reset_encounter, advance_round, encounter_state
from schemas.combat import EncounterRequestSchema
from schemas.actor import Actor
from pydantic import ValidationError
from schemas.encounter import Encounter
from schemas.lore_entry import LoreEntry
from backend.lore_log import add_lore_entry, get_lore_by_actor, get_lore_by_round, get_all_lore


import traceback

combat_blp = Blueprint(
    "Combat",
    "combat",
    url_prefix="/api/combat",
    description="Combat resolution and simulation"
)

from schemas.combat import CombatRollRequest, CombatRollResponse, SimulatedCombatResponse

@combat_blp.route("/roll/combat", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, CombatRollResponse)
@combat_blp.doc(tags=["Combat"], summary="Resolve a single combat roll")
@combat_blp.alt_response(400, description="Missing or invalid input")
@combat_blp.alt_response(500, description="Internal server error")
def post_roll_combat(payload):
    try:
        result = resolve_combat_roll(**payload)
        return result
    except Exception as e:
        print("Combat roll error:", str(e))
        traceback.print_exc()
        return {"error": "Combat roll failed"}, 500

@combat_blp.route("/roll/combat/simulate", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Combat"], summary="Simulate a multi-round combat encounter")
@combat_blp.alt_response(400, description="Missing or invalid input")
@combat_blp.alt_response(500, description="Internal server error")
def post_roll_combat_simulate(payload):
    try:
        result = simulate_combat(**payload)
        return result
    except Exception as e:
        print("Combat simulation error:", str(e))
        traceback.print_exc()
        return {"error": "Simulation failed"}, 500
    
@combat_blp.route("/simulate/encounter", methods=["POST"])
@combat_blp.arguments(EncounterRequestSchema)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Combat"], summary="Simulate a multi-round encounter with initiative")
def post_simulate_encounter(payload):
    try:
        result = simulate_combat(**payload)
        return result
    except Exception as e:
        print("Encounter simulation error:", str(e))
        traceback.print_exc()
        return {"error": "Encounter simulation failed"}, 500

@combat_blp.route("/actor", methods=["POST"])
@combat_blp.arguments(Actor)
@combat_blp.response(201, Actor)
def register_actor(payload):
    saved = add_actor(payload)
    return {"message": "Actor registered", "actor": saved}

@combat_blp.route("/actor/list", methods=["GET"])
@combat_blp.response(200, list[Actor])
def list_actors():
    return get_actors()

@combat_blp.route("/encounter/initiative", methods=["POST"])
@combat_blp.response(200, list[str])
def post_resolve_initiative():
    return resolve_initiative()

@combat_blp.route("/encounter/reset", methods=["POST"])
@combat_blp.response(200, dict)
def post_reset_encounter():
    reset_encounter()
    return {"message": "Encounter reset"}

@combat_blp.route("/encounter/round/advance", methods=["POST"])
@combat_blp.response(200, dict)
def post_advance_round():
    new_round = advance_round()
    return {"round": new_round}

@combat_blp.route("/encounter/state", methods=["GET"])
@combat_blp.response(200, dict)
def get_encounter_state():
    return encounter_state

@combat_blp.route("/simulate/encounter", methods=["POST"])
@combat_blp.arguments(Encounter)
@combat_blp.response(200, SimulatedCombatResponse)
def post_simulate_encounter(payload):
    try:
        result = simulate_combat(**payload)
        return result
    except Exception as e:
        print("Encounter simulation error:", str(e))
        traceback.print_exc()
        return {"error": "Encounter simulation failed"}, 500

@combat_blp.route("/lore/entry", methods=["POST"])
@combat_blp.arguments(LoreEntry)
@combat_blp.response(201, dict)
def post_lore_entry(payload):
    saved = add_lore_entry(payload)
    return {"message": "Lore entry recorded", "entry": saved}

@combat_blp.route("/lore/actor/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, list[LoreEntry])
def get_lore_for_actor(actor_name):
    return get_lore_by_actor(actor_name)

@combat_blp.route("/lore/round/<int:round_number>", methods=["GET"])
@combat_blp.response(200, list[LoreEntry])
def get_lore_for_round(round_number):
    return get_lore_by_round(round_number)

@combat_blp.route("/lore/all", methods=["GET"])
@combat_blp.response(200, list[LoreEntry])
def get_all_lore_entries():
    return get_all_lore()
