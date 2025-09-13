# models.py
from sqlalchemy import Column, String, DateTime, JSON
import uuid
from datetime import datetime
from backend.db import Base  # ✅ This works from project root

class Echo(Base):
    __tablename__ = "echoes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    schema_type = Column(String)
    payload = Column(JSON)