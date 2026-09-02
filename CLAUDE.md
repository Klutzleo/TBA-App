# CLAUDE.md — TBA-App

Guidance for working in this repo. TBA-App is the **live** web platform for the TBA
TTRPG system (Tools for the Bad Ass / Tools for Being Awesome). It runs in
production on Railway at **tba-rpg.com** and is actively being played and
playtested — treat `main` as production. Rules are at **v3.0**.

## Architecture

- **FastAPI + Uvicorn**, single process / single worker. Some state
  (encounter memory, WebSocket connection managers, pending AOE/combo maps) lives
  in in-process globals, so **do not** move to multi-worker without moving that
  state to the DB.
- **SQLAlchemy 2.0 ORM.** Postgres in production, SQLite (`local.db`) for local dev.
- **Auth:** Argon2 password hashing + JWT (HS256, 7-day tokens) via
  `backend/auth/jwt.py`. `SECRET_KEY` env var signs tokens.
- **Frontend:** plain HTML/CSS/JS in `static/`, no build step. `static/game.html`
  (~14k lines) is the main play surface. PWA (`manifest.json` + `sw.js`), Lucide
  icons, Umami analytics.

### Entry points

| File | Role |
|---|---|
| `backend/app.py` | Canonical app. Defines `application`, registers all routers, middleware (request ID + API key), lifespan (`init_db`, discord mirror workers), health checks, static mount at `/`. |
| `app.py` (root) | Thin dev wrapper — imports `backend.app` for `uvicorn --reload`. |
| `main.py` | Vestigial schema-loader script. Not part of the server. |
| `Dockerfile` | **The production build.** Railway builds this (`python:3.11-slim` base), not Nixpacks — the `railway.toml` `builder = "NIXPACKS"` line is not in effect. Every build is `pip install --no-cache-dir -r requirements.txt`, so `requirements.txt` is the complete, authoritative dependency list (nothing survives from a previous build). |
| `start.sh` | **The production start command**, set by `railway.toml`'s `startCommand = "bash start.sh"`, which overrides the Dockerfile `CMD`. Runs `run_migrations.py`, then `uvicorn backend.app:application --port $PORT` (8080 in prod). |
| `app.py` (root) | Thin dev wrapper — imports `backend.app` for `uvicorn --reload`. |
| `main.py` | Vestigial schema-loader script. Not part of the server. |

Dead weight in the Docker path: `scripts/docker-entrypoint.sh` (the Dockerfile `CMD`, but overridden by `startCommand` so never runs), the Dockerfile's `RUN pip install flasgger` (Flask swagger lib, unused by the FastAPI app), and its Flask-oriented `EXPOSE 8080` / `HEALTHCHECK`. `Procfile` is also unused (Railway uses `startCommand`, not Procfile). `runtime.txt` (python-3.10.8) is **not honored** — the Docker base image pins Python 3.11.

### Layout

- `backend/` — domain logic: `roll_logic.py` (dice, multi-die attack, initiative),
  `magic_logic.py`, `effect_engine.py`, `achievements.py` (153 achievements),
  `stats_tracker.py` (user/character/campaign/site stat rollups),
  `mention_parser.py`, `notification_center.py` / `notifications.py`,
  `discord_mirror.py` (live campaign→Discord mirror), `encounter_memory.py` (in-memory state).
- `backend/models.py` — **all** SQLAlchemy models in one file (~1140 lines).
- `routes/` — FastAPI `APIRouter`s. Biggest: `campaign_websocket.py` (~4.3k — the
  real-time hub: chat, combat, dice, initiative, Bonds/Combos), `character_fastapi.py`
  (~3.4k — character/NPC/Ally/party CRUD), `chat.py`, `campaigns.py`.
- `routes/schemas.py` — Pydantic models (flat file; also `routes/schemas/campaign.py`).
- `backend/migrations/*.sql` — production migrations, applied by `run_migrations.py`
  (tracks applied files in `schema_migrations`, advisory-locked, idempotent-ish).
  `backend/migrations/OLD_MIGRATIONS/` and root `migrations/` are historical — don't run them.
