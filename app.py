import logging
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError

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
from routes.effects import effects_blp
from routes.combat_fastapi import combat_blp_fastapi
from routes.character_fastapi import character_blp_fastapi
from routes.roll_blp_fastapi import roll_blp_fastapi

# 🚀 Create FastAPI app
app = FastAPI()

# 🔌 Register routers
app.include_router(chat_blp)
app.include_router(effects_blp, prefix="/api/effect")
app.include_router(combat_blp_fastapi)
app.include_router(character_blp_fastapi)
app.include_router(roll_blp_fastapi)

# 🎨 Template engine
templates = Jinja2Templates(directory="templates")

# 🏠 Root route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    await init_db_on_startup()
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    """Health check — returns 200 immediately even if DB is initializing."""
    return {"status": "ok", "db_ready": db_ready, "db_error": db_error}