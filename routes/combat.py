from flask_smorest import Blueprint
from marshmallow import fields

# Backend logic
from backend.roll_logic import resolve_combat_roll, simulate_combat
from backend.magic_logic import cast_spell, character_from_dict
from backend.combat_utils import resolve_initiative
from backend.encounter_memory import (
    add_actor, add_effect, get_actors,
    reset_encounter, advance_round, encounter_state
)
from backend.lore_log import (
    add_lore_entry, get_lore_by_actor,
    get_lore_by_round, get_all_lore
)

from schemas.lore_entry import LoreEntrySchema

# Schemas
from schemas.combat import (
    CombatRollRequest, CombatRollResponse,
    SimulatedCombatResponse, EncounterRequestSchema,
    ActorRequestSchema, ActorResponseSchema,
    ActorStatusSchema, ActorStatusForActorSchema,
    AllActorStatusSchema, ActorSummarySchema,
    ActorCompareSchema, EchoesSchema, EncounterResetSchema,
    RoundAdvanceSchema, EncounterStateSchema, EncounterValidationSchema,
    EncounterExportSchema, EncounterImportSchema, EchoResolveSchema, LoreEntryResponseSchema, EncounterSummarySchema,
    EncounterSnapshotSchema, EffectExpireSchema, RoundSummarySchema
)

combat_blp = Blueprint("combat", "combat", url_prefix="/api/combat", description="Combat endpoints")

# Combat roll
@combat_blp.route("/roll/combat", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, CombatRollResponse)
@combat_blp.doc(tags=["Combat"], summary="Resolve a single combat roll")
def post_roll_combat(payload):
    return resolve_combat_roll(**payload)

