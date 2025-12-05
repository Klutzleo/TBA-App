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
- `backend/roll_logic.py` — TBA v1.5 dice utilities:
  - `resolve_multi_die_attack()` — Multi-die attack resolution (Phase 1 MVP ✅)
  - `roll_die()` / `roll_dice()` — Individual die rolling
  - `resolve_combat_roll()` — Legacy single-die rolls (backward compatibility)
  - `roll_initiative()` — Initiative rolling with stat tiebreakers
  - `simulate_encounter()` — Full multi-round battle simulation

## TBA v1.5 Combat System (Multi-Die Attack Resolution)

### Character Stats (Fixed Distribution)
- **PP (Physical Power):** 1-3 (chosen at character creation)
- **IP (Intellect Power):** 1-3 (chosen at character creation)
- **SP (Social Power):** 1-3 (chosen at character creation)
- **Total always = 6** (no reuse, no changes after creation)

### Level-Based Stats (Fixed by Level, from leveling table)
- **DP (Damage Points):** 10-55 (scales with level: 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)
- **Edge:** 0-5 (adds to attack rolls, initiative, and combat totals; scales every 2 levels)
- **BAP (Bonus Action Points):** 1-5 (adds to rolls when triggered; scales every 2 levels)
- **Max Weapon Die (WD):** Level determines available options
  - Level 1-2: `1d4`
  - Level 3-4: `2d4` OR `1d6`
  - Level 5-6: `3d4` OR `2d6` OR `1d8`
  - Level 7-8: `4d4` OR `3d6` OR `2d8` OR `1d10`
  - Level 9-10: `5d4` OR `4d6` OR `3d8` OR `2d10` OR `1d12`
- **Max Defense Die (DD):** Fixed per level
  - Levels 1-2: `1d4` | Levels 3-4: `1d6` | Levels 5-6: `1d8` | Levels 7-8: `1d10` | Levels 9-10: `1d12`

### Attack Style (Player Choice at Character Creation)
- Player chooses **one attack style** from level's max weapon die options (e.g., `3d4`, `2d6`, or `1d8` for Level 5)
- Represents character's preferred combat approach
- Risk/reward trade-off: more dice = more rolls but lower per-die ceiling; fewer dice = higher potential damage per die but lower consistency

### Multi-Die Combat Resolution (TBA v1.5 Core)
**Attacker rolls their chosen attack die SEPARATELY against defender's single defense die:**

Each individual attacker die rolls independently vs the same defense die:

```
Example: Attacker chooses 3d4 | Defender has 1d8

Roll 1: 1d4 (rolled 2) vs 1d8 (rolled 7) → margin = 2 - 7 = -5 → 0 damage
Roll 2: 1d4 (rolled 4) vs 1d8 (rolled 2) → margin = 4 - 2 = +2 → 2 damage
Roll 3: 1d4 (rolled 4) vs 1d8 (rolled 1) → margin = 4 - 1 = +3 → 3 damage

Total Damage = 0 + 2 + 3 = 5 damage
```

**Damage Calculation (per individual die):**
- `margin = attacker_die_roll - defense_die_roll`
- If `margin > 0` → damage = margin
- If `margin ≤ 0` → damage = 0 (no negative damage)
- Sum all individual damages from all attacker die rolls

**Attack Total Calculation:**
- `attack_total = (chosen attack die) + stat_value + edge + (bap if triggered) + (weapon bonus if applicable)`
- BUT: Each die is compared individually against defense die (not totals added first)

### Technique/Spell System
- **Base Attacks (PP-based):** Use PP stat + weapon die (e.g., "Slash")
- **Spells/Techniques (flexible stat):** Can use PP, IP, or SP depending on technique flavor
  - Example: `Fireball` (IP-based) = IP + spell die (from leveling table)
  - Example: `Persuade` (SP-based) = SP + social die
  - Example: `Slash` (PP-based) = PP + weapon die
- Spell die depends on character level and spell slot (First Spell, Second Spell, etc.)

### Weapon/Armor System (Stubbed for Phase 2)
- Character data structure includes `weapon` and `armor` objects (currently null)
- Schema: `{ "name": str, "bonus_attack": int, "bonus_defense": int, "bonus_dp": int }`
- Phase 1: Validate and store in character schema (don't apply bonuses)
- Phase 2: Storyweaver grants items → bonuses applied to damage/defense calcs

### Backend Implementation (`backend/roll_logic.py`)
**NEW function required:**
- `resolve_multi_die_attack(attacker, attacker_die_str, attacker_stat, attacker_stat_value, defender, defense_die_str, defender_stat, defender_stat_value, edge, bap_triggered=False, weapon_bonus=0)`
  - Parse `attacker_die_str` (e.g., "3d4") into individual rolls
  - Roll each attacker die separately
  - For each attacker die roll against defense die: calculate margin, damage per roll
  - Sum total damage across all rolls
  - Return: list of individual roll results + total damage + narrative + outcome

**Keep existing functions:**
- `resolve_combat_roll()` for backward compatibility (single die vs single die)
- `roll_initiative()` with tiebreakers (1d6 + Edge, then PP → IP → SP)
- `simulate_encounter()` for multi-actor battles

### API Endpoints (Phase 1 MVP)
- `POST /api/combat/attack` → calls `resolve_multi_die_attack()`
  - Request: `{ attacker, defender, attack_style_die, technique_name, stat_type }`
  - Response: `{ individual_rolls, total_damage, narrative, defender_new_dp }`
- `POST /api/combat/roll-initiative` → rolls initiative for multiple combatants
- `POST /api/combat/encounter-1v1` → full battle simulation (multi-round)
- Legacy endpoints: `/log`, `/replay`, `/echoes` (combat history)

### Testing Guidelines (Phase 1 MVP)
- Character stats: PP/IP/SP 1-3 each, total = 6
- DP: use level table (e.g., Level 5 = 30 DP)
- Attack rolls: verify margin calculation **per individual die** (not totals)
- Damage: sum positive margins only (negative/zero margins = 0 damage)
- Initiative: 1d6 + Edge, tiebreak by PP → IP → SP
- WebSocket: test multiplayer broadcast with concurrent clients
- Armor/Weapons: accept in schema, store, but don't apply bonuses yet

## Phase 1 MVP Implementation Status (✅ Complete)

### Completed
- ✅ `backend/roll_logic.py` — `resolve_multi_die_attack()` function
- ✅ `routes/schemas/combat.py` — Pydantic models (Character, Attack, Initiative, Encounter1v1)
- ✅ `routes/combat_fastapi.py` — HTTP endpoints (attack, initiative, encounter-1v1)
- ✅ `backend/app.py` — Router registration with error handling
- ✅ Logging — Request ID preservation across all combat endpoints
- ✅ Async/await — All handlers support concurrent multiplayer requests

### Testing
- Run: `pytest tests/test_combat.py` (coming next)
- Manual: POST requests via `/docs` (FastAPI Swagger UI)

### Next Phase (Phase 2)
- Weapon/Armor bonus application
- WebSocket broadcast for multiplayer combat events
- Discord/Twitch spectator reactions
- Persistent combat log storage (DB)

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
- Router naming: Use `router = APIRouter(...)` for consistency in `backend/app.py` registration
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
