from fastapi import APIRouter
from fastapi import Body
from typing import Dict

from backend.effect_engine import resolve_effect, undo_effect, simulate_effect
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
custom_effects: Dict[str, Dict] = {}  # Temporary in-memory store


@effects_blp.post("/preview", response_model=EffectPreviewResponseSchema)
async def preview_effect(data: EffectPreviewSchema = Body(...)):
    outcome, narration = simulate_effect(**data.dict())
    return {
        "status": "success",
        "actor": data.actor,
        "simulated_outcome": outcome,
        "narration": narration if data.narrate else None
    }


@effects_blp.post("/resolve", response_model=EffectResolveResponseSchema)
async def resolve_effect_route(data: EffectResolveSchema = Body(...)):
    result = resolve_effect(**data.dict())
    return {
        "status": "success",
        **result
    }


@effects_blp.post("/undo", response_model=EffectUndoResponseSchema)
async def undo_effect_route(data: EffectUndoSchema = Body(...)):
    result = undo_effect(**data.dict())
    return {
        "status": "success",
        **result
    }


@effects_blp.post("/custom")
async def create_custom_effect(data: CustomEffectSchema = Body(...)):
    name = data.name
    custom_effects[name] = data.dict()
    return {
        "status": "registered",
        "effect": name
    }