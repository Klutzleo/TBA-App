from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from backend.db import init_db
init_db()  # ✅ This is what Railway will run

# 🧩 Route imports
from routes.chat import chat_blp
from routes.effects import effects_blp
from routes.combat_fastapi import combat_blp_fastapi
from routes.character_fastapi import character_blp_fastapi
from routes.roll_fastapi import roll_blp_fastapi

# 🚀 Create FastAPI app
app = FastAPI()

# 🔌 Register routers
app.include_router(chat_blp)
app.include_router(effects_blp, prefix="/api/effect")
app.include_router(combat_blp_fastapi)
app.include_router(character_blp_fastapi)  # ✅ Mount character sheet router
app.include_router(roll_blp_fastapi)  # ✅ Mount roll router

# 🎨 Template engine
templates = Jinja2Templates(directory="templates")

# 🏠 Root route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})