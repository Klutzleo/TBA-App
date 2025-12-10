<!-- Copilot instructions for TBA-App -->
# Copilot Instructions — TBA-App

Short, focused guidance so an AI coding agent can be productive immediately.

## 1) Big Picture

- **Single FastAPI runtime:** `backend/app.py` (FastAPI + uvicorn) is the canonical API server and entrypoint used by the `Procfile`: 
  ```
  web: uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
  ```
  FastAPI chosen for native async/await support, built-in WebSocket capability, and better concurrency handling — essential for a multiplayer online TTRPG with real-time chat and simultaneous player actions.

- **Dev entrypoint:** `app.py` (project root) imports `backend/app.py` for local hot-reload testing.

- **Core domain logic** lives in `backend/`:
  - `roll_logic.py` — Dice utilities (multi-die attack, initiative, encounter simulation)
  - `combat_utils.py` — ⚠️ **DEPRECATED** (removed; use `roll_logic.py` instead)
  - `effect_engine.py` — Status effects, damage over time
  - `magic_logic.py` — Spell/technique resolution
  - `encounter_memory.py` — In-memory encounter state (stateful globals)
  - `db.py` — SQLAlchemy engine, database initialization
  - `integrations/` — Discord bot, Twitch API client, emote reactions

- **Routes glue HTTP endpoints to backend logic:**
  - `routes/chat.py` — WebSocket chat, party management
  - `routes/combat_fastapi.py` — Combat resolution endpoints
  - `routes/character_fastapi.py` — Character CRUD
  - `routes/effects.py` — Status effect endpoints
  - `routes/social_integrations.py` — Discord/Twitch webhooks (coming in Phase 2)

