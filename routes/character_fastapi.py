from fastapi import APIRouter, HTTPException
from backend.utils.storage import load_character, save_character

character_blp_fastapi = APIRouter(prefix="/api/character", tags=["Character"])

@character_blp_fastapi.get("/sheet/{character_id}")
def get_character_sheet(character_id: str):
    print(f"📥 GET request received for: {character_id}")
    character = load_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character

@character_blp_fastapi.patch("/sheet/{character_id}")
def update_character_sheet(character_id: str, updates: dict):
    character = load_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    character.update(updates)
    save_character(character_id, character)
    return character