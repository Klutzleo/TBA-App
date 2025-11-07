from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routes.chat import chat_blp
from routes.effects import effects_blp
from routes.combat_fastapi import combat_blp_fastapi  # ⬅️ Add this line

app = FastAPI()

# ✅ Register routers AFTER app is created
app.include_router(chat_blp)
app.include_router(effects_blp, prefix="/api/effect")
app.include_router(combat_blp_fastapi)  # ⬅️ Mount the combat log router

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})