- **TBA RPG v1.5 System:** Multiplayer tabletop RPG with:
  - 3 core stats (PP, IP, SP): 1-3 each, total always = 6
  - Level-based progression (DP, Edge, BAP)
  - Multi-die attack resolution (attacker rolls multiple dice vs defender's single die)
  - Spells/techniques, weapon/armor system (Phase 2)
  - Real-time WebSocket chat, Discord/Twitch spectating

---

## 2) Where to Look First

| File | Purpose |
|------|---------|
| `backend/app.py` | FastAPI server config, router registration, middleware (request ID, API key), OpenAPI, WebSocket setup |
| `app.py` (root) | Dev entry point; imports `backend/app.py` for hot-reload |
| `routes/` | HTTP/WebSocket endpoints — use FastAPI `APIRouter` |
| `routes/schemas/` | Pydantic models (preferred for validation) |
| `routes/combat_fastapi.py` | Phase 1 MVP: 7 combat endpoints |
| `routes/chat.py` | WebSocket chat + party management |
| `backend/roll_logic.py` | Core dice logic (`resolve_multi_die_attack()`, `roll_initiative()`, etc.) |
| `backend/db.py` | SQLAlchemy engine, DB init |
| `backend/integrations/` | Discord bot, Twitch client (Phase 2) |
| `Procfile` | Production startup: `uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}` |

---

## 3) TBA v1.5 Combat System (Multi-Die Attack Resolution)

### Character Stats (Fixed Distribution)
- **PP (Physical Power):** 1-3 (chosen at character creation)
- **IP (Intellect Power):** 1-3 (chosen at character creation)
- **SP (Social Power):** 1-3 (chosen at character creation)
- **Total always = 6** (no reuse, no changes after creation)

### Level-Based Stats (Fixed by Level)
- **DP (Damage Points):** 10, 15, 20, 25, 30, 35, 40, 45, 50, 55 (by level 1-10)
- **Edge:** 0-5 (adds to attack rolls, initiative; scales every 2 levels)
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
- Risk/reward: more dice = more rolls but lower per-die ceiling; fewer dice = higher potential per-die but lower consistency

### Multi-Die Combat Resolution (Phase 1 MVP ✅)

**Each attacker die rolls INDEPENDENTLY against defender's single defense die:**

```
Example: Attacker chooses 3d4 | Defender has 1d8

Roll 1: 1d4 (rolled 2) vs 1d8 (rolled 7) → margin = 2 - 7 = -5 → 0 damage
Roll 2: 1d4 (rolled 4) vs 1d8 (rolled 2) → margin = 4 - 2 = +2 → 2 damage
Roll 3: 1d4 (rolled 4) vs 1d8 (rolled 1) → margin = 4 - 1 = +3 → 3 damage

Total Damage = 0 + 2 + 3 = 5 damage
Outcome = "partial_hit" (1-2 of 3 succeed)
```

**Damage Calculation (per individual die):**
- `margin = attacker_die_roll - defense_die_roll`
- If `margin > 0` → damage = margin
- If `margin ≤ 0` → damage = 0 (no negative damage)
- Sum all individual damages

**Attack Total for Roll (informational, not used for damage):**
- `attack_total = (chosen attack die) + stat_value + edge + (bap if triggered) + (weapon bonus if applicable)`
- Individual die comparisons happen BEFORE totals are added

### Technique/Spell System
- **Base Attacks (PP-based):** Use PP stat + weapon die (e.g., "Slash")
- **Spells/Techniques (flexible stat):** Can use PP, IP, or SP depending on technique flavor
  - Example: `Fireball` (IP-based) = IP + spell die
  - Example: `Persuade` (SP-based) = SP + social die
  - Example: `Slash` (PP-based) = PP + weapon die
- Spell die depends on character level and spell slot

### Weapon/Armor System (Phase 2)
- Character data structure includes `weapon` and `armor` objects (currently null)
- Schema: `{ "name": str, "bonus_attack": int, "bonus_defense": int, "bonus_dp": int }`
- Phase 1: Validate and store in character schema (✅ done)
- Phase 2: Apply bonuses to damage/defense calculations

### Backend Implementation (`backend/roll_logic.py`)

**Core Functions (Phase 1 MVP ✅):**

- `resolve_multi_die_attack(attacker, defender, attacker_die_str, stat_type, stat_value, edge, bap_triggered=False)` ✅
  - Parse `attacker_die_str` (e.g., "3d4") into individual rolls
  - Roll each attacker die separately against defender's single defense die
  - Calculate margin and damage per individual die
  - Return: list of individual roll results + total damage + narrative + outcome
  
- `roll_initiative(combatants: list)` ✅
  - Each combatant: 1d6 + Edge
  - Tiebreaker: PP → IP → SP
  
- `simulate_encounter(attackers, defenders, max_rounds=10)` ✅
  - Multi-round 1v1 or multi-actor battle
  - Returns: round list with actions, outcome

**Keep Existing Functions (Backward Compatibility):**
- `roll_die(num_dice, die_sides)` ✅ — Basic die rolling
- `resolve_combat_roll()` — Legacy single-die rolls (deprecated but kept)

---

## 4) Phase 1 MVP Implementation Status (✅ COMPLETE & VERIFIED)

### ✅ Completed
- `backend/roll_logic.py` — `resolve_multi_die_attack()` function
- `routes/schemas/combat.py` — Pydantic models (AttackRequest, InitiativeRequest, Encounter1v1Request, etc.)
- `routes/combat_fastapi.py` — 7 HTTP/async endpoints:
  - `POST /api/combat/attack`
  - `POST /api/combat/roll-initiative`
  - `POST /api/combat/encounter-1v1`
  - `POST /api/combat/log` — Record combat log entry
  - `GET /api/combat/log/recent` — Retrieve recent logs
  - `POST /api/combat/replay` — Replay combat history
  - `POST /api/combat/echoes` — Query combat echoes
- `backend/app.py` — Router registration with error handling
- `routes/chat.py` — WebSocket chat with party management
- `routes/character_fastapi.py` — Character CRUD endpoints
- `routes/effects.py` — Status effect endpoints
- Logging — Request ID preservation across all endpoints
- Async/await — All handlers support concurrent multiplayer requests
- **Deployment:** Railway fixed (`Procfile` uses `${PORT:-8000}`)

### ✅ Verified Working
- Local testing: `python app.py` → FastAPI server starts at `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs` → All 7 combat endpoints visible
- Railway deployment: `https://tba-app-production.up.railway.app/docs` → Live and accessible
- API Key enforcement: `X-API-Key` header required for `/api/` routes
- WebSocket chat: Tested with concurrent clients
- Health check: `GET /health` (no auth required) and `GET /api/health` (with DB status)

### Testing (Next Steps)
- Run: `pytest tests/test_combat.py` (unit tests for `resolve_multi_die_attack()`)
- Manual: POST requests via `/docs` (FastAPI Swagger UI)
- Load testing: Concurrent attack requests to verify async handling

---

## 5) Next Phase: Phase 2 (WebSocket Multiplayer + Social Integrations)

### Phase 2 Roadmap
- ✅ **Multiplayer WebSocket broadcast:** Combat events (attacks, damage, DP changes) broadcast to all players in a session
- ✅ **Discord spectator integration:** Discord bot listens for campaign events, posts rolls to Discord channel, handles emote reactions
- ✅ **Twitch spectator integration:** EventSub subscription for Twitch chat, parse emotes, forward to in-game spectators
- ✅ **Persistent combat log:** Store combat actions in database (currently in-memory)
- Weapon/Armor bonuses: Apply to damage/defense calculations
- Spell system expansion: Add more spell types and mechanics

### Files to Create/Extend (Phase 2)
```
backend/integrations/
├── discord_bot.py          (Discord bot listener, event handlers)
├── twitch_client.py        (Twitch EventSub, chat parsing)
└── reactions.py            (Emote-to-reaction mapping)

routes/
├── social_integrations.py  (Webhook endpoints for Discord/Twitch)
└── schemas/integrations.py (Pydantic models)
```

---

## 6) Important Runtime & Environment Patterns

### 6a) API Key & Auth
- API key: `backend/app.py` middleware enforces `X-API-Key` header against `API_KEY` env var for `/api/` routes
- Exempt paths: `/health`, `/docs`, `/openapi.json`, `/`, `/redoc` (no auth required)
- Request correlation: `backend/app.py` attaches `request_id` to each request. Preserve in all logs via `request.state.request_id`

### 6b) Database & State
- DB init: Call `init_db()` (from `backend/db.py`) on startup. `backend/app.py` does this in the lifespan context manager.
- Stateful memory: `backend/encounter_memory.py` uses in-memory globals for current encounter state
- **Important:** Use `--workers 1` in production (Procfile does this) or migrate to persistent DB for multi-worker deployments

### 6c) Procfile & Deployment (Railway ✅)
```
web: uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
```
- `${PORT:-8000}` ensures Railway can assign dynamic port (critical for 502 fix)
- `--host 0.0.0.0` binds to all interfaces (required for Railway)
- Single worker (`--workers 1`) default (maintains in-memory state)

### 6d) Environment Variables (Required)
```
API_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/dbname  (production; defaults to sqlite:///local.db)
DISCORD_BOT_TOKEN=your-discord-token  (Phase 2)
DISCORD_GUILD_ID=123456789  (Phase 2)
DISCORD_CHANNEL_ID=987654321  (Phase 2)
TWITCH_CLIENT_ID=your-client-id  (Phase 2)
TWITCH_ACCESS_TOKEN=your-token  (Phase 2)
TWITCH_CHANNEL_ID=your-channel-id  (Phase 2)
```

### 6e) WebSocket & Social Integrations (Phase 2)
- **WebSocket parties:** Real-time multiplayer chat + combat. See `routes/chat.py` for examples
- **Discord bot:** Listens for campaign events via webhook. Posts roll outcomes, initiative, DP changes to Discord channel. Handles Discord emote reactions (👍, 🔥) → forwards to in-game spectator system
- **Twitch integration:** Streams campaign via Twitch EventSub. Spectators react with emotes; forwarded to FastAPI WebSocket

---

## 7) How to Run Locally (PowerShell)

### Development (Hot-Reload)
```powershell
$env:API_KEY = 'devkey'
python app.py
```
- Starts FastAPI at `http://localhost:8000`
- Hot-reload on file changes
- Swagger UI: `http://localhost:8000/docs`

### Production-Like (Single Worker)
```powershell
$env:API_KEY = 'devkey'
uvicorn backend.app:application --host 0.0.0.0 --port 8000 --workers 1
```

### With Discord/Twitch (Phase 2 Testing)
```powershell
$env:API_KEY = 'devkey'
$env:DISCORD_BOT_TOKEN = 'your-token'
$env:TWITCH_CLIENT_ID = 'your-client-id'
$env:TWITCH_ACCESS_TOKEN = 'your-token'
python app.py
```

---

## 8) Common Codebase Conventions & Gotchas

### Do's
- ✅ Use Pydantic models for all request/response schemas (in `routes/schemas/`)
- ✅ Use FastAPI `APIRouter` for all new endpoints
- ✅ Preserve `request.state.request_id` in all logs
- ✅ Use async/await for all route handlers
- ✅ Register routers in `backend/app.py` via `application.include_router()`
- ✅ WebSocket handlers: Use `@router.websocket()` decorator, broadcast to all connected clients

### Don'ts
- ❌ Don't hardcode port numbers (use `${PORT:-8000}` in Procfile)
- ❌ Don't import from `backend.combat_utils` (deprecated; use `backend.roll_logic`)
- ❌ Don't import from `backend.lore_log` (deprecated; use in-memory `combat_log_store`)
- ❌ Don't let Discord/Twitch spectators affect game state directly (read-only observers; forward emote reactions only)

### Gotchas
- **In-memory state:** `encounter_state` (in `backend/encounter_memory.py`) is stateful. Mutations are global; keep them centralized
- **Multi-worker deployments:** In-memory state won't persist across workers. Use `--workers 1` or migrate to persistent DB
- **Async order:** WebSocket handlers are async; ensure all downstream calls support concurrency (use `await`)

---

## 9) Integration Points & External Dependencies

| Dependency | Purpose | Env Var(s) |
|------------|---------|-----------|
| FastAPI | HTTP/WebSocket framework | N/A |
| Uvicorn | ASGI server | N/A |
| SQLAlchemy | ORM + database | `DATABASE_URL` |
| Pydantic | Request validation | N/A |
| Discord.py | Discord bot | `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID` |
| Python-Twitch-Client | Twitch API | `TWITCH_CLIENT_ID`, `TWITCH_ACCESS_TOKEN`, `TWITCH_CHANNEL_ID` |
| Pytest | Testing framework | N/A |

---

## 10) Tests & Dev Tools

- Run tests: `pytest tests/test_combat.py -v`
- Check coverage: `pytest --cov=backend tests/`
- Lint: `flake8 backend/ routes/`

---

## 11) Quick Examples to Reference

### Multi-Die Attack Endpoint
```json
POST /api/combat/attack
{
  "attacker": {
    "name": "Alice",
    "level": 5,
    "stats": {"pp": 3, "ip": 2, "sp": 1},
    "dp": 30,
    "edge": 2,
    "bap": 3,
    "attack_style": "3d4",
    "defense_die": "1d8",
    "session_id": "test-session"
  },
  "defender": {
    "name": "Goblin",
    "level": 2,
    "stats": {"pp": 2, "ip": 1, "sp": 1},
    "dp": 15,
    "edge": 1,
    "bap": 1,
    "attack_style": "1d4",
    "defense_die": "1d4"
  },
  "technique_name": "Slash",
  "stat_type": "PP",
  "bap_triggered": false
}

Response:
{
  "type": "multi_die_attack",
  "attacker_name": "Alice",
  "defender_name": "Goblin",
  "individual_rolls": [
    {"attacker_roll": 2, "defense_roll": 7, "margin": -5, "damage": 0},
    {"attacker_roll": 4, "defense_roll": 2, "margin": 2, "damage": 2},
    {"attacker_roll": 4, "defense_roll": 1, "margin": 3, "damage": 3}
  ],
  "total_damage": 5,
  "outcome": "partial_hit",
  "narrative": "Alice connects with 2/3 strikes on Goblin—5 damage total.",
  "defender_new_dp": 10,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### WebSocket Chat
```powershell
# Connect to WebSocket (example with wscat CLI)
wscat -c ws://localhost:8000/api/chat/party/test-party

# Send message
{ "type": "message", "actor": "Alice", "text": "Attacking!" }

# Receive broadcast
{ "type": "message", "actor": "Alice", "text": "Attacking!", "party_id": "test-party" }
```

---

## 12) File Organization (Current)

```
TBA-App/
├── app.py                          (Dev entrypoint, hot-reload)
├── Procfile                        (Production: uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000})
├── requirements.txt                (Dependencies)
├── .github/copilot-instructions.md (This file)
├── backend/
│   ├── app.py                      (FastAPI server config, router registration, middleware)
│   ├── db.py                       (SQLAlchemy engine, init_db)
│   ├── roll_logic.py               (Core dice utilities: resolve_multi_die_attack, roll_initiative, etc.)
│   ├── effect_engine.py            (Status effects)
│   ├── magic_logic.py              (Spells/techniques)
│   ├── encounter_memory.py         (In-memory encounter state)
│   ├── integrations/
│   │   ├── discord_bot.py          (Phase 2: Discord bot listener)
│   │   ├── twitch_client.py        (Phase 2: Twitch EventSub client)
│   │   └── reactions.py            (Phase 2: Emote-to-reaction mapping)
│   └── utils/
│       └── storage.py              (Optional: persistent storage helpers)
├── routes/
│   ├── chat.py                     (WebSocket chat, party management)
│   ├── combat_fastapi.py           (Phase 1 MVP: 7 combat endpoints)
│   ├── character_fastapi.py        (Character CRUD)
│   ├── effects.py                  (Status effect endpoints)
│   ├── social_integrations.py      (Phase 2: Discord/Twitch webhooks)
│   └── schemas/
│       ├── combat.py               (Combat Pydantic models)
│       ├── character.py            (Character Pydantic models)
│       ├── integrations.py         (Phase 2: Discord/Twitch Pydantic models)
│       └── chat.py                 (Chat Pydantic models)
├── schemas/                        (JSON schema definitions for Storyweaver)
│   ├── core_ruleset.json
│   ├── character_profile.json
│   └── ... (other schemas)
└── tests/
    └── test_combat.py              (Unit tests for resolve_multi_die_attack)
