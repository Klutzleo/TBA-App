import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.staticfiles import StaticFiles

from backend.db import engine, init_db


# Load .env vars
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Track uptime
start_time = time.time()

# Get API key from env
API_KEY = os.getenv("API_KEY", "default-dev-key")

# Initialize rate limiter for authentication routes
limiter = Limiter(key_func=get_remote_address)


# Lifespan context for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 FastAPI TBA-App starting")
    try:
        # NOW run init_db - migrations will recreate with correct schema
        init_db()
        logger.info("✅ Database initialized")
        
        # Force recreate with SQLAlchemy models (just to be sure)
        from backend.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables verified with UUID types")
        # ================================================================
        # OLD MIGRATION CODE REMOVED
        # All migrations now handled by 000_CLEAN_START.sql
        # ================================================================

        # Old migration scripts removed:
        # - run_phase_2d.py (referenced deprecated party_memberships table)
        # - migrate_to_parties.py (no longer needed with clean schema)
        logger.info("✅ Using 000_CLEAN_START.sql for all migrations")

    except Exception as e:
        logger.warning(f"⚠️ DB init warning: {e}")
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

# Add rate limiter to app state
application.state.limiter = limiter
application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Add CORS middleware
application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ HEALTH CHECK FIRST — before middleware
@application.get("/health", tags=["Health"])
async def health_check():
    """Minimal health check for Railway — no auth required."""
    logger.info("🏥 Health check hit")
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "service": "TBA-App"},
    )


@application.get("/api/health", tags=["Health"])
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
        "request_id": getattr(request.state, "request_id", "N/A"),
    }


