# 📘 TBA API Reference

This document outlines the core endpoints of the TBA combat engine. Each endpoint is designed for modular, narratable, and expressive gameplay. All endpoints follow RESTful conventions and return structured JSON responses.

---

## 🧱 Actor Endpoints

### `POST /actor/create`
Create a new actor with traits, stats, and identity.

### `GET /actor/resolve/{name}`
Resolve all active effects on an actor.

### `POST /actor/plan/{name}`
Submit a tactical plan or intent for an actor.

---

## 🧪 Effect Endpoints

### `POST /effect/apply`
Apply an effect to an actor or encounter.

### `POST /effect/expire`
Expire a previously applied effect.

### `POST /effect/narrate`
Narrate the impact of an effect in cinematic language.

### `GET /effect/resolve/{id}`
Resolve a specific effect by ID.

### `POST /effect/preview`
Preview the outcome of an effect before applying.

### `POST /effect/branch`
Fork an effect into alternate outcomes.

### `POST /effect/stack`
Stack multiple effects on a target.

### `POST /effect/undo/{id}`
Undo a previously applied effect.

---

## 🧠 Encounter Endpoints

### `POST /encounter/start`
Start a new encounter with actors and context.

### `POST /encounter/save`
Save the current encounter state.

### `POST /encounter/load`
Load a saved encounter.

### `GET /encounter/resolve/all`
Resolve all active effects and plans in the encounter.

### `POST /encounter/fork`
Fork the encounter timeline for alternate outcomes.

---

## 🧬 Team & Initiative

### `POST /team/assign`
Assign actors to a team.

### `GET /team/status`
Get current team status and composition.

### `POST /team/resolve`
Resolve team-level actions.

### `POST /encounter/initiative/adjust`
Adjust initiative order within an encounter.

---

## 📜 Lore & Replayability

### `POST /lore/entry`
Add a narrative entry to the lore log.

### `POST /lore/branch`
Create a branching lore path.

### `GET /lore/compare`
Compare two lore entries or timelines.

### `GET /lore/echoes`
Retrieve past echoes of similar events.

---

## 💬 Chat Interface

### `POST /chat/parse`
Parse natural language into engine actions.

### `POST /chat/respond`
Generate a narrative response to a player input.

### `POST /chat/context`
Set or retrieve current chat context.

### `POST /chat/actor/{name}`
Chat with a specific actor.

### `POST /chat/resolve`
Resolve chat-based actions.

### `POST /chat/plan`
Submit a plan via chat.

### `POST /chat/branch`
Fork chat narrative into alternate paths.

---

## 🎲 Rolls & Randomness

### `POST /roll/dice`
Roll standard dice (e.g., d20, d6).

### `POST /roll/custom`
Roll custom dice pools or modifiers.

### `POST /roll/chat`
Roll based on chat input.

### `GET /roll/resolve`
Resolve a roll outcome.

### `GET /roll/actor/{name}`
Get roll history for an actor.

### `GET /roll/session/{id}`
Get roll history for a session.

### `GET /roll/log`
Retrieve global roll log.

---

## 🧱 Persistence & Database

### `POST /db/init`
Initialize database schema.

### `POST /db/save/{entity}`
Save an entity (actor, encounter, effect).

### `GET /db/load/{id}`
Load an entity by ID.

### `POST /db/query`
Query database for entities.

---

## 🧍 Character Builder

### `POST /character/create`
Create a new character profile.

### `POST /character/edit`
Edit an existing character.

### `GET /character/load`
Load a character profile.

### `GET /character/preview`
Preview character stats and traits.

---

## 🖼️ UI & Frontend (Planned)

- Encounter dashboard  
- Actor cards  
- Lore timeline  
- Chat + roll interface

---

## 🧑‍🤝‍🧑 Player Management

### `POST /user/create`
Create a new user profile.

### `POST /session/join`
Join an active session.

### `POST /session/permissions`
Set session permissions.

### `GET /session/history`
Retrieve session history.