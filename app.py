from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from routes.chat import chat_blp
from routes.effects import effects_blp

app = FastAPI()

# ✅ Register routers AFTER app is created
app.include_router(chat_blp)
app.include_router(effects_blp, prefix="/api/effect")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})