# Middleware: Attach request_id and enforce API key
@application.middleware("http")
async def attach_request_id_and_auth(request: Request, call_next):
    """Attach request_id. Enforce X-API-Key for /api/ routes only."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Exempt these paths from ALL authentication (public routes only)
    exempt_paths = {"/health", "/docs", "/openapi.json", "/", "/redoc"}

    # Auth routes (JWT-based authentication)
    auth_paths = {"/api/auth/register", "/api/auth/login", "/api/auth/logout",
                  "/api/auth/me", "/api/auth/forgot-password", "/api/auth/reset-password",
                  "/api/auth/change-password"}

    # All routes that require JWT authentication (not API key)
    jwt_protected_routes = auth_paths | {
        "/api/campaigns", "/api/campaigns/create", "/api/campaigns/browse", "/api/campaigns/join",
        "/api/characters/full"
    }

    # Only enforce API key on /api/ routes (and not on exempt paths or JWT protected routes)
    # Check if path starts with any JWT protected route
    is_jwt_protected = any(request.url.path.startswith(route) or request.url.path == route
                           for route in jwt_protected_routes)

    if request.url.path.startswith("/api/") and request.url.path not in exempt_paths and not is_jwt_protected:
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != API_KEY:
            logger.warning(f"[{request_id}] Unauthorized: {request.method} {request.url.path}")
            return JSONResponse(status_code=403, content={"error": "Invalid X-API-Key"})

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# API info endpoint (moved from root to allow static files at /)
@application.get("/api")
async def api_info(request: Request):
    """API info — returns links to docs and endpoints."""
    return {
        "message": "TBA-App API — TTRPG system with real-time multiplayer chat",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "api_health": "/api/health",
        "ws_test": "/ws-test",
        "request_id": getattr(request.state, "request_id", "N/A"),
    }


# Register routers
try:
    from routes.chat import chat_blp

    application.include_router(chat_blp, prefix="/api", tags=["Chat"])
    logger.info("✅ Registered chat_blp")
except Exception as e:
    logger.warning(f"⚠️ Failed to register chat_blp: {e}")

try:
    from routes.combat_fastapi import router as combat_router

    # Register combat router
    application.include_router(combat_router)
    logger.info("✅ Registered combat_blp_fastapi")
except Exception as e:
    logger.warning(f"⚠️ Failed to register combat_blp_fastapi: {e}")

try:
    from routes.character_fastapi import character_blp_fastapi, party_router, npc_router, ally_router

    application.include_router(character_blp_fastapi, tags=["Character"])
    application.include_router(party_router, tags=["Party"])
    application.include_router(npc_router, tags=["NPCs"])
    application.include_router(ally_router, tags=["Allies"])
    logger.info("✅ Registered character_blp_fastapi, party_router, npc_router, and ally_router")
except Exception as e:
    logger.warning(f"⚠️ Failed to register character_blp_fastapi: {e}")

# TODO: Migrate roll_blp_fastapi to use resolve_multi_die_attack() from roll_logic.py
# try:
#     from routes.roll_blp_fastapi import roll_blp_fastapi
#     application.include_router(roll_blp_fastapi, prefix="/api", tags=["Roll"])
#     logger.info("✅ Registered roll_blp_fastapi")
# except Exception as e:
#     logger.warning(f"⚠️ Failed to register roll_blp_fastapi: {e}")

try:
    from routes.effects import effects_blp

    application.include_router(effects_blp, prefix="/api", tags=["Effects"])
    logger.info("✅ Registered effects_blp")
except Exception as e:
    logger.warning(f"⚠️ Failed to register effects_blp: {e}")

try:
    from routes.campaign_websocket import router as campaign_ws_router
    
    application.include_router(campaign_ws_router, tags=["Campaign"])
    logger.info("✅ Registered campaign_websocket")
except Exception as e:
    logger.warning(f"⚠️ Failed to register campaign_websocket: {e}")

# try:
#     from routes.campaign_routes import router as campaign_router
#
#     application.include_router(campaign_router, tags=["Campaigns"])
#     logger.info("✅ Registered campaign_router")
# except Exception as e:
#     logger.warning(f"⚠️ Failed to register campaign_router: {e}")

try:
    from routes.auth import auth_router

    application.include_router(auth_router, tags=["Authentication"])
    logger.info("✅ Registered auth_router")
except Exception as e:
    logger.warning(f"⚠️ Failed to register auth_router: {e}")

try:
    from routes.campaigns import router as campaigns_router

    application.include_router(campaigns_router, prefix="/api/campaigns", tags=["Campaigns"])
    logger.info("✅ Registered campaigns_router with /api/campaigns prefix")
except Exception as e:
    logger.warning(f"⚠️ Failed to register campaigns_router: {e}")


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


# Serve simple WS test page for Railway/browser testing
@application.get("/ws-test", response_class=HTMLResponse)
async def ws_test_page():
    static_path = Path(__file__).resolve().parent.parent / "static" / "ws-test.html"
    try:
        return HTMLResponse(static_path.read_text(encoding="utf-8"))
    except Exception:
        return HTMLResponse("<h1>WS Test</h1><p>ws-test.html not found.</p>", status_code=404)


# Character creation form
@application.get("/create-character", response_class=HTMLResponse)
async def create_character_form():
    """
    Serve the character creation form.

    Usage: /create-character?campaign_id=<uuid>&return=/campaign/<uuid>
    """
    template_path = Path(__file__).resolve().parent.parent / "templates" / "create_character.html"
    try:
        return HTMLResponse(template_path.read_text(encoding="utf-8"))
    except Exception:
        return HTMLResponse("<h1>Error</h1><p>Character creation form not found.</p>", status_code=404)


@application.get("/ws-test")
async def ws_test():
    ws_test_path = Path("static/ws-test.html")
    if ws_test_path.exists():
        return HTMLResponse(ws_test_path.read_text())
    return HTMLResponse("<h1>Error</h1><p>WebSocket test page not found.</p>", status_code=404)


@application.get("/join/{code}")
async def direct_join_campaign(code: str):
    """
    Direct join link for campaigns.

    Redirects to campaigns.html with join code in URL parameter.
    Frontend will check authentication and join automatically or prompt login.

    Example: /join/A3K9M2 -> /campaigns.html?join=A3K9M2
    """
    from fastapi.responses import RedirectResponse

    # Validate join code format (6 characters, alphanumeric)
    code = code.upper().strip()
    if len(code) != 6 or not code.isalnum():
        return HTMLResponse(
            "<h1>Invalid Join Code</h1><p>Join codes must be 6 alphanumeric characters.</p>",
            status_code=400
        )

    # Redirect to campaigns page with join code
    return RedirectResponse(url=f"/campaigns.html?join={code}", status_code=302)

# Mount static files BEFORE the if __name__ block
application.mount("/", StaticFiles(directory="static", html=True), name="static")

# Entry point for dev hot-reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8000)