import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import time
from sqlalchemy.exc import OperationalError
from backend.db import init_db, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_ready = False

for attempt in range(5):
    try:
        with engine.connect() as conn:
            logger.info("✅ DB connection successful")
            init_db()
            db_ready = True
            break
    except OperationalError as e:
        logger.warning(f"⏳ DB not ready (attempt {attempt + 1}/5): {e}")
        time.sleep(5)

if not db_ready:
    logger.error("❌ DB failed to initialize after 5 attempts; app starting in degraded mode")

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
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok", "db_ready": db_ready}