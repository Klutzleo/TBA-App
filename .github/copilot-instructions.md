<!-- Copilot instructions for TBA-App -->
# Copilot Instructions — TBA-App

Short, focused guidance so an AI coding agent can be productive immediately.

1) Big picture
- **Single FastAPI runtime:** `backend/app.py` (FastAPI + uvicorn) is the canonical API server and entrypoint used by the `Procfile` (`uvicorn backend.app:application --host 0.0.0.0 --port 8000`). FastAPI is chosen for native async/await support, built-in WebSocket capability, and better concurrency handling — essential for a multiplayer online TTRPG with real-time chat and simultaneous player actions.
- The top-level `app.py` (FastAPI) is used for dev convenience (hot-reload) and can serve the template-based UI if needed.
- Core domain logic lives in `backend/` (e.g., `combat_utils.py`, `effect_engine.py`, `magic_logic.py`, `roll_logic.py`, `encounter_memory.py`). Routes glue HTTP endpoints to backend logic in `routes/`.
- **TBA RPG v1.5 System:** Multiplayer tabletop RPG with 3 core stats (Intellect, Physical, Social), die-vs-die contested rolls, spells/techniques, multiplayer parties, real-time WebSocket chat, and social integrations (Discord/Twitch spectating + emote reactions).

2) Where to look first
- `backend/app.py` — FastAPI API server configuration, router registration, request middleware (request id assignment, API key enforcement), OpenAPI setup, WebSocket handlers.
- `app.py` (project root) — Dev entry point; imports `backend/app.py` for hot-reload testing.
- `routes/` — HTTP/WebSocket endpoints. Use FastAPI routers (e.g., `routes/chat.py`, `routes/combat_fastapi.py`, `routes/social_integrations.py`).
- `routes/schemas/` — Pydantic models (preferred). Use Pydantic for FastAPI validation.
- `backend/db.py` — SQLAlchemy engine, `DATABASE_URL` default (`sqlite:///local.db`). Production expects Postgres via env `DATABASE_URL`.
- `backend/integrations/` — Discord bot, Twitch API client, emote reaction handlers (see section 3c below).

3) Important runtime & env patterns

**3a) API Key & Auth:**
- API key: `backend/app.py` middleware enforces `X-API-Key` header against `API_KEY` env var for `/api/` routes (docs/openapi endpoints are exempt).
- Request correlation: `backend/app.py` attaches a `request_id` to each incoming request. Preserve in logs via `request.state.request_id`.

**3b) Database & State:**
- DB init: call `init_db()` (from `backend/db.py`) on startup. `backend/app.py` calls it — keep that ordering.
- Stateful memory: `backend/encounter_memory.py` uses in-memory globals for current encounter state.
- Use `--workers 1` or migrate to persistent DB for multi-worker deployments.

