import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# For dev convenience: run FastAPI with hot-reload
# Usage: uvicorn app:application --reload --port 8001

from backend.app import application

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8001, reload=True)