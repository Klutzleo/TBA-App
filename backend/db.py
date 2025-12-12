# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv
import os as _os

# When running inside a container (Docker, Railway), avoid loading the
# repository `.env` file. Loading it at import-time can override platform
# provided env vars or point the app at remote DB hosts that are not
# reachable from the local environment. Only load `.env` when not running
# inside a container (no `/.dockerenv`).
if not _os.path.exists("/.dockerenv"):
    load_dotenv()

DATABASE_URL = _os.getenv("DATABASE_URL", "sqlite:///local.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    from models.effect_log import EffectLog
    from models.roll_log import RollLog
    from backend.models import Character, Party, PartyMembership
    
    Base.metadata.create_all(bind=engine)


from sqlalchemy.orm import Session

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
