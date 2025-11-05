from backend.effect_engine import resolve_effect, undo_effect, simulate_effect
from flask import current_app
from fastapi import APIRouter
from routes.schemas.effect import (
    EffectPreviewSchema,
    EffectPreviewResponseSchema,
    EffectResolveSchema,
    EffectResolveResponseSchema,
    EffectUndoSchema,
    EffectUndoResponseSchema,
    CustomEffectSchema
)

effects_blp = APIRouter()

custom_effects = {}  # Temporary in-memory store


@effects_blp.route("/preview", methods=["POST"])
@effects_blp.arguments(EffectPreviewSchema)
@effects_blp.response(200, EffectPreviewResponseSchema)
def preview_effect(data):
    outcome, narration = simulate_effect(**data)
    return {
        "status": "success",
        "actor": data["actor"],
        "simulated_outcome": outcome,
        "narration": narration if data.get("narrate") else None
    }

@effects_blp.route("/resolve", methods=["POST"])
@effects_blp.arguments(EffectResolveSchema)
@effects_blp.response(200, EffectResolveResponseSchema)
def resolve_effect_route(data):
    result = resolve_effect(**data)
    return {
        "status": "success",
        **result
    }

@effects_blp.route("/undo", methods=["POST"])
@effects_blp.arguments(EffectUndoSchema)
@effects_blp.response(200, EffectUndoResponseSchema)
def undo_effect_route(data):
    result = undo_effect(**data)
    return {
        "status": "success",
        **result
    }

@effects_blp.route("/custom", methods=["POST"])
@effects_blp.arguments(CustomEffectSchema)
def create_custom_effect(data):
    name = data["name"]
    custom_effects[name] = data
    current_app.logger.info(f"Custom effect registered: {name}")
    return {"status": "registered", "effect": name}
