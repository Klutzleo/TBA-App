from urllib import response
from fastapi import APIRouter, Request, Form, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.magic_logic import resolve_spellcast
from routes.schemas.chat import ChatMessageSchema
from routes.schemas.resolve import ResolveRollSchema
from typing import Dict, Any
import json
import logging
import random
import httpx  # For making async HTTP requests
import os
import re

COMBAT_LOG_URL = os.getenv("COMBAT_LOG_URL", "https://tba-app-production.up.railway.app/api/combat/log")

chat_blp = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("uvicorn")

# Simple in-memory connection store: party_id -> list[WebSocket]
active_connections: Dict[str, list[WebSocket]] = {}

def add_connection(party_id: str, ws: WebSocket):
    active_connections.setdefault(party_id, []).append(ws)

def remove_connection(party_id: str, ws: WebSocket):
    if party_id in active_connections:
        try:
            active_connections[party_id].remove(ws)
        except ValueError:
            pass
        if not active_connections[party_id]:
            del active_connections[party_id]

async def broadcast(party_id: str, message: Dict[str, Any]):
    for ws in active_connections.get(party_id, []):
        try:
            await ws.send_json(message)
        except Exception:
            # Best-effort send; failures will be cleaned up on disconnect
            pass


async def broadcast_combat_event(party_id: str, event: Dict[str, Any]):
    """Broadcast a combat event to all sockets in a party."""
    payload = {"type": "combat_event", "party_id": party_id, **event}
    await broadcast(party_id, payload)


def parse_dice_notation(expr: str) -> Dict[str, Any]:
    """Parse dice like '3d6+2' and roll it. Returns breakdown and total."""
    m = re.fullmatch(r"\s*(\d+)d(\d+)([+\-]\d+)?\s*", expr)
    if not m:
        raise ValueError("Invalid dice expression. Try like 3d6+2")
    num = int(m.group(1))
    sides = int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls) + mod
    return {"rolls": rolls, "modifier": mod, "total": total}


async def handle_macro(party_id: str, actor: str, text: str) -> Dict[str, Any]:
    """Handle simple system macros: /roll, /pp, /ip, /sp, /initiative (placeholder)."""
    parts = text.strip().split()
    cmd = parts[0].lower()
    if cmd == "/roll":
        if len(parts) < 2:
            return {"type": "system", "actor": "system", "text": "Usage: /roll 3d6+2", "party_id": party_id}
        try:
            result = parse_dice_notation(parts[1])
            # Math-first formatting: "(4 + 3 + 3) + 2 = 12" or "4 + 3 + 3 = 10"
            plus_join = " + ".join(map(str, result["rolls"]))
            modifier = result["modifier"]
            if modifier:
                mod_str = f" + {abs(modifier)}" if modifier > 0 else f" - {abs(modifier)}"
                equation = f"({plus_join}){mod_str} = {result['total']}"
            else:
                equation = f"{plus_join} = {result['total']}"
            # Include the original expression so the origin of the math is visible in chat
            pretty_text = f"{parts[1]} → {equation}"
            return {
                "type": "dice_roll",
                "actor": actor,
                "text": pretty_text,
                "dice": parts[1],
                "result": result["total"],
                "breakdown": result["rolls"],
                "party_id": party_id,
            }
        except Exception as e:
            return {"type": "system", "actor": "system", "text": f"Dice error: {e}", "party_id": party_id}
    if cmd in {"/pp", "/ip", "/sp"}:
        # Placeholder: roll 1d6 + stat; later tie to character data
        stat = cmd[1:].upper()
        result = random.randint(1, 6) + 1  # +1 as simple edge placeholder
        return {
            "type": "stat_roll",
            "actor": actor,
            "text": f"{stat} roll → {result}",
            "stat": stat,
            "result": result,
            "party_id": party_id,
        }
    if cmd == "/initiative":
        result = random.randint(1, 6) + 1
        return {"type": "initiative", "actor": actor, "text": f"Initiative → {result}", "result": result, "party_id": party_id}
    # Unknown macro → echo as system
    return {"type": "system", "actor": "system", "text": f"Unknown command: {cmd}", "party_id": party_id}

@chat_blp.get("/chat/party/{party_id}/connections", response_model=Dict[str, Any])
async def party_connections(party_id: str):
    """Debug endpoint: see active WebSocket connections for a party."""
    conns = active_connections.get(party_id, [])
    return {"party_id": party_id, "connection_count": len(conns)}

async def log_combat_event(entry: Dict[str, Any]):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(COMBAT_LOG_URL, json=entry)
    except Exception as e:
        logger.warning(f"Combat log failed: {e}")

actor_roll_modes = {
    "Kai": "manual",
    "Aria": "auto",
    "NPC Guard": "auto",
    "Bill": "prompt"
}

@chat_blp.get("/chat", response_class=HTMLResponse)
async def chat_get(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request, "response": None})


@chat_blp.websocket("/chat/party/{party_id}")
async def chat_party_ws(websocket: WebSocket, party_id: str):
    # Accept connection; optional api_key via query param for convenience
    # Note: API key enforcement is not applied to WebSocket in HTTP middleware
    await websocket.accept()
    add_connection(party_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"type": "message", "actor": "unknown", "text": data}
            actor = payload.get("actor", "unknown")
            text = payload.get("text", "")
            if isinstance(text, str) and text.startswith("/"):
                msg = await handle_macro(party_id, actor, text)
            else:
                msg = {
                    "type": payload.get("type", "message"),
                    "actor": actor,
                    "text": text,
                    "party_id": party_id,
                }
            await broadcast(party_id, msg)
    except WebSocketDisconnect:
        remove_connection(party_id, websocket)
    except Exception as e:
        remove_connection(party_id, websocket)
        # Attempt to notify others of disconnect
        try:
            await broadcast(party_id, {"type": "system", "actor": "system", "text": f"Disconnect: {e}", "party_id": party_id})
        except Exception:
            pass


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
        "timestamp": data.timestamp,
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

    await log_combat_event({
    "actor": data.actor,
    "timestamp": data.timestamp,
    "context": data.context,
    "encounter_id": data.context,
    "triggered_by": data.triggered_by or data.actor,
    "narration": response.get("narration"),
    "action": data.action.dict() if data.action else None,
    "roll": data.roll,
    "tethers": data.tethers,
    "log": response.get("log")
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

    await log_combat_event({
        "actor": data.actor,
        "timestamp": getattr(data, "timestamp", "unknown"),
        "context": data.context,
        "encounter_id": data.encounter_id,
        "triggered_by": data.triggered_by or data.actor,
        "narration": narration,
        "roll": {
            "die": data.die,
            "modifiers": data.modifiers,
            "result": data.result
        },
        "outcome": outcome,
        "log": [{
            "event": "resolve_roll",
            "actor": data.actor,
            "result": data.result,
            "outcome": outcome
        }]
    })

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
