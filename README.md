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
| **Narration Engine** | Every effect, roll, and action generates expressive, replayable story beats. |
| **Modular API** | Endpoints for actors, effects, encounters, and chat-based resolution. |
| **Session Manager** | Tracks scenes, rolls, emotional beats, and memory markers across campaigns. |
| **Lore & Asset Library** | Taggable, reusable homebrew content—spells, NPCs, vehicles, and more. |
| **Cross-Platform Spectator Mode** | View-only access from web, mobile, or Discord. |
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

- ✅ Sprint 1–4: Core schema, narration, and persistent effects complete
- 🧠 Sprint 5: Tactical resolution, preview, and branching (in progress)
- 🧩 Sprint 6–8: Squad coordination, conditionals, and deep lore replayability
- 💬 Sprint 11–12: Conversational interface and dice-based reactions
- 🧍 Sprint 14–16: Character builder, UI, and player management

Full roadmap: `docs/roadmap.md`

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

## 🧪 Local Development

1) Copy `.env.example` to `.env` and adjust if needed (defaults to sqlite and `devkey`).
2) Install deps: `pip install -r requirements.txt`
3) Run locally: `uvicorn backend.app:application --host 0.0.0.0 --port 8000 --reload`
4) Hit `http://localhost:8000/health` (public) or `http://localhost:8000/api/health` with `X-API-Key: devkey`.

Note: `.env` is git-ignored; do not commit secrets.

---

## 💌 Want to Follow or Contribute?

TBA is currently in private development. Contributions are paused while foundational systems are refined. Feel free to follow progress, fork for personal use, or reach out with questions or encouragement.
