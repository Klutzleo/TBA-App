import logging
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError
from flask_socketio import SocketIO, emit, join_room, leave_room
from backend.db import db
from models.chat import ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_ready = False
db_error = None

async def init_db_on_startup():
    """Initialize DB asynchronously on first request, not at startup."""
    global db_ready, db_error
    if db_ready or db_error:
        return
    
    from backend.db import init_db, engine
    
    for attempt in range(5):
        try:
            with engine.connect() as conn:
                logger.info(f"✅ DB connection successful (attempt {attempt + 1}/5)")
                init_db()
                db_ready = True
                return
        except OperationalError as e:
            logger.warning(f"⏳ DB not ready (attempt {attempt + 1}/5): {e}")
            if attempt < 4:
                await asyncio.sleep(5)
    
    db_error = "Failed to connect to database after 5 attempts"
    logger.error(f"❌ {db_error}")

# 🧩 Route imports
from routes.chat import chat_blp
# from routes.effects import effects_blp  # ⚠️ COMMENT OUT — this breaks FastAPI startup due to DB import at module level
# from routes.combat_fastapi import combat_blp_fastapi
# from routes.character_fastapi import character_blp_fastapi
# from routes.roll_blp_fastapi import roll_blp_fastapi
# from routes.chat_socket import init_socketio

# 🚀 Create FastAPI app (UI only)
app = FastAPI()

# 🎨 Template engine
templates = Jinja2Templates(directory="templates")

# 🏠 Root route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    """Simple FastAPI health check — does NOT check DB."""
    return {"status": "ok", "runtime": "fastapi-ui-only"}