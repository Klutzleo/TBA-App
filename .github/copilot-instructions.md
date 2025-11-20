<!-- Copilot instructions for TBA-App -->
# Copilot Instructions — TBA-App

Short, focused guidance so an AI coding agent can be productive immediately.

1) Big picture
- Dual runtime: a Flask-based API (primary backend) and a FastAPI front-facing app. The canonical API server is `backend/app.py` (Flask + `flask-smorest`) and is the entrypoint used by the `Procfile` (`gunicorn backend.app:application`). The top-level `app.py` (FastAPI) is used to serve the template-based UI and newer FastAPI routers (look for `*_fastapi` modules under `routes/`).
- Core domain logic lives in `backend/` (e.g., `combat_utils.py`, `effect_engine.py`, `magic_logic.py`, `roll_logic.py`, `encounter_memory.py`). Routes glue HTTP endpoints to backend logic in `routes/`.

2) Where to look first
- `backend/app.py` — API server configuration, blueprint registration, request middleware (request id assignment, API key enforcement), OpenAPI setup.
- `app.py` (project root) — FastAPI + Jinja templates, registers `routes/*_fastapi` routers and serves `/`.
- `routes/` — HTTP endpoints. Many are Flask-Smorest Blueprints (e.g., `routes/combat.py`) and some FastAPI router equivalents (`routes/combat_fastapi.py`). Use the Flask blueprints as ground truth for API behavior; FastAPI files mostly mirror or adapt those routes.
- `schemas/` and `routes/schemas/` — JSON schemas and marshmallow schemas used for validation and OpenAPI generation.
- `backend/db.py` — SQLAlchemy engine, `DATABASE_URL` default (`sqlite:///local.db`). Production expects a DB via env `DATABASE_URL` (e.g., Postgres).

3) Important runtime & env patterns
- API key: `backend/app.py` enforces `X-API-Key` header against `API_KEY` env var for `/api/` routes (docs/openapi endpoints are exempt). To exercise protected endpoints set `$env:API_KEY = 'yourkey'` in PowerShell.
- Request correlation: `backend/app.py` attaches a `request_id` to each incoming request and adds a logging filter. When adding log statements, preserve or propagate `g.request_id` so logs remain traceable.
- DB init: call `init_db()` (imported from `backend/db.py`) before using models. `main.py` and `app.py` call/init the DB on startup — keep that ordering when changing startup code.
- Stateful memory: `backend/encounter_memory.py` and `memory/lore_store.py` use in-memory globals for encounter state and lore — these are intentionally stateful for quick prototyping. Be cautious when converting to multithreaded or multi-worker servers (gunicorn workers will not share memory).

4) How to run locally (PowerShell examples)
- Run Flask backend (prod-like with gunicorn):
```powershell
$env:API_KEY = 'devkey'
# install requirements first (recommended in a venv)
# pip install -r requirements.txt
gunicorn backend.app:application --bind 0.0.0.0:8000
```
- Run Flask backend with Flask CLI (dev):
```powershell
$env:FLASK_APP = 'backend.app'
$env:API_KEY = 'devkey'
flask run --port 5000
```
- Run FastAPI front-end (dev):
```powershell
$env:API_KEY = 'devkey'
uvicorn app:app --reload --port 8001
```
- Notes: `Procfile` uses `gunicorn backend.app:application` for deployment (Heroku-style). The FastAPI `app.py` and Flask `backend/app.py` coexist — run the one appropriate for your change set.

5) Common codebase conventions & gotchas
- Marshmallow + flask-smorest drive request/response schemas. When you change a JSON schema under `schemas/`, update the corresponding marshmallow class in `routes/schemas` and register it with its blueprint.
- When adding public endpoints, add the blueprint registration in `backend/app.py` (for Flask) and consider adding a mirroring router in `routes/*_fastapi.py` if you want it available via the FastAPI front.
- Global state: `encounter_state` (in `backend/encounter_memory.py`) and other in-memory stores are used heavily — prefer returning pure data from `backend/*` helpers and keep mutation centralized in `encounter_memory` to avoid inconsistent state.
- Logging: `backend/logging_config.py` configures handlers/formatters. Do not assume default logger behavior; new handlers should respect the `request_id` filter.

6) Integration points & external deps
- DB: `DATABASE_URL` (default `sqlite:///local.db`; production typically uses Postgres — `psycopg2-binary` is in `requirements.txt`).
- OpenAPI: `flask-smorest` produces OpenAPI spec and serves docs (configured under `/api/docs` in `backend/app.py`).
- Deployment: `gunicorn` serves the Flask app as `application` (see `Procfile`). FastAPI uvicorn is used for dev convenience.

7) Tests & dev tools
- `requirements.txt` includes `pytest`, but there are no authoritative test folders discovered. Run `pytest` after adding tests. Use `yamllint`/`ruff` locally as desired.

8) Quick examples to reference
- Add a new combat endpoint: modify `routes/combat.py` (blueprint `combat_blp`) and register it; the domain function should live in `backend/roll_logic.py` or `backend/combat_utils.py`.
- Inspect auth behavior: check `backend/app.py` before_request — endpoints under `/api/` require `X-API-Key` (except docs/openapi).
- Schema files: `schemas/core_ruleset.json` and `routes/schemas/blp.py` are good examples of schema → marshmallow → blueprint wiring.

9) When editing code — checklist for PRs
- Update or add JSON schema(s) in `schemas/` if changing API contracts.
- Update corresponding marshmallow schemas in `routes/schemas/` and blueprint docs in `backend/app.py`.
- Make state changes through `backend/encounter_memory.py` helpers rather than mutating globals directly.
- Preserve `request_id` usage when adding logs or middleware.

If anything above is unclear or you want more examples (specific route, schema, or a small runnable example), tell me which area to expand and I will iterate.
