from backend.db import SessionLocal  # ✅
from models import Echo

def store_echo(schema_type, payload):
    session = SessionLocal()
    echo = Echo(schema_type=schema_type, payload=payload)
    session.add(echo)
    session.commit()
    session.close()