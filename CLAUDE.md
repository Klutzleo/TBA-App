# CLAUDE.md — TBA-App

Guidance for working in this repo. TBA-App is the **live** web platform for the TBA
TTRPG system (Tools for the Bad Ass / Tools for Being Awesome). It runs in
production on Railway at **tba-rpg.com** and is actively being played and
playtested — treat `main` as production. The rules documents (`Rulebook.md`,
`LevelingTable.md`) are **v3.1.1** and the app implements them (the v3.1 phases shipped in Nov 2026:
see `docs/rules-v3.1-app-plan.md` and `PROJECT_STATUS.md`). When code and the Rulebook disagree, the
Rulebook is right and the code is the gap. All rules numbers live in `schemas/leveling_v3_1.json`,
read through `backend/leveling.py`; never hand-type a copy in the backend.

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
  (~3.4k — character/NPC/Ally CRUD), `campaigns.py`.
- Unregistered / legacy (kept as files, not mounted — see `backend/app.py` comments):
  `routes/chat.py` (`chat_blp`; still exports `broadcast_combat_event`), the
  `party_router` in `character_fastapi.py`, `routes/effects.py`, and the
  `/api/combat/*-by-id` routes. `routes/roll_blp_fastapi.py` is also commented out.
- `routes/schemas.py` — Pydantic models (flat file; also `routes/schemas/campaign.py`).
- `backend/migrations/*.sql` — production migrations, applied by `run_migrations.py`
  (tracks applied files in `schema_migrations`, advisory-locked, idempotent-ish).
  `backend/migrations/OLD_MIGRATIONS/` and root `migrations/` are historical — don't run them.
- `schemas/` (repo root) — JSON rule definitions for the ruleset loader (`schemas/loader.py` → `CORE_RULESET`).
- `tests/` — 600 pytest tests (rules, Combos, vehicles, security hardening, signup guard, email, copy, membership, whispers, reports, suspension, admin messaging, security events, status). Run them all before any push.
- Vehicles: `backend/vehicles.py` (stations, systems, crew adds, knock-outs) and `routes/vehicles.py`; a vehicle is a `Character`
  row with `is_npc` + `is_vehicle`, kept out of NPC lists. Plan and decisions: `docs/vehicles-plan.md`.
- **Admin center** (all live; plan and decisions in `docs/admin-center-plan.md`). Screen: `static/admin.html` (tabs: player reports, bug reports, closed, message, security, status, audit log), reached by an Admin link in the page header that only the admin sees. Backend: `routes/reports.py` (player and bug reports, inbox, audit log, suspend and unsuspend), `routes/admin_messages.py` (bell, push, email to a player or campaign; templates), `routes/admin_security.py` and `backend/security_events.py` (blocked signups, failed logins, rate limits, unhandled server errors), `routes/admin_status.py` (version, database, backup and uptime checks read from GitHub Actions, campaign health), `routes/moderation.py` (`require_admin`, banner reports), `backend/membership.py` (leave and removal notifications), `backend/whispers.py` (private whispers), `backend/backup_watchdog.py` (hourly in-app check that starts the nightly backup and monthly restore drill through GitHub's `workflow_dispatch` API, because GitHub's own scheduler skips runs on this repo; needs `GITHUB_DISPATCH_TOKEN` in Railway). Rules to keep: the reporter is never shown to the reported player; private conversations are opened only from inside a report and every opening is audit-logged first; no raw IPs, emails or database error text in the security log; nothing secret in any admin response.

## Domain model quick reference

- **Character** table holds PCs, NPCs, Allies, and Summons — distinguished by
  `is_npc` / `is_ally` / `is_summon` / `parent_character_id`.
- **Party** = a *channel* within a campaign (`story`, `ooc`, `whisper`,
  `split_group`, `spectator`), not a group of players. `CampaignMembership` is the
  user↔campaign link; `PartyMembership` is character↔channel.
- **Campaign** has one `story_weaver_id` (the GM). SW-gated actions use
  `require_story_weaver()` / `require_campaign_access()` from `backend/auth/jwt.py`.
- Core rules: stats PP/IP/SP each 1–3, sum = 6. Levels 1–15 (Ascension 11–15 is live; Allies and
  vehicles stop at 10). DP is 8 +2/level and uses are level + 2 as one shared pool for every
  spell, technique and vehicle system.
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
  or public lists. New feature routes must be JWT (`Authorization: Bearer`) + an
  object-level check (`_is_sw` / `_is_campaign_member` in `character_fastapi.py`) — the
  shared static `X-API-Key` is legacy and should not gate anything new.
- The middleware does **not** run on WebSocket connections — WS routes authenticate
  in-handler (`campaign_websocket.py` decodes the JWT + checks `CampaignMembership`).
- Public/exempt: `/health`, `/docs`, `/openapi.json`, `/`, `/redoc`, `/api/public/*`,
  the auth endpoints.