```

---

## 13) When Editing Code — PR Checklist

- [ ] Update or add Pydantic schemas in `routes/schemas/` if changing API contracts
- [ ] Update router registration in `backend/app.py` if adding new routers
- [ ] Preserve `request.state.request_id` usage in all logs
- [ ] Use async/await for all route handlers
- [ ] Test locally: `python app.py` → verify no import errors
- [ ] Test endpoint: POST via `/docs` Swagger UI
- [ ] For Discord/Twitch: Validate webhook signatures before processing
- [ ] Forward emote reactions to WebSocket + spectator system (read-only; don't mutate game state)
- [ ] Test multiplayer scenarios with concurrent clients
- [ ] Commit with clear message: `feat: ...` or `fix: ...`

---

## 14) Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 502 Bad Gateway (Railway) | Port binding issue | Ensure `Procfile` uses `${PORT:-8000}` (not hardcoded `8000`) |
| `ModuleNotFoundError` on startup | Missing import or deleted file | Check `backend/app.py` router registration; verify file exists |
| Request ID missing in logs | Not preserved in middleware | Ensure all handlers use `request.state.request_id` |
| WebSocket broadcast not working | Connection not tracked in session group | Check `routes/chat.py` `active_connections` dict |
| Combat log not persisting | In-memory only (Phase 2 feature) | Migrate to database when implementing Phase 2 |

---

If anything is unclear or you want more examples, let me know which area to expand.