**3c) WebSocket & Social Integrations:**
- **WebSocket parties:** Real-time multiplayer chat + combat. See `routes/chat.py` for examples.
- **Discord bot:** Listens for campaign events via webhook from FastAPI. Posts roll outcomes, initiative, DP changes to Discord channel. Handles Discord emote reactions (e.g., 👍, 🔥) → forwards to in-game spectator system.
  - Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID`
  - Endpoint: `POST /api/integrations/discord/webhook` receives campaign events
- **Twitch integration:** Streams campaign via Twitch Chat or EventSub API. Spectators react with emotes; forwarded to FastAPI WebSocket.
  - Env vars: `TWITCH_CLIENT_ID`, `TWITCH_ACCESS_TOKEN`, `TWITCH_CHANNEL_ID`
  - Endpoint: `GET /api/integrations/twitch/subscribe` (setup EventSub subscription)
- **Spectator reactions:** Discord/Twitch emotes mapped to in-game reactions (e.g., 🔥 = "epic moment", 👍 = "approve"). Aggregated and broadcast to all players/party.

4) How to run locally (PowerShell examples)
- Run FastAPI backend (prod-like with uvicorn):
```powershell
$env:API_KEY = 'devkey'
$env:DISCORD_BOT_TOKEN = 'your-discord-token'
$env:TWITCH_CLIENT_ID = 'your-twitch-client-id'
$env:TWITCH_ACCESS_TOKEN = 'your-twitch-token'
uvicorn backend.app:application --host 0.0.0.0 --port 8000
```
- Run FastAPI backend (dev with hot-reload):
```powershell
$env:API_KEY = 'devkey'
python app.py
```
- Notes: `Procfile` uses `uvicorn backend.app:application --host 0.0.0.0 --port 8000`. FastAPI enables async handlers, WebSocket, and Discord/Twitch integrations.

5) Common codebase conventions & gotchas
- Pydantic models drive all request/response schemas. Update `routes/schemas/` when changing API contracts.
- When adding public endpoints, register the router in `backend/app.py` via `application.include_router()`.
- Global state: `encounter_state` (in `backend/encounter_memory.py`) is intentionally stateful. Keep mutations centralized.
- Logging: Preserve `request.state.request_id` in all logs.
- WebSocket handlers: Use `@router.websocket()` decorator. Broadcast to all connected clients + Discord/Twitch spectators.
- **Discord/Twitch spectators:** Treat as read-only observers. Forward emote reactions to WebSocket broadcast but do NOT let them affect rolls/combat directly.

6) Integration points & external deps
- DB: `DATABASE_URL` (default `sqlite:///local.db`; production = Postgres).
- OpenAPI: FastAPI auto-generates at `/docs` and `/openapi.json`.
- **Discord.py:** `discord.py` library for bot. Listens for emote reactions on campaign posts. Posts roll outcomes to Discord channel.
- **Twitch API:** `python-twitch-client` or direct HTTP calls to EventSub for real-time events. Parse chat messages for emote reactions.
- Deployment: Direct `uvicorn` serve (see `Procfile`). Use `--workers 1` for in-memory state.

7) Tests & dev tools
- `requirements.txt` includes `pytest`. Run `pytest` after adding tests.

8) Quick examples to reference
- **Discord live feed:** Create `backend/integrations/discord_bot.py` with bot that listens to FastAPI webhook events. Post rolls/outcomes to Discord channel. Handle reaction_add events.
- **Twitch spectators:** Create `backend/integrations/twitch_client.py` to subscribe to Twitch EventSub. Parse chat for emotes (e.g., `KappaHD`, `VoHiYo`) → convert to reaction → broadcast.
- **Emote mapping:** Define in `backend/integrations/reactions.py` (e.g., `{ "fire": ["🔥", "KappaHD"], "epic": ["😱", "VoHiYo"] }`). Forward to WebSocket as `{ "emote": "fire", "count": 5, "source": "discord" }`.
- **Spectator broadcast:** When roll outcome posted, broadcast to all connected WebSocket clients + emit Discord message + Twitch chat message.

9) File Organization (Social Integration additions)
- `backend/integrations/discord_bot.py` — Discord bot listener, event handlers, post-to-channel logic
- `backend/integrations/twitch_client.py` — Twitch EventSub subscription, chat parsing, emote handling
- `backend/integrations/reactions.py` — Emote-to-reaction mapping, aggregation logic
- `routes/social_integrations.py` — Webhook endpoints for Discord/Twitch events, emote broadcast
- `routes/schemas/integrations.py` — Pydantic models (DiscordEvent, TwitchEvent, EmoteReaction, SpectatorReaction)

10) When editing code — checklist for PRs
- Update or add Pydantic schemas in `routes/schemas/` if changing API contracts.
- Update router registration in `backend/app.py` if adding new endpoints.
- Preserve `request.state.request_id` usage in all logs.
- Use async/await for all route handlers.
- **For Discord/Twitch:** Validate webhook signatures (Discord: X-Signature-Ed25519; Twitch: HMAC-SHA256) before processing events.
- Forward emote reactions to WebSocket + in-game spectator system, do NOT mutate game state from spectator actions.
- Test multiplayer scenarios with Discord/Twitch spectators (concurrent broadcasts, emote aggregation, rate limiting).

If anything above is unclear or you want more examples, tell me which area to expand and I will iterate.
