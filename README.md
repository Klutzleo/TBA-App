<div align="center">

# TBA

### Tools for the Bad Ass &nbsp;/&nbsp; Tools for Being Awesome

**A cinematic tabletop RPG you can play in your browser, together or apart.**

[![Live](https://img.shields.io/badge/live-tba--rpg.com-d4af37?style=for-the-badge)](https://tba-rpg.com)
[![Rules](https://img.shields.io/badge/rules-v3.1.1-8b5cf6?style=for-the-badge)](https://klutzleo.itch.io/tba-rpg)
[![License](https://img.shields.io/badge/license-AGPL--3.0-3b82f6?style=for-the-badge)](#-license)

![Python](https://img.shields.io/badge/python-3.11-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169e1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-600%2B-34d399)

[Play](https://tba-rpg.com) &nbsp;·&nbsp; [Get the rulebook on itch.io](https://klutzleo.itch.io/tba-rpg) &nbsp;·&nbsp; [Discord](https://discord.gg/pnuamjT) &nbsp;·&nbsp; [Docs](docs/) &nbsp;·&nbsp; [Run it locally](#-run-it-locally)

</div>

---

TBA is a modular, cinematic RPG engine built for expressive storytelling, tactical clarity, and emotional connection. Whether you are a seasoned Story Weaver running gritty cyberpunk heists or a parent guiding your kids through whimsical adventures, TBA adapts to your table and your players.

Everything happens in one place: real-time chat, dice, initiative, combat, characters, and the story itself. Every roll and attack comes back as expressive narration, so a fight reads like a scene, not a spreadsheet.

## 🎭 Two systems in one

- **Tools for the Bad Ass**: mature, tactical, and gritty. Expressive combat, branching timelines, and cinematic narration for adult players.
- **Tools for Being Awesome**: kid-friendly, emotionally safe, and easy to learn. The same mechanics, reworded and softened for younger players and families.

An age gate is planned to switch between the two, adjusting language, narration tone, and content filters, so everyone can play, learn, and grow together.

## ✨ What you can do

### At the table

| | Feature | What it does |
|---|---|---|
| 💬 | **Real-time party chat** | WebSocket chat with in-character, out-of-character, and private whispers. Inline dice, system macros, and a persistent log. |
| ⚔️ | **Initiative and encounters** | Turn order, Story Weaver controls, round counter, and automatic restore when a fight ends. |
| 🎲 | **Multi-die combat** | Each attacker die rolls against the defender's single defense die. Damage is the margin, summed. |
| 📖 | **Narration engine** | Every roll, attack, and ability produces expressive narrative output. |
| 🔗 | **Bonds and Combos** | Characters form Bonds with allies and chain them into Combo attacks, including Triple Combos, fully resolved by the app. |
| ⚓ | **Tethers and Boosts** | Tethers ride on every roll, and a Boost card combines BAP and Tethers after a roll. |
| 🚗 | **Vehicles** | Crewed vehicles with stations, weapons, systems, and called-shot disabling. |
| 🕯️ | **The Calling** | A death spiral with battle scars, Marks, and Memory Echoes when a character falls. |

### For the Story Weaver

| | Feature | What it does |
|---|---|---|
| 🎯 | **Hidden stat checks** | Send checks with a hidden difficulty. Character, Character vs NPC, or NPC, to one player or many. |
| 🌋 | **Environmental checks** | Damage tiers that players roll to resist, and that can trigger The Calling. |
| 🧙 | **NPCs, Allies, summons** | Run NPCs and swarms, give players Allies, and manage summons. |
| ✅ | **Character governance** | An approval queue, spectator role, NPC conversion, and character transfer. |
| 🚪 | **Table control** | Remove or ban a disruptive player. If someone leaves, you are told which character it was and whether they were in the current fight. |

### Characters and progression

| | Feature | What it does |
|---|---|---|
| 📈 | **Levels 1 to 15** | Ascension (11 to 15) is live. Allies and vehicles stop at 10. |
| 🛠️ | **Custom ability macros** | Spells and techniques with six effect types, drawn from one shared pool of uses. |
| 🏆 | **Achievements** | 153 achievements across 11 categories, with rarity tiers, a badge showcase, and live toasts. |
| 👤 | **Public profiles** | Shareable `/u/username` pages with stats, characters, and achievements. No login needed to view. |

### Community and platform

| | Feature | What it does |
|---|---|---|
| 🔔 | **Notification center** | In-app bell, web push, and an optional twice-a-day email for your turn and mentions. |
| 📚 | **Lore for the Bad-Ass (LBA)** | Publish structured story packages, browse them without logging in, and start a campaign from one. |
| 🖼️ | **Campaign covers and tags** | Optional banner, genres, and content ratings on the campaign cards. |
| 📱 | **Installable app** | A PWA that works on phone and desktop. |

## 📜 The rules

The app implements the **v3.1.1** rules, and when the code and the rulebook disagree, the rulebook wins. The rulebook is on itch.io, pay what you want.

- Three stats (PP, IP, SP), each 1 to 3, adding up to 6.
- Levels 1 to 15. DP is 8, plus 2 per level.
- Uses are level plus 2, as one shared pool for every spell, technique, and vehicle system.
- All the numbers live in one file, [`schemas/leveling_v3_1.json`](schemas/leveling_v3_1.json), read through `backend/leveling.py`.

**[Get the rulebook on itch.io](https://klutzleo.itch.io/tba-rpg)** (pay what you want) to read the full rules before your first session.

## 🛡️ Safe to play in public

TBA is a live site with real players, so safety is part of the product.

- **Private means private.** Whispers reach only the people they are sent to.
- **Reports and bug reports** go to a private admin inbox. The person reported never learns who reported them.
- **Story Weavers can remove or ban** a player from their own campaign, and the site admin can suspend an account.
- **Signup protection:** a honeypot, a throwaway-email block, and Cloudflare Turnstile, plus per-IP rate limits.
- **Backups:** nightly encrypted database backups, a monthly restore drill, and an uptime alert.
- **Security log** of blocked signups, failed logins, and server errors that stores no raw IP addresses.

## 🧰 Under the hood

| Layer | Choice |
|---|---|
| Backend | FastAPI and Uvicorn, one process |
| Database | PostgreSQL in production, SQLite for local development, SQLAlchemy 2.0 |
| Real time | WebSockets |
| Auth | Argon2 password hashing and JWT |
| Frontend | Plain HTML, CSS, and JavaScript with no build step, installable as a PWA |
| Hosting | Railway, built from the `Dockerfile` |

```
backend/      game logic: dice, magic, effects, achievements, notifications, models
routes/       FastAPI routers: chat and combat hub, characters, campaigns, admin tools
static/       the play surface (game.html), landing page, admin screens
schemas/      the rules numbers as JSON
tests/        600+ pytest tests covering rules, combat, security, and privacy
docs/         plans, API reference, backup and restore guide
```

## 🧪 Run it locally

```bash
cp .env.example .env          # defaults to SQLite and a dev API key
pip install -r requirements.txt
python app.py                 # http://localhost:8000, API docs at /docs
```

Run the tests before you push anything:

```bash
pytest tests/ -v
```

The health check is public at `http://localhost:8000/health`. `.env` is git-ignored, so never commit secrets.

## 🗺️ Roadmap

**Shipped**

- ✅ Real-time chat, macros, combat broadcast, initiative, and encounters
- ✅ Stat checks, achievements, public profiles, and the notification center
- ✅ Bonds, Combos, and The Calling
- ✅ Rules v3.1.1, Ascension, Allies, summons, swarms, and vehicles
- ✅ Lore for the Bad-Ass (LBA), the first stage
- ✅ Safety tools: private whispers, reports, removal and bans, suspension, and an admin center

**Next**

- 🔄 Email verification at signup
- 🔄 Discord integration: a live campaign mirror and linked accounts
- 🔄 Tools for Being Awesome (kids) mode
- 🔄 Vehicle systems inside Combos
- 🔄 Social features: follow players and a friend activity feed
- 🚀 Lore Builder and cross-game identity ("GO ID") are designed and waiting their turn

## 👨‍👧 Origin story

TBA was born while watching his kids soccer practice. Getting older and devoting time to family makes things hard to continue to play TTRPGs. I wanted something more simple, less math, more eventful, and more benefits for thinking outside of the box. Though playtesting hasn't been performed as systems like this should be, I playtested with my son at age 7. That moment of shared imagination, laughter, and connection sparked the vision for a system that could bridge generations. Whether you're a parent, a GM, or a player looking for something more expressive, TBA is for you.

## 👤 Author

Created and maintained by **Jason Germino**, a designer, service desk manager, and narrative systems architect. Jason is passionate about expressive digital spaces, cinematic RPGs, and building tools that bring families and communities together through play.

Also founder and editor-in-chief of [GameOctane.com](https://gameoctane.com).

## 📜 License

This project is licensed under the **AGPL-3.0**. All hosted versions and derivatives must remain open-source to preserve community-driven development.

## 💌 Want to follow or contribute?

Contributions are paused while the foundations are refined. Feel free to follow progress, fork for personal use, or reach out with questions or encouragement. The best way to see TBA is to [play it](https://tba-rpg.com), and you can chat with other players on [Discord](https://discord.gg/pnuamjT).
