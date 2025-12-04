from fastapi import APIRouter, HTTPException
from backend.utils.storage import load_character, save_character
from backend.db import Base  # ✅ Import Base from backend.db, NOT sqlalchemy
import logging

logger = logging.getLogger(__name__)

character_blp_fastapi = APIRouter(prefix="/character", tags=["Character"])

class RollLog(Base):
    __tablename__ = 'roll_logs'
    __table_args__ = {'extend_existing': True}  # ← Add this
    
    id = Column(Integer, primary_key=True)
    character_id = Column(String)
    roll = Column(Integer)
    timestamp = Column(DateTime)

class Echo(Base):
    __tablename__ = 'echoes'
    __table_args__ = {'extend_existing': True}  # ← Add this too if needed
    
    id = Column(Integer, primary_key=True)
    character_id = Column(String)
    message = Column(Text)
    timestamp = Column(DateTime)

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