import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from backend.db import init_db


# Load .env vars
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Track uptime
start_time = time.time()

# Get API key from env
API_KEY = os.getenv("API_KEY", "default-dev-key")


# Initialize DB on startup
try:
    init_db()
    logger.info("✅ Database initialized")
except Exception as e:
    logger.warning(f"⚠️ DB init warning: {e}")


# Lifespan context for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 FastAPI TBA-App starting")
    yield
    # Shutdown
    logger.info("🛑 FastAPI TBA-App shutting down")


# Create FastAPI app
application = FastAPI(
    title="TBA-App API",
    description="TTRPG system API server with real-time multiplayer support",
    version="1.0.0",
    lifespan=lifespan,
)


# Add CORS middleware
application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware: Attach request_id and enforce API key
@application.middleware("http")
async def attach_request_id_and_auth(request: Request, call_next):
    """Attach request_id to all requests. Enforce X-API-Key for /api/ routes (except docs/health)."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Exempt routes from API key check
    exempt_paths = ["/docs", "/openapi.json", "/health", "/api/health", "/"]

    # Enforce API key for /api/ routes
    if request.url.path.startswith("/api/") and request.url.path not in exempt_paths:
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != API_KEY:
            logger.warning(
                f"[{request_id}] Unauthorized API key attempt: {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid or missing X-API-Key", "request_id": request_id},
            )

    # Log request
    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Health check (no auth required)
@application.get("/health")
async def health_check():
    """Health check endpoint for Railway and load balancers."""
    return {"status": "ok", "service": "TBA-App"}


# API health check (no auth required)
@application.get("/api/health")
async def api_health_check(request: Request):
    """Detailed health check with DB status."""
    try:
        from backend.db import engine

        with engine.connect() as conn:
            db_ok = True
            db_msg = "Connected"
    except Exception as e:
        db_ok = False
        db_msg = str(e)

    return {
        "status": "ok" if db_ok else "degraded",
        "uptime_seconds": time.time() - start_time,
        "database": {"status": "ok" if db_ok else "error", "message": db_msg},
        "timestamp": time.time(),
        "request_id": request.state.request_id,
    }


# Root endpoint
@application.get("/")
async def root(request: Request):
    """API root — returns links to docs and endpoints."""
    return {
        "message": "TBA-App API — TTRPG system with real-time multiplayer chat",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "api_health": "/api/health",
        "request_id": request.state.request_id,
    }


# Register routers
try:
    from routes.chat import chat_blp

    application.include_router(chat_blp, prefix="/api", tags=["Chat"])
    logger.info("✅ Registered chat_blp")
except Exception as e:
    logger.warning(f"⚠️ Failed to register chat_blp: {e}")

try:
    from routes.combat_fastapi import combat_blp_fastapi

    application.include_router(combat_blp_fastapi, prefix="/api", tags=["Combat"])
    logger.info("✅ Registered combat_blp_fastapi")
except Exception as e:
    logger.warning(f"⚠️ Failed to register combat_blp_fastapi: {e}")

try:
    from routes.character_fastapi import character_blp_fastapi

    application.include_router(character_blp_fastapi, prefix="/api", tags=["Character"])
    logger.info("✅ Registered character_blp_fastapi")
except Exception as e:
    logger.warning(f"⚠️ Failed to register character_blp_fastapi: {e}")

try:
    from routes.roll_blp_fastapi import roll_blp_fastapi

    application.include_router(roll_blp_fastapi, prefix="/api", tags=["Roll"])
    logger.info("✅ Registered roll_blp_fastapi")
except Exception as e:
    logger.warning(f"⚠️ Failed to register roll_blp_fastapi: {e}")

try:
    from routes.effects import effects_blp

    application.include_router(effects_blp, prefix="/api", tags=["Effects"])
    logger.info("✅ Registered effects_blp")
except Exception as e:
    logger.warning(f"⚠️ Failed to register effects_blp: {e}")


# Custom OpenAPI schema
def custom_openapi():
    if application.openapi_schema:
        return application.openapi_schema

    openapi_schema = get_openapi(
        title="TBA-App API",
        version="1.0.0",
        description="TTRPG system API server with real-time multiplayer support",
        routes=application.routes,
    )

    # Add API key requirement to OpenAPI spec
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }

    application.openapi_schema = openapi_schema
    return application.openapi_schema


application.openapi = custom_openapi


# Entry point for dev hot-reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(application, host="0.0.0.0", port=8000)