from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from backend.db import Base

class RollLog(Base):
    __tablename__ = "roll_log"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, index=True)
    session_id = Column(String, index=True, nullable=True)
    encounter_id = Column(String, index=True, nullable=True)
    result = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())