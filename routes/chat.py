from urllib import response
from fastapi import APIRouter, Request, Form, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.magic_logic import resolve_spellcast
from routes.schemas.chat import ChatMessageSchema
from routes.schemas.resolve import ResolveRollSchema
from typing import Dict, Any
import json
import logging
import random

chat_blp = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("uvicorn")

actor_roll_modes = {
    "Kai": "manual",
    "Aria": "auto",
    "NPC Guard": "auto",
    "Bill": "prompt"
}

@chat_blp.get("/chat", response_class=HTMLResponse)
async def chat_get(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request, "response": None})


@chat_blp.post("/chat", response_class=HTMLResponse)
async def chat_post(request: Request, payload: str = Form(...)):
    try:
        data = json.loads(payload)
        result = resolve_spellcast(
            caster=data["caster"],
            target=data["target"],
            spell=data["spell"],
            encounter_id=data.get("encounter_id"),
            log=True
        )
        response = {
            "narration": result.get("notes", []),
            "effects": result.get("effects", []),
            "log": result.get("log", [])
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        response = {
            "narration": [f"Error: {str(e)}"],
            "effects": [],
            "log": []
        }

    return templates.TemplateResponse("chat.html", {"request": request, "response": response})

@chat_blp.post("/chat/api", response_model=Dict[str, Any])
async def chat_api(data: ChatMessageSchema = Body(...)):
    response = {
        "actor": data.actor,
        "triggered_by": data.triggered_by or data.actor,
        "message": data.message,
        "context": data.context,
        "timestamp": data.timestamp
    }

    # Handle action logic
    if data.action:
        if data.action.type in ["spell", "technique"]:
            response["narration"] = f"{data.actor} uses {data.action.name} ({data.action.type})!"
            response["simulated_outcome"] = {
                "traits": data.action.traits,
                "tags": data.action.tags
            }

        elif data.action.type == "custom":
            response["narration"] = f"{data.actor} performs a custom move: {data.action.name}. {data.action.description or ''}"

        elif data.action.type in ["buff", "debuff"]:
            response["narration"] = f"{data.actor} applies a {data.action.type}: {data.action.name}."

        elif data.action.type == "summon":
            response["narration"] = f"{data.actor} summons: {data.action.name}. {data.action.description or ''}"

    # Handle tethers
    if data.tethers:
        response["tether_echoes"] = [
            f"Tether '{t}' may trigger a bonus or memory echo." for t in data.tethers
        ]

    # Handle roll metadata
    if data.roll:
        response["roll_metadata"] = data.roll

    # Handle roll mode logic
    target = data.actor
    roll_mode = actor_roll_modes.get(target, "manual")

    if roll_mode in ["manual", "prompt"]:
        response["roll_request"] = {
            "target": target,
            "type": "defense",
            "reason": f"Incoming action: {data.action.name}",
            "expected_die": "1d10 + PP + Edge",
            "submit_to": "/resolve_roll",
            "example_payload": {
                "actor": target,
                "roll_type": "defense",
                "die": "1d10",
                "modifiers": {"PP": 2, "Edge": 1},
                "result": 11,
                "context": data.context,
                "triggered_by": data.triggered_by or target
                        }
                    }   
    
    if roll_mode == "prompt":
        response["roll_request"]["fallback_time"] = "5 minutes"
    elif roll_mode == "auto":
        modifiers = {"PP": 2, "Edge": 1}  # Stubbed for now
        result = simulate_roll("1d10", modifiers)
        response["auto_roll"] = {
            "target": target,
            "type": "defense",
            "die": "1d10",
            **result
        }
        response.setdefault("log", []).append({
            "event": "auto_roll",
            "actor": target,
            "details": result
        })

    return response

@chat_blp.get("/chat/schema", response_model=Dict[str, Any])
async def chat_schema():
    return {
        "actor": "Kai",
        "triggered_by": "Story Weaver",
        "message": "Kai casts Ember Veil!",
        "context": "Volcanic battlefield",
        "action": {
            "name": "Ember Veil",
            "type": "spell",
            "target": "aoe",
            "traits": {"IP": 3, "Edge": 2},
            "tags": ["fire", "protective"],
            "description": "A veil of flame shields allies and scorches nearby foes."
        },
        "tethers": ["Protect the innocent"],
        "roll": {
            "die": "1d10",
            "modifiers": {"IP": 3, "Edge": 2},
            "result": 9
        },
        "timestamp": "2025-11-07T11:30:00"
    }

def simulate_roll(die: str, modifiers: Dict[str, int]) -> Dict[str, Any]:
    """
    Simulates a roll like '1d10' and adds modifiers.
    Returns the breakdown and total.
    """
    num, sides = map(int, die.lower().split("d"))
    rolls = [random.randint(1, sides) for _ in range(num)]
    mod_total = sum(modifiers.values())
    total = sum(rolls) + mod_total

    return {
        "rolls": rolls,
        "modifiers": modifiers,
        "total": total
    }

@chat_blp.post("/resolve_roll", response_model=Dict[str, Any])
async def resolve_roll(data: ResolveRollSchema = Body(...)):
    narration = f"{data.actor} resolves a {data.roll_type} roll with {data.result} using {data.die}."
    
    # Stubbed logic — later compare against incoming threat
    outcome = "success" if data.result >= 10 else "failure"

    return {
        "actor": data.actor,
        "triggered_by": data.triggered_by or data.actor,
        "roll_type": data.roll_type,
        "result": data.result,
        "outcome": outcome,
        "narration": narration,
        "log": [{
            "event": "resolve_roll",
            "actor": data.actor,
            "roll": {
                "die": data.die,
                "modifiers": data.modifiers,
                "result": data.result
            },
            "outcome": outcome
        }]
    }
