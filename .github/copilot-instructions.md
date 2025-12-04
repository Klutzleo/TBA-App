<!-- Copilot instructions for TBA-App -->
# Copilot Instructions — TBA-App

Short, focused guidance so an AI coding agent can be productive immediately.

1) Big picture
- **Single FastAPI runtime:** `backend/app.py` (FastAPI + uvicorn) is the canonical API server and entrypoint used by the `Procfile` (`uvicorn backend.app:application --host 0.0.0.0 --port 8000`). FastAPI is chosen for native async/await support, built-in WebSocket capability, and better concurrency handling — essential for a multiplayer online TTRPG with real-time chat and simultaneous player actions.
- The top-level `app.py` (FastAPI) is used for dev convenience (hot-reload) and can serve the template-based UI if needed.
- Core domain logic lives in `backend/` (e.g., `combat_utils.py`, `effect_engine.py`, `magic_logic.py`, `roll_logic.py`, `encounter_memory.py`). Routes glue HTTP endpoints to backend logic in `routes/`.

2) Where to look first
- `backend/app.py` — FastAPI API server configuration, router registration, request middleware (request id assignment, API key enforcement), OpenAPI setup, WebSocket handlers.
- `app.py` (project root) — Dev entry point; imports `backend/app.py` for hot-reload testing.
- `routes/` — HTTP/WebSocket endpoints. Use FastAPI routers (e.g., `routes/chat.py`, `routes/combat_fastapi.py`). Older Flask-Smorest blueprints (if any) are deprecated in favor of FastAPI equivalents.
- `schemas/` and `routes/schemas/` — Pydantic models (preferred) and any legacy marshmallow schemas. Use Pydantic for FastAPI validation.
- `backend/db.py` — SQLAlchemy engine, `DATABASE_URL` default (`sqlite:///local.db`). Production expects Postgres via env `DATABASE_URL`.

3) Important runtime & env patterns
- API key: `backend/app.py` middleware enforces `X-API-Key` header against `API_KEY` env var for `/api/` routes (docs/openapi endpoints are exempt). To exercise protected endpoints set `$env:API_KEY = 'yourkey'` in PowerShell.
- Request correlation: `backend/app.py` attaches a `request_id` to each incoming request. When adding log statements, preserve or propagate `request.state.request_id` so logs remain traceable.
- DB init: call `init_db()` (imported from `backend/db.py`) before using models. `backend/app.py` calls it on startup — keep that ordering when changing startup code.
- Stateful memory: `backend/encounter_memory.py` and `memory/lore_store.py` use in-memory globals for encounter state and lore — these are intentionally stateful for quick prototyping. Be cautious with gunicorn `--workers > 1` (workers do not share memory); use `--workers 1` or move to persistent DB storage for multi-worker deployments.
- WebSocket support: FastAPI's native WebSocket support is used for real-time multiplayer chat. See `routes/chat.py` for WebSocket endpoint examples.

4) How to run locally (PowerShell examples)
- Run FastAPI backend (prod-like with uvicorn):
```powershell
$env:API_KEY = 'devkey'
# install requirements first (recommended in a venv)
# pip install -r requirements.txt
uvicorn backend.app:application --host 0.0.0.0 --port 8000
```
- Run FastAPI backend (dev with hot-reload):
```powershell
$env:API_KEY = 'devkey'
python app.py
# or: uvicorn backend.app:application --reload --host 0.0.0.0 --port 8000
```
- Notes: `Procfile` uses `uvicorn backend.app:application --host 0.0.0.0 --port 8000` for deployment. FastAPI enables async route handlers and WebSocket connections for real-time multiplayer features.

5) Common codebase conventions & gotchas
- Pydantic models drive request/response schemas. When you change a JSON contract, update the corresponding Pydantic class in `routes/schemas/` and register it with its router.
- When adding public endpoints, register the router in `backend/app.py` via `application.include_router()`.
- Global state: `encounter_state` (in `backend/encounter_memory.py`) and other in-memory stores are used heavily — prefer returning pure data from `backend/*` helpers and keep mutation centralized in `encounter_memory` to avoid inconsistent state.
- Logging: `backend/logging_config.py` configures handlers/formatters. Do not assume default logger behavior; new handlers should respect the `request_id` filter.
- WebSocket handlers: Use `@router.websocket()` decorator for real-time connections. See `routes/chat.py` for multiplayer chat example.

6) Integration points & external deps
- DB: `DATABASE_URL` (default `sqlite:///local.db`; production typically uses Postgres — `psycopg2-binary` is in `requirements.txt`).
- OpenAPI: FastAPI auto-generates OpenAPI spec and serves docs at `/docs` and `/openapi.json`.
- Deployment: `gunicorn` with `--worker-class uvicorn.workers.UvicornWorker` or direct `uvicorn` serve the FastAPI app (see `Procfile`). Use `--workers 1` for stateful in-memory stores.

7) Tests & dev tools
- `requirements.txt` includes `pytest`. Run `pytest` after adding tests. Use `yamllint`/`ruff` locally as desired.

8) Quick examples to reference
- Add a new combat endpoint: create or modify `routes/combat_fastapi.py` (router `combat_blp_fastapi`) and register it in `backend/app.py`; domain logic lives in `backend/roll_logic.py` or `backend/combat_utils.py`.
- Inspect auth behavior: check `backend/app.py` middleware — endpoints under `/api/` require `X-API-Key` (except docs/openapi/health).
- Add WebSocket chat: see `routes/chat.py` for `@router.websocket()` example. Handlers receive async connections and can emit/receive messages for real-time multiplayer.
- Schema files: use Pydantic models in `routes/schemas/` — they auto-validate and generate OpenAPI docs.

9) When editing code — checklist for PRs
- Update or add Pydantic schemas in `routes/schemas/` if changing API contracts.
- Update router registration in `backend/app.py` if adding new endpoints.
- Make state changes through `backend/encounter_memory.py` helpers rather than mutating globals directly.
- Preserve `request.state.request_id` usage when adding logs or middleware.
- Use async/await for all route handlers to leverage FastAPI's concurrency.

If anything above is unclear or you want more examples (specific route, schema, or a small runnable example), tell me which area to expand and I will iterate.