- `schemas/` (repo root) — JSON rule definitions for the ruleset loader (`schemas/loader.py` → `CORE_RULESET`).
- `tests/` — thin: `test_api.py`, `test_characters.py` only.

## Domain model quick reference

- **Character** table holds PCs, NPCs, Allies, and Summons — distinguished by
  `is_npc` / `is_ally` / `is_summon` / `parent_character_id`.
- **Party** = a *channel* within a campaign (`story`, `ooc`, `whisper`,
  `split_group`, `spectator`), not a group of players. `CampaignMembership` is the
  user↔campaign link; `PartyMembership` is character↔channel.
- **Campaign** has one `story_weaver_id` (the GM). SW-gated actions use
  `require_story_weaver()` / `require_campaign_access()` from `backend/auth/jwt.py`.
- Core rules: stats PP/IP/SP each 1–3, sum = 6. Levels 1–10 (app cap is 10).
  Multi-die attack = each attacker die rolls independently vs the defender's single
  defense die; per-die `damage = max(0, attacker_roll − defense_roll)`, summed.
  See `LevelingTable.md` / `Rulebook.md` for DP/Edge/BAP/die progressions.
- Systems in play: Edge, BAP, Tethers/Boosts, Bonds→Combos, Stat Checks
  (hidden difficulty), The Calling (death spiral at −10 DP) + battle scars,
  Initiative/Encounters, achievements, public `/u/{username}` profiles,
  notification center + web push, Discord mirror.

## Auth / request flow

- Middleware in `backend/app.py` attaches `request.state.request_id` (echo it in logs)
  and enforces `X-API-Key` **only** for `/api/*` routes that aren't in the JWT-protected
  or public lists. Most feature routes are JWT (`Authorization: Bearer`), not API key.
- Public/exempt: `/health`, `/docs`, `/openapi.json`, `/`, `/redoc`, `/api/public/*`,
  the auth endpoints.
- CORS is currently wide open (`allow_origins=["*"]` with credentials).

## Running locally (PowerShell)

```powershell
# one-time: copy env, install deps
Copy-Item .env.example .env
pip install -r requirements.txt

# run (SQLite, hot reload)
python app.py            # http://localhost:8000  — Swagger at /docs
```

Tests: `pytest tests/ -v`. Prod runs Python 3.11 (Docker base image); `runtime.txt`
says 3.10 but is ignored. Local 3.11 matches prod.

> `jsonschema` is a real runtime dep (`schemas/loader.py`, `routes/schemas/validation.py`) —
> it's in `requirements.txt`. If you hit `ModuleNotFoundError` for something a router
> needs, add it there; the Docker build installs *only* what `requirements.txt` lists.

## Conventions

- New endpoints: FastAPI `APIRouter`, `async def` handlers, register in `backend/app.py`
  inside a `try/except` block (matches existing pattern — a broken router logs a
  warning instead of killing startup).
- Request/response validation via Pydantic in `routes/schemas.py`.
- DB migrations that must hit production: add a numbered `NNN_*.sql` to
  `backend/migrations/` (plain SQL, safe to re-run). It applies on next deploy.
- Preserve `request.state.request_id` in log lines.
- Since prod is live and played daily: prefer additive, backward-compatible DB
  changes; call out anything that needs a migration + code deploy in lockstep.

## Current focus

Post-launch polish. Near-term per `PROJECT_STATUS.md`: Combo cancellation +
Triple Combo in `campaign_websocket.py`, then Ascension levels 11–15.

`PROJECT_STATUS.md` runs a bit behind the code — e.g. it lists the grief-tether
weight fix as pending, but `routes/bonds.py` `break_bond` already takes an
SW-selected `weight` (clamped −5..−1). Verify against the code before trusting
its task list.
