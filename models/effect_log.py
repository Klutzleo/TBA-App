from sqlalchemy import Column, String, Integer, Boolean, DateTime
from backend.db import Base
from datetime import datetime

class EffectLog(Base):
    __tablename__ = "effect_log"

    id = Column(String, primary_key=True)  # UUID or hash
    actor = Column(String, nullable=False)
    effect = Column(String, nullable=False)
    source = Column(String, nullable=True)
    hp_change = Column(Integer, nullable=True)
    status = Column(String, nullable=True)
    area_damage = Column(Boolean, default=False)
    narration = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)