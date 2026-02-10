# TBA — Tools for the Bad Ass / Tools for Being Awesome

TBA is a modular, cinematic RPG engine designed for expressive storytelling, tactical clarity, and emotional connection. Whether you're a seasoned GM running gritty cyberpunk heists or a parent guiding your kids through whimsical adventures, TBA adapts to your table—and your players.

Built from the ground up with modular endpoints, narratable mechanics, and dual-mode accessibility, TBA empowers families, friends, and communities to tell unforgettable stories together—even when they’re apart.

---

## 🎭 Dual-System Design

TBA is two systems in one:

- **Tools for the Bad Ass**: Mature, tactical, and gritty. Designed for adult players who want expressive combat, branching timelines, and cinematic narration.
- **Tools for Being Awesome**: Kid-friendly, emotionally safe, and easy to learn. The same mechanics, reworded and softened for younger players and families.

An age gate toggles between these modes, adjusting language, narration tone, and content filters—so everyone can play, learn, and grow together.

---

## 🔧 Core Features (In Development)

| Feature | Description |
|---------|-------------|
| **Real-Time Multiplayer Chat** | WebSocket party chat — IC/OOC, system macros, emotional tone indicators, message reactions. The living table where everything happens. |
| **Narration Engine** | Every effect, roll, and action generates expressive, replayable story beats. |
| **Modular API** | Endpoints for actors, effects, encounters, and chat-based resolution. |
| **Session Manager** | Tracks scenes, rolls, emotional beats, and memory markers across campaigns. |
| **Lore & Asset Library** | Taggable, reusable homebrew content—spells, NPCs, vehicles, and more. |
| **Cross-Platform Spectator Mode** | View-only access from web, mobile, or Discord. Spectators can react to messages. |
| **AI Assistant (Optional)** | Prompt-based support for NPC generation, scene narration, and lore expansion. |
| **Age-Gated Experience** | Switch between adult and kid-friendly modes with filtered narration and UI. |

---

## 🧠 Design Philosophy

TBA is built on three pillars:

- **Cinematic Play**: Every roll, reaction, and scene should feel like part of a story worth telling.
- **Modular Simplicity**: Tools should be powerful, but never overwhelming.
- **Emotional Resonance**: Digital spaces should feel like home—personal, persistent, and expressive.

---

## 🛠️ Development Status

TBA is in active development. The backend engine is functional and modular, with narration, effect resolution, and encounter persistence already implemented. Upcoming sprints will focus on tactical coordination, reactive storytelling, and multiplayer session management.

The UI and hosting layers will follow once the emotional and mechanical foundations are solid.

---

## 🧭 Roadmap Highlights

- ✅ **Phase 1 MVP:** Multi-die combat resolution, FastAPI endpoints, Railway deployment
- ✅ **Phase 2a:** Real-time WebSocket party chat (working on Railway)
- ✅ **Phase 2b:** System macros (`/roll`, `/attack`, `/pp`/`/ip`/`/sp`), combat broadcasting, persistent chat
- ✅ **Phase 2d:** Custom ability macros, initiative & encounter system, usage tracking (3 per level per encounter)
- 🔄 **Phase 2c:** Emotional tone indicators, message reactions, markdown support
- 🔄 **Phase 3:** Character builder UI improvements, ability slot management
- 🧍 **Alpha Testing:** Chat tabs (IC/OOC/DMs), spectator integration (Discord/Twitch)
- 🚀 **Beta:** Full encounter manager UI, campaign persistence, cross-platform spectator mode

---

## 👨‍👧 Origin Story

TBA was born while watching his kids soccer practice. Getting older and devoting time to family makes things hard to continue to play TTRPGs. I wanted something more simple, less math, more eventful, and more benefits for thinking outside of the box. Though playtesting hasn't been performed as systems like this should be, I playtested with the my son at age 7. That moment—of shared imagination, laughter, and connection—sparked the vision for a system that could bridge generations. Whether you're a parent, a GM, or a player looking for something more expressive, TBA is for you.

---

## 👤 Author

Created and maintained by **Jason Germino**, a designer, service desk manager, and narrative systems architect. Jason is passionate about expressive digital spaces, cinematic RPGs, and building tools that bring families and communities together through play.