# Combat simulation
@combat_blp.route("/roll/combat/simulate", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Combat"], summary="Simulate a multi-round combat encounter")
def post_roll_combat_simulate(payload):
    return simulate_combat(**payload)

# Encounter simulation
@combat_blp.route("/simulate/encounter", methods=["POST"])
@combat_blp.arguments(EncounterRequestSchema)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Encounter"], summary="Simulate a multi-round encounter with initiative")
def post_simulate_encounter(payload):
    return simulate_combat(**payload)

# Register actor
@combat_blp.route("/actor", methods=["POST"])
@combat_blp.arguments(ActorRequestSchema)
@combat_blp.response(201, ActorResponseSchema)
@combat_blp.doc(tags=["Actor"], summary="Register a new actor")
def register_actor(payload):
    return add_actor(payload)

# List actors
@combat_blp.route("/actor/list", methods=["GET"])
@combat_blp.response(200, ActorResponseSchema(many=True))
@combat_blp.doc(tags=["Actor"], summary="List all registered actors")
def list_actors():
    return get_actors()

# Actor status (all)
@combat_blp.route("/actor/status", methods=["GET"])
@combat_blp.response(200, ActorStatusSchema)
@combat_blp.doc(tags=["Actor"], summary="Get current status of all actors")
def get_actor_status():
    status = {}
    for effect in encounter_state.get("effects", []):
        actor = effect["actor"]
        tag = effect["tag"]
        desc = effect["effect"]
        rounds = effect["duration"]
        status.setdefault(actor, []).append(f"{tag}: {desc} ({rounds} rounds remaining)")
    return {"status": status}

# Actor status (specific)
@combat_blp.route("/actor/status/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, ActorStatusForActorSchema)
@combat_blp.doc(tags=["Actor"], summary="Get current status of a specific actor")
def get_actor_status_for_actor(actor_name):
    effects = [
        f"{e['tag']}: {e['effect']} ({e['duration']} rounds remaining)"
        for e in encounter_state.get("effects", [])
        if e.get("actor") == actor_name and e.get("duration", 0) > 0
    ]
    return {"actor": actor_name, "active_effects": effects}

# Actor status (initiative order)
@combat_blp.route("/actor/status/all", methods=["GET"])
@combat_blp.response(200, AllActorStatusSchema)
@combat_blp.doc(tags=["Actor"], summary="Get status of all actors in initiative order")
def get_all_actor_status():
    status = {}
    initiative_order = encounter_state.get("initiative", [])
    for actor in initiative_order:
        effects = [
            f"{e['tag']}: {e['effect']} ({e['duration']} rounds remaining)"
            for e in encounter_state.get("effects", [])
            if e.get("actor") == actor and e.get("duration", 0) > 0
        ]
        status[actor] = effects
    return {"initiative_order": initiative_order, "status": status}

# Actor summary
@combat_blp.route("/actor/summary/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, ActorSummarySchema)
@combat_blp.doc(tags=["Actor"], summary="Get full round-by-round summary for an actor")
def get_actor_summary(actor_name):
    effects = [
        {
            "round": e["round"],
            "tag": e["tag"],
            "effect": e["effect"],
            "duration": e["duration"]
        }
        for e in encounter_state.get("effects", [])
        if e.get("actor") == actor_name
    ]
    lore = [
        {
            "round": entry["round"],
            "tag": entry["tag"],
            "effect": entry["effect"]
        }
        for entry in get_all_lore()
        if entry.get("actor") == actor_name
    ]
    timeline = sorted(effects + lore, key=lambda x: x["round"])
    return {"actor": actor_name, "timeline": timeline}

# Compare actors
@combat_blp.route("/actor/compare/<string:actor_a>/<string:actor_b>", methods=["GET"])
@combat_blp.response(200, ActorCompareSchema)
@combat_blp.doc(tags=["Actor"], summary="Compare two actors' effects and lore")
def compare_actors(actor_a, actor_b):
    def get_effects(actor):
        return [
            {
                "round": e["round"],
                "tag": e["tag"],
                "effect": e["effect"],
                "duration": e["duration"]
            }
            for e in encounter_state.get("effects", [])
            if e.get("actor") == actor
        ]
    def get_lore(actor):
        return [
            {
                "round": entry["round"],
                "tag": entry["tag"],
                "effect": entry["effect"]
            }
            for entry in get_all_lore()
            if entry.get("actor") == actor
        ]
    return {
        "actor_a": {"name": actor_a, "effects": get_effects(actor_a), "lore": get_lore(actor_a)},
        "actor_b": {"name": actor_b, "effects": get_effects(actor_b), "lore": get_lore(actor_b)}
    }

# Echoes for actor
@combat_blp.route("/actor/echoes/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, EchoesSchema)
@combat_blp.doc(tags=["Actor"], summary="Get all echoes applied to an actor")
def get_actor_echoes(actor_name):
    echoes = [
        {
            "tag": e["tag"],
            "effect": e["effect"],
            "duration": e["duration"],
            "round": e["round"],
            "encounter_id": e["encounter_id"]
        }
        for e in encounter_state.get("effects", [])
        if e.get("actor") == actor_name
    ]
    return {"actor": actor_name, "echoes": echoes, "count": len(echoes)}

# Encounter reset
@combat_blp.route("/encounter/reset", methods=["POST"])
@combat_blp.response(200, EncounterResetSchema)
@combat_blp.doc(tags=["Encounter"], summary="Reset the encounter state")
def post_reset_encounter():
    reset_encounter()
    return {"message": "Encounter reset"}

# Advance round
@combat_blp.route("/encounter/round/advance", methods=["POST"])
@combat_blp.response(200, RoundAdvanceSchema)
@combat_blp.doc(tags=["Encounter"], summary="Advance round and expire effects")
def post_advance_round():
    new_round = advance_round()
    expired, active = [], []

    for effect in encounter_state.get("effects", []):
        effect["duration"] -= 1
        (expired if effect["duration"] <= 0 else active).append(effect)

    encounter_state["effects"] = active

    for e in expired:
        add_lore_entry({
            "actor": e["actor"],
            "round": new_round,
            "tag": e["tag"],
            "effect": f"{e['tag']} effect expired",
            "duration": 0,
            "encounter_id": e["encounter_id"]
        })

    return {
        "round": new_round,
        "expired_count": len(expired),
        "expired_effects": expired
    }

# Encounter state
@combat_blp.route("/encounter/state", methods=["GET"])
@combat_blp.response(200, EncounterStateSchema)
@combat_blp.doc(tags=["Encounter"], summary="Get current encounter state")
def get_encounter_state():
    return encounter_state

# Validate encounter
@combat_blp.route("/encounter/validate", methods=["GET"])
@combat_blp.response(200, EncounterValidationSchema)
@combat_blp.doc(tags=["Encounter"], summary="Validate encounter state integrity")
def validate_encounter():
    errors = []
    round_number = encounter_state.get("round")
    if not isinstance(round_number, int) or round_number < 0:
        errors.append("Invalid round number")

    initiative = encounter_state.get("initiative", [])
    if not isinstance(initiative, list) or not all(isinstance(i, str) for i in initiative):
        errors.append("Initiative must be a list of actor names")

    for idx, effect in enumerate(encounter_state.get("effects", [])):
        for field in ["actor", "tag", "effect", "duration", "round", "encounter_id"]:
            if field not in effect:
                errors.append(f"Effect {idx} missing field: {field}")
            elif field == "duration" and not isinstance(effect["duration"], int):
                errors.append(f"Effect {idx} has non-integer duration")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "round": round_number,
        "initiative_count": len(initiative),
        "effect_count": len(encounter_state.get("effects", []))
    }

# Export encounter
@combat_blp.route("/encounter/export", methods=["GET"])
@combat_blp.response(200, EncounterExportSchema)
@combat_blp.doc(tags=["Encounter"], summary="Export full encounter state")
def export_encounter():
    return {"encounter_state": encounter_state}

# Import encounter
@combat_blp.route("/encounter/import", methods=["POST"])
@combat_blp.arguments(EncounterImportSchema)
@combat_blp.response(200, EncounterResetSchema)
@combat_blp.doc(tags=["Encounter"], summary="Import a full encounter state")
def import_encounter(data):
    global encounter_state
    if "encounter_state" not in data or not isinstance(data["encounter_state"], dict):
        return {"success": False, "error": "Missing or invalid encounter_state payload"}

    encounter_state = data["encounter_state"]
    return {
        "success": True,
        "message": "Encounter state imported successfully",
        "round": encounter_state.get("round"),
        "initiative_count": len(encounter_state.get("initiative", [])),
        "effect_count": len(encounter_state.get("effects", []))
    }

# Resolve echoes
@combat_blp.route("/echo/resolve", methods=["GET"])
@combat_blp.response(200, EchoResolveSchema)
@combat_blp.doc(tags=["Echo"], summary="Resolve and narrate active effects")
def resolve_echoes():
    active = []
    for effect in encounter_state.get("effects", []):
        if effect.get("duration", 0) > 0:
            actor = effect["actor"]
            tag = effect["tag"]
            desc = effect["effect"]
            rounds = effect["duration"]
            active.append(f"{actor} is affected by {tag}: {desc} ({rounds} rounds remaining)")
    return {"active_effects": active}

# Lore entry
@combat_blp.route("/lore/entry", methods=["POST"])
@combat_blp.arguments(LoreEntrySchema)
@combat_blp.response(201, LoreEntryResponseSchema)
@combat_blp.doc(tags=["Lore"], summary="Record a lore entry")
def post_lore_entry(payload):
    saved = add_lore_entry(payload)
    return {"message": "Lore entry recorded", "entry": saved}

# Lore queries
@combat_blp.route("/lore/actor/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, LoreEntrySchema(many=True))
@combat_blp.doc(tags=["Lore"], summary="Get lore by actor")
def get_lore_by_actor_route(actor_name):
    return get_lore_by_actor(actor_name)

@combat_blp.route("/lore/round/<int:round_number>", methods=["GET"])
@combat_blp.response(200, LoreEntrySchema(many=True))
@combat_blp.doc(tags=["Lore"], summary="Get lore by round")
def get_lore_for_round(round_number):
    return get_lore_by_round(round_number)

@combat_blp.route("/lore/all", methods=["GET"])
@combat_blp.response(200, LoreEntrySchema(many=True))
@combat_blp.doc(tags=["Lore"], summary="Get all lore entries")
def get_all_lore_entries():
    return get_all_lore()

@combat_blp.route("/lore/encounter/<string:encounter_id>", methods=["GET"])
@combat_blp.response(200, LoreEntrySchema(many=True))
@combat_blp.doc(tags=["Lore"], summary="Get lore by encounter ID")
def get_lore_for_encounter(encounter_id):
    return [entry for entry in get_all_lore() if entry.get("encounter_id") == encounter_id]

@combat_blp.route("/lore/tag/<string:tag>", methods=["GET"])
@combat_blp.response(200, LoreEntrySchema(many=True))
@combat_blp.doc(tags=["Lore"], summary="Get lore by tag")
def get_lore_by_tag(tag):
    return [entry for entry in get_all_lore() if entry.get("tag") == tag]

# Encounter summary
@combat_blp.route("/encounter/<string:encounter_id>/summary", methods=["GET"])
@combat_blp.response(200, EncounterSummarySchema)
@combat_blp.doc(tags=["Encounter"], summary="Get encounter summary")
def get_encounter_summary(encounter_id):
    echoes = [e for e in get_all_lore() if e.get("encounter_id") == encounter_id]
    return {
        "encounter_id": encounter_id,
        "echo_count": len(echoes),
        "lore": echoes
    }

# Current encounter snapshot
@combat_blp.route("/encounter/current", methods=["GET"])
@combat_blp.response(200, EncounterSnapshotSchema)
@combat_blp.doc(tags=["Encounter"], summary="Get current encounter snapshot")
def get_current_encounter():
    return encounter_state

# Expire effects
@combat_blp.route("/effect/expire", methods=["POST"])
@combat_blp.response(200, EffectExpireSchema)
@combat_blp.doc(tags=["Echo"], summary="Expire and clean up effects")
def expire_effects():
    expired, active = [], []
    for effect in encounter_state.get("effects", []):
        effect["duration"] -= 1
        (expired if effect["duration"] <= 0 else active).append(effect)

    encounter_state["effects"] = active

    for e in expired:
        add_lore_entry({
            "actor": e["actor"],
            "round": e["round"] + e["duration"],
            "tag": e["tag"],
            "effect": f"{e['tag']} effect expired",
            "duration": 0,
            "encounter_id": e["encounter_id"]
        })

    return {
        "expired_count": len(expired),
        "expired_effects": expired
    }

# Round summary
@combat_blp.route("/round/summary", methods=["GET"])
@combat_blp.response(200, RoundSummarySchema)
@combat_blp.doc(tags=["Encounter"], summary="Narrate the current round summary")
def get_round_summary():
    round_number = encounter_state.get("round", 0)
    initiative = encounter_state.get("initiative", [])
    effects = encounter_state.get("effects", [])
    lore = [entry for entry in get_all_lore() if entry.get("round") == round_number]

    summary = []
    for actor in initiative:
        actor_effects = [
            f"{e['tag']}: {e['effect']} ({e['duration']} rounds remaining)"
            for e in effects
            if e.get("actor") == actor and e.get("duration", 0) > 0
        ]
        if actor_effects:
            summary.append(f"{actor} is affected by: " + "; ".join(actor_effects))
        else:
            summary.append(f"{actor} is ready with no active effects.")

    for entry in lore:
        summary.append(f"{entry['actor']} -{entry['tag']}: {entry['effect']}")

    return {
        "round": round_number,
        "initiative_order": initiative,
        "summary": summary
    }

@combat_blp.route("/spell/cast", methods=["POST"])
@combat_blp.arguments(SpellCastRequest)
@combat_blp.response(200, SpellCastResponse)
@combat_blp.doc(tags=["Spellcasting"], summary="Cast a spell and resolve effects")
def cast_spell_route(payload):
    result = cast_spell(**payload)
    return result