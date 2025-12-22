# CHANGELOG — TBA-App

This document summarizes notable changes and instrumentation added during development.

## 2025-12-22 — WS Chat Macros, UI, and Logging Controls

### Enhancements
- WebSocket macros now show explicit formulas and results for all clients:
  - `/roll 2d4+4` → displays `2d4+4 → (3 + 1) + 4 = 8`.
  - `/pp`, `/ip`, `/sp` (stat rolls) → displays `1d6+1 → 4 + 1 = 5` (Edge as placeholder).
  - `/initiative` → displays `1d6+1 → 3 + 1 = 4` (Edge as placeholder).
- Broadcast payloads include:
  - `dice` (formula), `breakdown` (raw rolls), `modifier` (Edge placeholder), `text` (equation), and `result`.
- Combat logs enriched for macros:
  - `/roll`, `stat_roll`, and `initiative` entries now include `dice`, `breakdown`, `modifier`, `result`.
  - Optional `context` and `encounter_id` threaded from WS payload (if provided).

### WS Test UI
- Added optional inputs: `Context` and `Encounter ID`.
- Added role selector: `Player` or `Story Weaver (SW)`.
  - SW: breakdowns auto-expand; toggle label starts as “Hide details”.
  - Player: breakdowns collapsed by default; toggle label starts as “Show details”.
- Added compact "Show details" toggle for `dice_roll`, `stat_roll`, and `initiative` messages.

### Logging & Rate Control
- New env var `WS_LOG_VERBOSITY` to gate macro logging to combat log:
  - `macros` (default): log all macro types.
  - `minimal`: log only `dice_roll` and `initiative`.
  - `off`: disable macro logging.
- Macro throttle per `party_id+actor`:
  - New env var `WS_MACRO_THROTTLE_MS` (default `700`).
  - Prevents spam; rate-limited users see a small system message.

### Files Touched
- Server:
  - [routes/chat.py](../routes/chat.py)
    - Macro handler enriched with `dice`, `breakdown`, `modifier`, formatted `text`.
    - Logs routed through `log_if_allowed()` honoring `WS_LOG_VERBOSITY`.
    - Threaded `context` and `encounter_id` from WS payload to macro logs.
    - Added macro throttle using `WS_MACRO_THROTTLE_MS`.
- Client UI:
  - [static/ws-test.html](../static/ws-test.html)
    - Renders formula + equation for all macro types.
    - Adds context/encounter payload fields.
    - Adds role selector and toggle to expand/collapse details.

### Notes & Next Steps
- Current `modifier` uses a placeholder `Edge = 1`. Wire real character stats (PP/IP/SP, Edge, BAP) next.
- Initiative: Implement tie-breakers (PP → IP → SP) per TBA v1.5.
- Consider a unified schema for macro messages in `routes/schemas/chat.py`.
- Optionally include `meta` (context/encounter) in broadcast messages if party clients should see it.

## 2025-12-11 — Campaign WebSocket Chat (Initial)
- Introduced Party WebSocket endpoint and basic test page (see `.github/copilot-instructions.md` for details).