- **Admin** is `ADMIN_USER_IDS` in Railway: a comma-separated list of user **UUIDs**, never usernames (a username once sat there and no admin page worked; a username is also unsafe to trust because a deleted account's name can be re-registered). Every admin endpoint uses `require_admin`. Production's database has only an internal Railway address, so prod reads go through a deployed endpoint (the Status tab) or the Railway CLI, not a direct connection from the dev PC.
- **Global membership filter:** every SELECT on `CampaignMembership` ignores people who left (`left_at` set), through one listener at the bottom of `backend/models.py`. Opt out with `.execution_options(include_left_members=True)`, used only where the websocket checks for a stale membership.
- CORS is currently wide open (`allow_origins=["*"]` with credentials).
- **Signup protection** (`backend/signup_guard.py`): a hidden honeypot field, a throwaway-email-domain block, and Cloudflare Turnstile,
  which is ON in production (it enforces only when BOTH `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY` are set in Railway; the page asks
  `/api/public/signup-config`). Plus 10 signups per hour per IP.
- **Email verification** (`backend/email_verification.py`, token and email in `backend/email_service.py`, page `static/verify-email.html`, banner in `static/js/auth-helper.js`): new accounts are emailed a link that opens a page with a Confirm button (a button, because mail scanners open links). Nothing is blocked by default. `REQUIRE_VERIFIED_EMAIL=1` in Railway makes creating or joining a campaign require a confirmed address; accounts that existed before migration 046 are `email_verification_exempt` (never asked, never blocked, and NOT recorded as verified). The token uses its own derived key, a purpose claim, a 3-day expiry and the address it was issued for.
- **Email** is sent from `no-reply@tba-rpg.com` (`FROM_EMAIL`; the From domain must match the link domain, which is what fixed the spam-folder problem).
  Links use `FRONTEND_URL` (set to `https://tba-rpg.com` in Railway; the code default is the same). The Resend API key is scoped by domain: a new sending domain needs a new key first. Never let them fall back to a
  `*.railway.app` address: it is a spam signal. Every email also carries a plain-text part; `REPLY_TO_EMAIL` optionally sets Reply-To.

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

Before shipping a dependency upgrade (FastAPI, Starlette, uvicorn, Pillow...), also run `scripts/smoke_server.py` against a migrated
local Postgres (see its docstring): pytest mostly calls handlers directly, so it does not exercise the web stack. Never point it at prod.

> `jsonschema` is a real runtime dep (`schemas/loader.py`, `routes/schemas/validation.py`) —
> it's in `requirements.txt`. If you hit `ModuleNotFoundError` for something a router
> needs, add it there; the Docker build installs *only* what `requirements.txt` lists.

## Conventions

- New endpoints: FastAPI `APIRouter`, `async def` handlers, register in `backend/app.py`
  inside a `try/except` block (matches existing pattern — a broken router logs a
  warning instead of killing startup).
- Request/response validation via Pydantic in `routes/schemas.py`.
- DB migrations that must hit production: add a numbered `NNN_*.sql` to
  `backend/migrations/` (plain SQL, safe to re-run). It applies on next deploy; the latest is 045. `start.sh` runs them before the server starts and stops the deploy if one fails, so a bad migration leaves the old version serving.
- Testing a new route: the app mounts static files at `/` last, so a route added to the app after import never matches in a test. Insert it at `application.router.routes[0]`. Tests share one SQLite file per module, so clear the tables you assert on at the start of each test.
- Preserve `request.state.request_id` in log lines.
- Since prod is live and played daily: prefer additive, backward-compatible DB
  changes; call out anything that needs a migration + code deploy in lockstep.

## Project status (read first, update last)

`PROJECT_STATUS.md` is how Jason and Claude stay in sync across sessions. A morning job reads it across all his repos. It has drifted behind the code before, so verify against the code and `git log` before trusting its task list.

- **Before starting work:** read `PROJECT_STATUS.md`. If it looks older than the recent git history, say so and fix it.
- **Before finishing a session:** update `PROJECT_STATUS.md`:
  - `Last session` — date, what changed, where you stopped.
  - `Resume here` — the first file for the next session.
  - `waiting_on` — `jason`, `claude`, `external` or `none`. If a decision is Jason's, put the question in `decision` and what you will do on a yes in `if_go`.
  - `focus`, `next_milestone`, `momentum` if they changed.
- Only write what you verified from the code, git history or a test. Say plainly what was not run.
- Do not change `excitement` or `priority`; those are Jason's.
- Anything a later session needs (plans, decisions, design notes) goes in the repo, for example `docs/plans/`, not only in a local folder or local memory file. Cloud and scheduled sessions cannot read files on Jason's PC.
- Near-term work lives in the status file's `Next up`; this file no longer duplicates it.
