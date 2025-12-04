import logging
import os
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from backend.db import Base, engine, init_db
from backend.logging_config import setup_logging
from backend.health_checks import check_database, check_env, get_app_metadata
from backend.error_handlers import register_error_handlers
from backend.metrics import increment_request, get_metrics


# Load .env vars
load_dotenv()

# Show current working dir
print("Working directory:", os.getcwd())

# Initialize DB
try:
    init_db()
    print("✅ Database initialized")
except Exception as e:
    print(f"⚠️ DB init warning: {e}")

# Setup logging
setup_logging()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Track uptime
start_time = time.time()

# Get API key from env
API_KEY = os.getenv("API_KEY", "default-dev-key")


# Lifespan context for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 FastAPI app starting")
    yield
    # Shutdown
    logger.info("🛑 FastAPI app shutting down")


# Create FastAPI app
application = FastAPI(
    title="TBA-App API",
    description="TTRPG system API server",
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


# API Key dependency
async def verify_api_key(request: Request) -> None:
    """Verify X-API-Key header for /api/ routes (except docs)."""
    if request.url.path.startswith("/api/") and not request.url.path.startswith(
        "/api/docs"
    ) and not request.url.path.startswith("/api/openapi"):
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != API_KEY:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"error": "Invalid or missing X-API-Key"},
            )


# Middleware to attach request_id and check auth
@application.middleware("http")
async def add_request_id_and_auth(request: Request, call_next):
    import uuid
    from contextvars import ContextVar

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Check auth
    if request.url.path.startswith("/api/") and not any(
        x in request.url.path for x in ["/api/docs", "/api/openapi", "/api/health"]
    ):
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != API_KEY:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"error": "Invalid or missing X-API-Key", "request_id": request_id},
            )

    # Log request
    logger.info(f"[{request_id}] {request.method} {request.url.path}")

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Health check
@application.get("/health")
async def health_check():
    """Simple health check."""
    return {
        "status": "ok",
        "uptime_seconds": time.time() - start_time,
        "timestamp": time.time(),
    }


# Health check with DB status
@application.get("/api/health")
async def api_health_check():
    """Detailed health check with DB and env checks."""
    db_status = check_database()
    env_status = check_env()
    metadata = get_app_metadata()

    return {
        "status": "ok",
        "uptime_seconds": time.time() - start_time,
        "database": db_status,
        "environment": env_status,
        "metadata": metadata,
        "timestamp": time.time(),
    }


# Metrics endpoint
@application.get("/api/metrics")
async def metrics():
    """Get app metrics."""
    return get_metrics()


# OpenAPI schema customization
def custom_openapi():
    if application.openapi_schema:
        return application.openapi_schema

    openapi_schema = get_openapi(
        title="TBA-App API",
        version="1.0.0",
        description="TTRPG system API server",
        routes=application.routes,
    )

    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    application.openapi_schema = openapi_schema
    return application.openapi_schema


application.openapi = custom_openapi

# ✅ Register routers (import after app creation to avoid circular imports)
from routes.chat import chat_blp
from routes.combat_fastapi import combat_blp_fastapi
from routes.character_fastapi import character_blp_fastapi
from routes.roll_blp_fastapi import roll_blp_fastapi
from routes.effects import effects_blp

application.include_router(chat_blp, prefix="/api", tags=["Chat"])
application.include_router(combat_blp_fastapi, prefix="/api", tags=["Combat"])
application.include_router(character_blp_fastapi, prefix="/api", tags=["Character"])
application.include_router(roll_blp_fastapi, prefix="/api", tags=["Roll"])
application.include_router(effects_blp, prefix="/api", tags=["Effects"])


# Root endpoint
@application.get("/")
async def root():
    """API root."""
    return {
        "message": "TBA-App API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "api_health": "/api/health",
    }


# Error handlers (if needed)
register_error_handlers(application)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(application, host="0.0.0.0", port=8000)