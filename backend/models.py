# models.py
from sqlalchemy import Column, String, DateTime, JSON, Integer
import uuid
from datetime import datetime
from backend.db import Base  # ✅ This works from project root

class Echo(Base):
    __tablename__ = "echoes"
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    schema_type = Column(String)
    payload = Column(JSON)

class RollLog(Base):
    __tablename__ = "roll_logs"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String)
    target = Column(String)
    roll_type = Column(String)  # e.g., "combat", "skill"
    roll_mode = Column(String)  # e.g., "manual", "auto", "prompt"
    triggered_by = Column(String)
    result = Column(JSON)       # Full roll result dict
    modifiers = Column(JSON)    # Any edge, bap, tether, echo bonuses
    session_id = Column(String, nullable=True)
    encounter_id = Column(String, nullable=True)
