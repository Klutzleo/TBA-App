from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from backend.db import Base

class RollLog(Base):
    __tablename__ = "roll_logs"  # ✅ match the query exactly

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, index=True)
    target = Column(String, nullable=True)
    roll_type = Column(String, nullable=True)
    roll_mode = Column(String, nullable=True)
    triggered_by = Column(String, nullable=True)
    result = Column(JSON, nullable=False)
    modifiers = Column(JSON, nullable=True)
    session_id = Column(String, nullable=True)
    encounter_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())