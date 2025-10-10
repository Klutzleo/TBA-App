from flask_smorest import Blueprint
from marshmallow import Schema, fields

# 🔧 Backend logic
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

# 🧩 Schemas
from schemas.combat import CombatRollRequest, CombatRollResponse, SimulatedCombatResponse, EncounterRequestSchema
from schemas.actor import ActorRequestSchema, ActorResponseSchema
from schemas.lore_entry import LoreEntrySchema
from schemas.echo import EchoSchema

# 🧪 Utility schema for string lists
class StringListSchema(Schema):
    items = fields.List(fields.Str())

# 📘 Blueprint
combat_blp = Blueprint("combat", "combat", url_prefix="/api/combat", description="Combat endpoints")

# 🎯 Combat Roll
@combat_blp.route("/roll/combat", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, CombatRollResponse)
@combat_blp.doc(tags=["Combat"], summary="Resolve a single combat roll")
def post_roll_combat(payload):
    return resolve_combat_roll(**payload)

# 🧠 Combat Simulation
@combat_blp.route("/roll/combat/simulate", methods=["POST"])
@combat_blp.arguments(CombatRollRequest)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Combat"], summary="Simulate a multi-round combat encounter")
def post_roll_combat_simulate(payload):
    return simulate_combat(**payload)

# 🧩 Encounter Simulation
@combat_blp.route("/simulate/encounter", methods=["POST"])
@combat_blp.arguments(EncounterRequestSchema)
@combat_blp.response(200, SimulatedCombatResponse)
@combat_blp.doc(tags=["Encounter"], summary="Simulate a multi-round encounter with initiative")
def post_simulate_encounter(payload):
    return simulate_combat(**payload)

# 🧙 Register Actor
@combat_blp.route("/actor", methods=["POST"])
@combat_blp.arguments(ActorRequestSchema)
@combat_blp.response(201, ActorResponseSchema)
@combat_blp.doc(tags=["Actor"], summary="Register a new actor")
def register_actor(payload):
    return add_actor(payload)

# 📜 List Actors
@combat_blp.route("/actor/list", methods=["GET"])
@combat_blp.response(200, ActorResponseSchema(many=True))
@combat_blp.doc(tags=["Actor"], summary="List all registered actors")
def list_actors():
    return get_actors()

# Actor status should allow visuals of what is effecting all characters.
@combat_blp.route("/actor/status", methods=["GET"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Actor"], summary="Get current status of all actors")
def get_actor_status():
    status = {}

    for effect in encounter_state.get("effects", []):
        actor = effect["actor"]
        tag = effect["tag"]
        desc = effect["effect"]
        rounds = effect["duration"]

        if actor not in status:
            status[actor] = []

        status[actor].append(f"{tag}: {desc} ({rounds} rounds remaining)")

    return {"status": status}

# Same as status, but for a single character instead of all.
@combat_blp.route("/actor/status/<string:actor_name>", methods=["GET"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Actor"], summary="Get current status of a specific actor")
def get_actor_status_for_actor(actor_name):
    effects = [
        f"{e['tag']}: {e['effect']} ({e['duration']} rounds remaining)"
        for e in encounter_state.get("effects", [])
        if e.get("actor") == actor_name and e.get("duration", 0) > 0
    ]

    return {
        "actor": actor_name,
        "active_effects": effects
    }


@combat_blp.route("/actor/status/all", methods=["GET"])
@combat_blp.response(200, dict)
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

    return {
        "initiative_order": initiative_order,
        "status": status
    }

# 🧠 Initiative
@combat_blp.route("/encounter/initiative", methods=["POST"])
@combat_blp.response(200, StringListSchema)
@combat_blp.doc(tags=["Encounter"], summary="Resolve initiative order")
def post_resolve_initiative():
    return {"items": resolve_initiative()}

# 🔄 Encounter Reset
@combat_blp.route("/encounter/reset", methods=["POST"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Encounter"], summary="Reset the encounter state")
def post_reset_encounter():
    reset_encounter()
    return {"message": "Encounter reset"}

@combat_blp.route("/encounter/round/advance", methods=["POST"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Encounter"], summary="Advance round and expire effects")
def post_advance_round():
    new_round = advance_round()

    expired = []
    active = []

    for effect in encounter_state.get("effects", []):
        effect["duration"] -= 1
        if effect["duration"] <= 0:
            expired.append(effect)
        else:
            active.append(effect)

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

# 📊 Encounter State
@combat_blp.route("/encounter/state", methods=["GET"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Encounter"], summary="Get current encounter state")
def get_encounter_state():
    return encounter_state

# 🧬 Apply Echo
@combat_blp.route("/echo/apply", methods=["POST"])
@combat_blp.arguments(EchoSchema)
@combat_blp.response(201, EchoSchema)
@combat_blp.doc(tags=["Echo"], summary="Apply a persistent effect to an actor")
def apply_echo(payload):
    saved = add_effect(payload)
    add_lore_entry(payload)  # 🪶 Narrate it!
    return saved

# Resolves the Echo
@combat_blp.route("/echo/resolve", methods=["GET"])
@combat_blp.response(200, dict)
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

# 📖 Lore Entry
@combat_blp.route("/lore/entry", methods=["POST"])
@combat_blp.arguments(LoreEntrySchema)
@combat_blp.response(201, dict)
@combat_blp.doc(tags=["Lore"], summary="Record a lore entry")
def post_lore_entry(payload):
    saved = add_lore_entry(payload)
    return {"message": "Lore entry recorded", "entry": saved}

# 📚 Lore Queries
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

@combat_blp.route("/encounter/<string:encounter_id>/summary", methods=["GET"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Encounter"], summary="Get encounter summary")
def get_encounter_summary(encounter_id):
    echoes = [e for e in get_all_lore() if e.get("encounter_id") == encounter_id]
    return {
        "encounter_id": encounter_id,
        "echo_count": len(echoes),
        "lore": echoes
    }

@combat_blp.route("/encounter/current", methods=["GET"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Encounter"], summary="Get current encounter snapshot")
def get_current_encounter():
    return encounter_state

# Expire and cleans up effects so they dont continue or overlap
@combat_blp.route("/effect/expire", methods=["POST"])
@combat_blp.response(200, dict)
@combat_blp.doc(tags=["Echo"], summary="Expire and clean up effects")
def expire_effects():
    expired = []
    active = []

    for effect in encounter_state.get("effects", []):
        effect["duration"] -= 1
        if effect["duration"] <= 0:
            expired.append(effect)
        else:
            active.append(effect)

    encounter_state["effects"] = active

    # 🪶 Optionally log expired effects
    for e in expired:
        add_lore_entry({
            "actor": e["actor"],
            "round": e["round"] + e["duration"],  # approximate expiration round
            "tag": e["tag"],
            "effect": f"{e['tag']} effect expired",
            "duration": 0,
            "encounter_id": e["encounter_id"]
        })

    return {
        "expired_count": len(expired),
        "expired_effects": expired
    }

@combat_blp.route("/round/summary", methods=["GET"])
@combat_blp.response(200, dict)
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
        summary.append(f"{entry['actor']} - {entry['tag']}: {entry['effect']}")

    return {
        "round": round_number,
        "initiative_order": initiative,
        "summary": summary
    }