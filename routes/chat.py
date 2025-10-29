from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
from backend.magic_logic import resolve_spellcast

chat_blp = APIRouter()
templates = Jinja2Templates(directory="templates")

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
            "narration": result["notes"],
            "effects": result["effects"],
            "log": result["log"]
        }
    except Exception as e:
        response = { "narration": [f"Error: {str(e)}"], "effects": [], "log": [] }

    return templates.TemplateResponse("chat.html", {"request": request, "response": response})