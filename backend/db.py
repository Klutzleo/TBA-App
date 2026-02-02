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

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Test connections before using
        pool_recycle=3600,       # Recycle connections every hour
        pool_size=5,             # Connection pool size
        max_overflow=10,         # Max connections beyond pool_size
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )
else:
    # SQLite doesn't need these settings
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    from models.effect_log import EffectLog
    from models.roll_log import RollLog
    from backend.models import Character, Party, PartyMembership, NPC, CombatTurn

    Base.metadata.create_all(bind=engine)


from sqlalchemy.orm import Session

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
