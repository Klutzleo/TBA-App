# 🧠 Combat Engine Roadmap

This document outlines the development roadmap for the narratable, modular combat engine built by Jason. Each sprint represents a tactical and narrative milestone, moving from backend persistence to expressive storytelling and campaign-grade orchestration.

---

## 🧱 Sprint 1: Core Schema & Engine Bootstrapping
**Goal**: Define foundational schema and initialize combat engine  
**Status**: Complete  
**Key Features**:
- Actor, effect, and encounter schemas
- Modular endpoint scaffolding
- Initial Flask app with persistent state
- `/actor/create`, `/encounter/start`, `/effect/apply`

---

## 🧪 Sprint 2: Validation & Debugging
**Goal**: Ensure schema integrity and cross-platform reliability  
**Status**: Complete  
**Key Features**:
- JSON parsing fixes across PowerShell, curl, and VS Code
- Expressive error handling and debug logs
- `/validate/schema`, `/log/error`, `/debug/trace`

---

## 🧠 Sprint 3: Narration & Replayability
**Goal**: Add narrative hooks and replayable state  
**Status**: Complete  
**Key Features**:
- `/lore/entry` for narrating effects
- `/encounter/save` and `/encounter/load`
- `/effect/narrate` for expressive storytelling

---

## ✅ Sprint 4: Persistent Effects
**Goal**: Apply, expire, narrate, and validate persistent effects  
**Status**: Complete  
**Key Endpoints**:
- `/effect/apply`
- `/effect/expire`
- `/effect/narrate`
- `/encounter/save`
- `/encounter/load`

---

## 🧠 Sprint 5: Tactical Expansion
**Goal**: Resolve effects, preview outcomes, fork timelines  
**Status**: In Progress  
**Key Endpoints**:
- `/effect/resolve/{id}`
- `/actor/resolve/{name}`
- `/encounter/resolve/all`
- `/effect/preview`
- `/effect/branch`
- `/encounter/fork`
- `/actor/plan/{name}`
- `/effect/stack`
- `/effect/undo/{id}`

---

## 🧩 Sprint 6: Multi-Actor Coordination
**Goal**: Tactical coordination, squad-level planning  
**Status**: Planned  
**Key Endpoints**:
- `/team/assign`
- `/team/status`
- `/team/resolve`
- `/encounter/initiative/adjust`

---

## 🧬 Sprint 7: Conditionals and Triggers
**Goal**: Reactive combat logic, status-based storytelling  
**Status**: Planned  
**Key Endpoints**:
- `/effect/trigger`
- `/actor/condition/{name}`
- `/effect/chain`

---

## 📜 Sprint 8: Lore Engine Expansion
**Goal**: Deep narrative replayability and expressive storytelling  
**Status**: Planned  
**Key Endpoints**:
- `/lore/branch`
- `/lore/compare`
- `/lore/echoes`

---

## 🧪 Sprint 9: Testing & Validation Suite
**Goal**: MSP-grade reliability, automated validation  
**Status**: Planned  
**Key Endpoints**:
- `/test/encounter`
- `/validate/branch`
- `/log/errors`

---

## 🌐 Sprint 10: Multiplayer & Session Management
**Goal**: Collaborative play, persistent sessions  
**Status**: Future  
**Key Endpoints**:
- `/session/create`
- `/session/join`
- `/session/log`

---

## 💬 Sprint 11: Conversational Interface
**Goal**: Natural-language interaction with the engine  
**Status**: Future  
**Key Endpoints**:
- `/chat/parse`
- `/chat/respond`
- `/chat/context`
- `/chat/actor/{name}`
- `/chat/resolve`
- `/chat/plan`
- `/chat/branch`

---

## 🎲 Sprint 12: Rolls, Reactions, and Randomness
**Goal**: Dice rolls, modifiers, and reactive outcomes via chat  
**Status**: Future  
**Key Endpoints**:
- `/roll/dice`
- `/roll/custom`
- `/roll/chat`
- `/roll/resolve`
- `/roll/actor/{name}`
- `/roll/session/{id}`
- `/roll/log`

---

## 🧱 Sprint 13: Database & Persistence
**Goal**: Durable backend, multi-session campaigns  
**Status**: Future  
**Key Endpoints**:
- `/db/init`
- `/db/save/{entity}`
- `/db/load/{id}`
- `/db/query`

---

## 🧍‍♂️ Sprint 14: Character Builder
**Goal**: Personalized actors with persistent identity  
**Status**: Future  
**Key Endpoints**:
- `/character/create`
- `/character/edit`
- `/character/load`
- `/character/preview`

---

## 🖼️ Sprint 15: UI & Frontend
**Goal**: Visual interface for players and GMs  
**Status**: Future  
**Features**:
- Encounter dashboard
- Actor cards
- Lore timeline
- Chat + roll interface

---

## 🧑‍🤝‍🧑 Sprint 16: Player Management
**Goal**: Collaborative play with persistent user identity  
**Status**: Future  
**Key Endpoints**:
- `/user/create`
- `/session/join`
- `/session/permissions`
- `/session/history`

---

## 🧭 Next Steps
- Finalize Sprint 5 endpoints
- Begin scaffolding Sprint 6 and 7 logic
- Prototype `/chat/parse` and `/roll/chat`
- Draft schema for `/character/create`
- Explore frontend wireframes for Sprint 15

---