Also founder and editor-in-chief of [GameOctane.com](https://gameoctane.com).

---

## 📜 License

This project is licensed under the **AGPL-3.0**. All hosted versions and derivatives must remain open-source to preserve community-driven development.

---

## 🔗 Live API (Railway)

- Base URL: https://tba-app-production.up.railway.app
- Public health: `/health`
- Protected routes: everything under `/api/` (requires header `X-API-Key: <your key>`)
- OpenAPI docs: `/docs` (click **Authorize** and paste your API key to use “Try it out”).

Quick checks

- Health (no auth):
	```bash
	curl https://tba-app-production.up.railway.app/health
	```
- API health (with key):
	```bash
	curl -H "X-API-Key: <YOUR_API_KEY>" \
			 https://tba-app-production.up.railway.app/api/health
	```
- Sample combat attack (with key):
	```bash
	curl -X POST "https://tba-app-production.up.railway.app/api/combat/attack" \
			 -H "X-API-Key: <YOUR_API_KEY>" \
			 -H "Content-Type: application/json" \
			 -d '{"attacker":"Hero","defender":"Goblin","attack_style_die":"3d4","technique_name":"Slash","stat_type":"PP"}'
	```

### WebSocket Chat Testing

Test real-time multiplayer party chat:

**Browser Test (Easiest)**

1. Open: `https://tba-app-production.up.railway.app/ws-test`
2. Fill in:
   - Railway Base URL: `https://tba-app-production.up.railway.app`
   - Party ID: `test-party` (same for all players)
   - Actor: `Alice` (unique per player)
   - API Key: leave empty
3. Click **Connect**, open second tab with same Party ID
4. Send messages — both tabs receive broadcasts instantly

**CLI Test**
```powershell
npm install -g wscat
wscat -c wss://tba-app-production.up.railway.app/api/chat/party/test-party
{"type":"message","actor":"Alice","text":"Hello!"}
```

**Endpoint:** `wss://<url>/api/chat/party/{party_id}` — broadcasts to all party members

### Quick Start Examples

**Combat Flow:**
```
Alice: /initiative                    # Everyone rolls
Bob: /initiative
SW: /initiative @Goblin              # SW rolls for NPCs
SW: /initiative show                 # See turn order
Alice: /fireball @Goblin             # Cast custom ability
Bob: /heal @Alice                    # Heal teammate
SW: /attack @Alice target:Bob        # SW controls NPC attack
SW: /initiative end                  # End combat, restore abilities
```

**Stat Checks:**
```
Alice: /pp                           # Physical check
Output: 📊 Alice - PP Check: 9
        1d6(4) + PP(3) + Edge(2) = 9
```

**Ability Usage:**
- Create abilities in Character Builder (slots 1-5)
- Each ability has: name, macro command, die, effect type, power source
- Example: "Healing Touch" → `/heal` → 2d6 → heal → IP
- Uses: 3 × character level per encounter
- Auto-restores when `/initiative end` is used

### Live Chat Features ✨

**The Living Table** — Chat is the central hub for everything.

**✅ System Commands (Phase 2b - LIVE)**
- `/roll XdY+Z` — Execute dice rolls from chat
- `/pp`, `/ip`, `/sp` — Stat checks with full math breakdown (1d6 + stat + Edge)
- `/attack @target` — Trigger combat resolution
- `/who` — List party members and stats
- All combat results broadcast in real-time

**✅ Initiative & Encounter System (NEW)**
- `/initiative` — Roll your initiative (1d20)
- `/initiative show` — Display current turn order
- `/initiative @target` (SW) — Roll initiative for someone else
- `/initiative silent @target` (SW) — Hidden rolls for surprise encounters
- `/initiative end` (SW) — End encounter & restore all ability uses
- `/initiative clear` (SW) — Clear initiative without ending
- Turn order filters by role (players only see visible rolls)
- Full persistence across page refreshes

**✅ Custom Ability Macros (Phase 2d - LIVE)**
- **Create character-specific abilities** via character builder
- **Universal macro system** — `/heal`, `/fireball`, `/shield`, `/stealth`, etc.
- **Six effect types:**
  - Single-target damage (attack roll + defense)
  - Single-target healing (auto-success)
  - AOE damage (specify multiple targets: `/fireball @Enemy1 @Enemy2`)
  - AOE healing (heal multiple allies)
  - Buffs (contested roll for success)
  - Debuffs (contested roll for success)
- **Usage tracking:** 3 uses per encounter per character level
- **Smart targeting:** Self-targeting default, @ mentions for others
- **Power sources:** PP (Physical), IP (Intellect), SP (Social)
- Auto-decrements uses, auto-restores on encounter end

**✅ Real-Time Combat Integration**
- Damage/healing updates character DP bars instantly
- Full narrative descriptions for every ability cast
- Math breakdowns for attack/defense rolls
- Persistent combat log (survives page reload)

**🔄 Upcoming Features (Phase 2c-3)**
- **Emotional Expression** — Tone indicators, color-coded bubbles, message reactions
- **Chat Tabs** — IC/OOC/DMs/System Log with filtering
- **Markdown & Media** — Safe markdown, image attachments
- **Spectator Mode** — Discord/Twitch integration with live reactions

## 🧪 Local Development

1) Copy `.env.example` to `.env` and adjust if needed (defaults to sqlite and `devkey`).
2) Install deps: `pip install -r requirements.txt`
3) Run locally: `uvicorn backend.app:application --host 0.0.0.0 --port 8000 --reload`
4) Hit `http://localhost:8000/health` (public) or `http://localhost:8000/api/health` with `X-API-Key: devkey`.

Note: `.env` is git-ignored; do not commit secrets.

---

## 💌 Want to Follow or Contribute?

TBA is currently in private development. Contributions are paused while foundational systems are refined. Feel free to follow progress, fork for personal use, or reach out with questions or encouragement.
