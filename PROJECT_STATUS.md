---
phase: active
priority: high
category: app
progress: 83
focus: "Admin center (reports, suspension, messaging, security feed, system status) is finished and live. Rules v3.1.1 is fully in the app. Next: play-test with real players, then pick the next build."
next_milestone: "Real-world check of the admin center and backups (first unattended backup, a test report, a test message), then the next feature Jason picks"
milestone_distance: weeks
community_pressure: low
excitement: high
strategic: true
momentum: rolling
audience: "TTRPG players who want an online platform for async/live play: families, indie creators, adults"
uniqueness: first-mover
viral_potential: medium
mvp_distance: days
waiting_on: jason                # jason / claude / external / none
decision: "What to build next. Candidates: email verification at signup; launch the Discord mirror (built, not announced); Tools for Being Awesome (kids) mode; vehicle systems inside Combos; LBA Stage 0.5 (designed, deliberately paused since Oct 1). Also two small things only Jason can do: check the first unattended nightly backup after 10:17 UTC on 2026-11-20, and click through the new admin screens once."
if_go: "Claude starts whichever one Jason picks on its own branch with tests, shipped separately, and checks it on a real local Postgres before asking to push."
status_verified: "2026-11-19 against the code and git log. pytest 599 passed, 5 skipped. A real-server run on local Postgres passed 40 checks (reports, inbox, suspension, messaging, security feed, status). Admin center A to F is deployed to prod and answers correctly (health 200; admin routes 401 without a login; Jason confirmed the Admin link and the Status tab). Not run: the report and message screens in a real browser."
---

## Why this exists
A live TTRPG platform built for the TBA ruleset — real-time combat, Bonds, Combos, and expressive narration in the browser so you can run sessions without a table.

## Strategic picture
TBA is live at tba-rpg.com. The v3.0 Core Rules dropped on itch.io and Reddit (Jun 2026). The app implements the full ruleset — combat, abilities, initiative, Bonds, Combo attacks, achievements, public profiles. Post-launch traffic via Reddit is the current growth lever. Umami analytics just added to all 11 pages.

The app implements the final **v3.1.1** rules (Rulebook.md, LevelingTable.md), including Ascension (levels 11 to 15), vehicles, Combos resolved by the app, and the rest of the v3.1 phases; the rules numbers all come from one file, `schemas/leveling_v3_1.json`. Since then the work has been making the live site safe to run in public: security upgrades, signup protection, email deliverability, backups and monitoring, private whispers, and an admin center for reports, suspensions, messaging, security events and system status.

Growth direction: Jason is thinking bigger than just TBA — a shared cross-game identity/achievement system ("GO ID") spanning TBA plus other GameOctane projects in the pipe (a Godot 16-bit RPG, FlipperRPG for Flipper Zero, ~15 more early-stage). Key decision made 2026-09-29: GO ID owns the canonical account; Discord is an optional *linked* identity (via a `linked_identities`-style table), never a login method — avoids making the whole universe's auth depend on a third party, and fits FlipperRPG's hardware (no browser for OAuth). Still in the concept/design stage, not scoped yet. In the meantime, the concrete, shippable piece of the "notifications reach people reliably" problem — email digest for your-turn/@mention, max twice a day — shipped this session and doesn't depend on GO ID or Discord at all.

## What's shipped
### Nov 2026: rules v3.1.1, vehicles, safe to run in public, admin center
- ✅ **Rules v3.1.1 fully in the app** (live Nov 17 to 18). The Calling (a tie is Marked, only Marks count, the 5th kills), one leveling file, DP 8 +2 per level and uses level +2 as one shared pool, buffs and debuffs tied to a stat, healing once per person per encounter, summons, Combos resolved by the app (enemy Combos for the SW, all-or-nothing save), Allies and Tethers, Ascension levels 11 to 15, Damage Effects, swarms. Existing characters were migrated in prod (undo: `scripts/migrate_rules_v31.py --undo`). Plan: `docs/rules-v3.1-app-plan.md`.
- ✅ **Vehicles V1 to V5** (migrations 038, 039): SW creates them, crew stations, weapons and systems, called-shot disabling. Plan: `docs/vehicles-plan.md`.
- ✅ **Security**: a crafted Host header could skip the API-key gate (fixed); framework upgrade (FastAPI 0.165, Starlette 1.10, uvicorn 0.54, pydantic 2.14, Pillow 13 and more); a real-server smoke test, `scripts/smoke_server.py`.
- ✅ **Signup protection and email deliverability**: honeypot, throwaway-email block, Cloudflare Turnstile (ON in prod); email now sends from `no-reply@tba-rpg.com`, links use the real domain, every message has a plain-text part.
- ✅ **Backups and monitoring**: nightly encrypted `pg_dump` to a private R2 bucket (14 daily, 8 weekly), a monthly restore drill, both GitHub Actions; guide in `docs/backup-and-restore.md`. Uptime: UptimeRobot on `https://tba-rpg.com/health` (set up by Jason 2026-11-19, alerts to his Gmail). The GitHub uptime workflow is throttled by GitHub and runs only a few times a day, so it is a backup, not the alarm.
- ✅ **Whispers are private** (`3239bea`, migration 041): they reach only the sender and the people addressed, live and in history; recipients are stored. The Story Weaver does not see player-to-player whispers (one switch, `SW_SEES_ALL_WHISPERS` in `backend/whispers.py`). Never sent to Discord.
- ✅ **Admin center, phases A to F** (plan and decisions: `docs/admin-center-plan.md`). Jason is the only admin (`ADMIN_USER_IDS`, which must hold the user **UUID**, not a username). Screens: `/admin.html`, with an Admin link in the header for admins only.
  - A (`689d138`, migration 040): leaving means leaving (every membership lookup ignores people who left, one global filter in `backend/models.py`); the Story Weaver can Remove or Ban a player (their live connection is closed, their character becomes an NPC by default); the SW gets a lasting notification when someone leaves.
  - B (`fab51d1`, migration 042): Report a player or message and Report a bug; an admin inbox with statuses and notes; an audit log; the reporter is never shown to the reported player; "open full conversation" works only from inside a report, shows only whispers between the two people, and is logged before anything is returned.
  - C (`831337d`, migration 043): the admin can suspend and restore an account. A suspended account is logged out of every campaign at once, refused at login and at the live chat connection (which never checked before), and gets no digest email. The reason is private.
  - D (`c3f7ae1`, migration 044): message a player or a whole campaign by bell, push and email, with four built-in and custom saved templates; every send is audit-logged.
  - E (`73589df`, migration 045): a security log (blocked signups, failed logins, rate-limit hits) and a feed of unhandled server errors. No raw IPs (a short salted hash), no emails or bodies; database error messages are dropped; capped and pruned at 30 days.
  - F (`6d256cd`, `0a2e99e`): a read-only Status tab: deployed commit, database, latest migration, the latest backup, restore drill and uptime check, config as yes or no, 24-hour counts, and per-campaign health.

### Earlier
- ✅ Real-time WebSocket combat chat, roll macros, narration engine
- ✅ Initiative & encounter system, turn order, auto-restore on end
- ✅ Custom ability macros — 6 effect types, usage tracking, PP/IP/SP power sources
- ✅ Buff/debuff system — die-based modifiers, duration, contested rolls
- ✅ Tether Boosts — BAP + Tethers into boost card after any roll
- ✅ Stat check system — SW sends hidden-difficulty checks; Character / Char VS NPC / NPC modes
- ✅ Bonds + Combo system — SW-declared, story-earned; propose/accept/fire WS flow
- ✅ Character governance — approval queue, spectator role, NPC conversion, character transfer
- ✅ Achievement system — 153 achievements, 11 categories, rarity tiers, live toasts, Zelda chime
- ✅ Public player profiles — shareable /u/username, no login required to view
- ✅ Notification center — push alerts, live unread count, scroll icon drawer
- ✅ Umami analytics — all 11 pages instrumented (Jun 2026)
- ✅ v3.0 Core Rules — published to itch.io, posted to Reddit
- ✅ Combo cancellation — proposer takes damage before firing → cancel, acceptor's turn resumes normally
- ✅ Triple Combo — full backend (3-way hold/fire state machine) + frontend (propose/accept modals, toolbar buttons)
- ✅ Grief tether weight — SW-selectable, clamped -5..-1, on `break_bond` (`routes/bonds.py`)
- ✅ The Called status system — full Calling roll-off (SW-vs-player, level-scaled difficulty die, margin outcomes), Marked by Death scars → optional Tether, Memory Echo on death, Called Check 1d6 table, cleansing. v3.1 rules (live since Nov 17): a tie is Marked, only Marks count, the 5th Mark kills after the roll. See "Called status — known gaps" below for the small pieces still missing.
- ✅ Mobile/desktop UI pass (Sep 2026) — phone header collapsed to a bell + ⋯ menu, chat toolbar stays one row, sidebar merged into Session/Campaign tabs with initiative round counter, connection-down buttons now say so instead of failing silently
- ✅ Email digest notifications (Sep 2026) — your-turn / @mention, max twice a day (9am/6pm ET), skips anyone already online or already-seen, live-revalidates "your turn" before sending, 2-day staleness cutoff, opt-out toggle + one-click unsubscribe. Live in prod as of 2026-09-29 (the Railway platform incident that briefly queued the deploy resolved; confirmed via `railway deployment list`).
- ✅ Bug/security audit (2026-09-29) over everything since the last documented security pass — found and fixed a High-severity account-takeover hole in the digest's unsubscribe token (was signed with the same key as real login tokens, no expiry; confirmed via a read-only prod query that it was never actually exploited — no digest had sent a real token yet), plus 6 more real correctness bugs (a Postgres-only naive/aware datetime crash that would have silently killed the whole digest feature, a notification-trim data-loss bug, a public-profile privacy leak, a tether-PATCH crash risk, and two initiative-round-counter bugs). See memory `email-digest-notifications.md` / `bug-audit-cadence.md` for full detail. Also worked through the audit's lower-priority reuse/simplification/efficiency findings the same session.
- ✅ Ally auto-Combo (2026-09-29) — `create_ally` now auto-creates the Bond between a character and their new Ally (the mechanism a Combo actually needs), matching the rulebook's "get one Combo automatically at creation." `combo_name` stays blank for the SW to fill in later via the existing bond-update endpoint, same as any other bond.
- ✅ LBA Stage 0 (2026-09-30, pushed 2026-10-01) — "Lore for the Bad-Ass / Lore for Being Awesome": SWs write structured, taggable story packages (`LbaPackage`) — title/tagline/format/party-size/content-rating/genre (multi-select)/tags, plus real linked NPCs (with abilities) and items, side quests, story/world text. Two visibility tiers: a public no-login "window shopping" teaser (`routes/public_lba.py`, `static/lba.html`) and a login-gated full tier behind an explicit spoiler click-through ("Story Weaver, not player" — real public content can't be technically spoiler-proofed, same as a published adventure module). **Start Campaign** is the real feature: clones the package's NPCs (with their abilities — the detail that makes a clone actually runnable), clones items, seeds the new campaign's SW notes with story/side-quests/homebrew (private) and the Lore tab with world text only (spoiler-free, all members can read it — this split was deliberately corrected mid-build after realizing the Lore tab isn't SW-only), and increments `adoption_count` — the real popularity signal, not raw page views. Authoring UI lives in `game.html` (header menu → Publish to LBA); public page restyled to genuinely match the real landing page's design tokens. Verified via 11 new automated tests (76 total passing) plus full real-browser runs of the anonymous→login→reveal→Start-Campaign flow and the multi-select filter UI.
- ✅ Campaign covers v2 (2026-10-08): the cover is now a dimmed background on the game header (no strip, works on phones), with a Header focus slider (migration 033) and a header-shaped preview; every cover is re-encoded server-side with Pillow to a small metadata-free JPEG (800px min, 1920px max, 10MB upload cap); the SW can pick any Images-tab picture as the cover ('Use as cover'). Fixed Brave hiding the old cover (class `cb-banner` is in the Easylist Cookie List, classes are now `tbacv-*`).
- ✅ Campaign banners, browse tags and moderation (2026-10-07). Inspired by Rolegate's game list. SWs can upload an optional campaign banner (JPEG/PNG/WebP, 3MB, validated by real bytes, SW-only; `banner_url` is only ever written by the upload endpoint, never a settings PATCH) shown on the campaigns.html cards (My Campaigns + Browse) and as a collapsible strip under the game.html header (hidden on phones). Campaigns also get genres (up to 5, same list as LBA), a content rating, and a "Last post N minutes ago" line from the newest message; Browse hides archived campaigns and uses grouped queries. Campaigns started from an LBA story copy its tags and a "Based on [Title] by @author" credit (title/author copied in so it survives the story being deleted), start **private**, and hide the credit from players inside the game unless the SW opts in (spoiler guard). Moderation shipped first: any logged-in user can report a banner with a reason dropdown (`REPORT_REASON_LABELS` in models.py), rate-limited and deduplicated, admins (env `ADMIN_USER_IDS`) review at `/admin-reports.html` and can remove (deletes the R2 file, notifies the SW with the reason) or remove-and-lock; reporter identity is only returned to admins. `content_reports` is built to take LBA packages/characters later. Migrations 031 + 032. Reports are emailed to the admin accounts' email addresses.
- ✅ Oct 19 batch (2026-10-19, recorded by Claude from commit messages; no session notes existed): **BAP is never banked** — it applies to one roll through a compact Boost button; banked BAP tokens, their grant/revoke endpoints and the dead "arm BAP" code are gone; stat checks the SW grants BAP for include it in the roll, a fired Combo adds full BAP to both rolls (rules 3.1); old token flags in the DB are inert, no migration. **Summons act for real** — damage/heal/debuff rolls, saved cards, Boost, and an SW Act button on the summon's turn; casting a summon no longer fails on Postgres (missing attack_style/defense_die); summon cards keep their style after refresh. **Discord mirror is story only** — before this it forwarded OOC chat and private whispers to the public channel; now blocked by event type and by chat_mode, plus a guard test. `MODERATION_EMAIL` env var sets where content-report emails go.

## Deliberate sequencing decision (2026-10-01)
LBA Stage 0.5 (Lore Builder, campaign-less authoring, cloning/attribution,
NPC/PC-level publishing, moderation) is fully designed — see the plan doc,
`C:\Users\jgermino\.claude\plans\hashed-seeking-pudding.md` — but
**deliberately not being built next**. Reasoning, from Jason directly: TBA
is still in testing, not promoted, and the ruleset isn't final (Ascension
+ a possible broader rules revision are still ahead). Publishing/sharing
content now, before rules settle, risks that content going stale the
moment mechanics change — weakens LBA's "clone something that actually
works" promise. **Order: Ascension → possible rules revision → LBA Stage
0.5.** Don't resume LBA work until Ascension (and any rules revision) is
done, even if it's tempting to — this was an explicit, reasoned call, not
a drop.

## Next up
**Do these first (small, only Jason can):**
- [x] **Backups are now automatic and watched (2026-11-20).** GitHub's own scheduler is unreliable on this repo: the 10:17 UTC backup was not started until 18:38 UTC (8 hours late, event 'schedule', success) and the uptime workflow runs only every few hours. So `backend/backup_watchdog.py` (live, deploy 9eda6dbb) checks hourly inside the app and starts the nightly backup (daily 10:17 UTC) or the restore drill (1st of the month, 11:43 UTC) through GitHub's `workflow_dispatch` API when no successful run exists since the last scheduled time (never twice within 6 hours, never while one runs). Jason set `GITHUB_DISPATCH_TOKEN` in Railway; verified: it reads runs (200) and has write permission (a dispatch to a nonexistent branch returned 422 'No ref found', not 403). **The token expires 2027-11-20: renew it before then or the watchdog stops working** (the Status tab will show 'Backup watchdog' red with the GitHub error). Not yet seen: the watchdog actually starting a run, because the delayed scheduled run had already covered today. Confirm once by looking at Admin > Status after a day when GitHub skips the schedule, or see a `workflow_dispatch` backup run appear without a manual start. Restore drill: last run 2026-11-19; the next is due 2026-12-01.
- [ ] Confirm UptimeRobot shows the monitor "Up" and that the Gmail alert contact is verified.
- [ ] Click through the new screens once: send yourself a bug report (sidebar > Report a bug), a player report from a second account, and a bell message from Admin > Message, then try email. These were tested in code and against a real server, not in a browser.
- [ ] Save `BACKUP_PASSPHRASE` in a password manager (without it a backup cannot be opened). Check GitHub Settings > Notifications > Actions so failure emails reach you.
- [ ] Approve or reject the pending character "Handmann (Handyman)"; reach out to Zaytoven, who is in no campaign.

**Open questions for Jason (raised 2026-11-19, nothing changed yet):**
- [ ] **Open source or not?** The repo is public under AGPL-3.0, with 0 forks. Claude's recommendation: keep the code public (free unlimited GitHub Actions for the backups and uptime check, trust with the audience), but put the rules text and art under a separate content license (AGPL lets anyone host a paid copy with the rulebook text), move `docs/LICENSE` to the repo root so GitHub detects it, and scan the git history for leaked secrets. Waiting on his call before changing any license.
- [x] The site said "free rulebook" while the itch.io page is pay what you want. Jason had the four places changed to "Get the rulebook on itch.io (pay what you want)" on 2026-11-19 (`auth.html`, `campaigns.html`, `index.html`, `game.html`).

**Build candidates (Jason picks):**
- [ ] Email verification at signup (there is none today; signup protection stops bots, not typos or fake addresses).
- [ ] Launch the Discord mirror (built and tested, deliberately not announced yet).
- [ ] Tools for Being Awesome (kids) mode.
- [ ] Vehicle systems inside Combos; a vehicle play-test with real players first.
- [ ] Optional hygiene: optional Cloudflare Email Routing plus `REPLY_TO_EMAIL`; migrate python-jose to PyJWT; tidy the Docker dead weight listed in CLAUDE.md; the untracked docs under `docs/TBA-App-v3.1*-Handoff/` and `docs/tba_rules-3.1*.md`.
- [ ] Parked on purpose: LBA Stage 0.5 and 1 (see the sequencing decision), social and friends, GO ID (concept only), the age-gated experience.

**Done since the last version of this list:** all nine v3.1 phases and Ascension, Triple Combo's level gate (now 11+), the environmental damage tier system, the admin center, backups, signup protection and email deliverability.

### Called status — known gaps (small, optional; core mechanic is done)
- No escalating trigger cadence by `times_called` (now the Mark count) — rulebook says 1st Calling = rests only, 2nd = rests+adventuring, 3rd-4th = +battle. App has one manual SW "Called Check" button, usable anytime regardless of count.
- The Called Check's ±1 result is narrative-only — never mechanically applied to a subsequent roll. No wiring to the Tether/Active-Effects modifier system.
- No nightmare/vision flavor-text table — one static sentence per outcome (nightmare/peaceful/vision) rather than a bank of prompts to roll from.
- Cosmetic: `Character.is_called`/`times_called` column comments in `backend/models.py:227-228` say "summoned" (stale, reused-column leftover).
- `backend/achievements.py:819-822` "Death Knows My Name" (survive Calling ×5) was unreachable under v3.0. Under v3.1 (live) a clean return does not count toward the five and the 5th is decided by the roll, so five survivals is reachable again. Not tested against the achievement tracker yet.

## Blockers
Nothing blocks the code. Everything under "Do these first" is Jason's to do, and none of it stops new work. Production data cannot be queried from Jason's PC (the database only has an internal Railway address), so anything that needs a prod read goes through a deployed endpoint, such as the Status tab, or the Railway CLI.

## Resume here
The admin center is finished, so there is no half-built work. Open `PROJECT_STATUS.md` > **Next up** and take Jason's pick. If he has not picked, ask; do not default to LBA Stage 0.5 (paused on purpose, see the sequencing decision above).

First file to open: `routes/auth.py` if the pick is email verification (the signup guard is `backend/signup_guard.py`), `backend/discord_mirror.py` for the Discord launch, or `docs/admin-center-plan.md` for anything that touches the admin screens (`static/admin.html`, `routes/reports.py`, `routes/admin_*.py`).

Gotchas learned the hard way: new routes registered after the static mount at `/` never match in tests (insert at `router.routes[0]`); `ADMIN_USER_IDS` must be UUIDs; the production database is not reachable from the dev PC; a push to `main` redeploys prod and runs new migrations first, and `start.sh` stops the deploy if a migration fails.

**Sync gap:** the plan doc named in the sequencing decision lives at `C:\Users\jgermino\.claude\plans\...` on Jason's PC, and the memory notes named under "What's shipped" are local too. A cloud or scheduled session cannot read them. Copy anything a future session needs into the repo (for example `docs/plans/`) before relying on it.

## Last session
**2026-11-19** (one long session, all of it pushed to `main` and verified live): whispers made private, then the whole admin center, phases A to F, then a small date-format fix (`0a2e99e`). Latest deploy `62cb4075`; health 200; every admin route answers 401 without a login; Jason confirmed the Admin link and the Status tab. Migrations 040 to 045 all applied (each is additive). Tests: 599 passed, 5 skipped. Each phase was also run against a real server on a local Postgres (40 checks, all real ones passing).

Findings worth remembering:
- `ADMIN_USER_IDS` held the username `Klutzleo`, so no admin page had ever worked; it now holds Jason's user id.
- The GitHub uptime workflow ran only twice in about ten hours (GitHub throttles scheduled jobs on quiet repos), so the down alert was not reliable. Jason added UptimeRobot on `/health`.
- Whispers had been broadcast to every connected member and returned in history to every member. Production had none stored, so no past leak; fixed going forward.
- 53 of 81 membership lookups ignored `left_at`, so someone who left could still call campaign APIs. Fixed at one choke point.
- A test caught that an admin search for `%` listed everyone; fixed before it shipped.

Found the next morning (2026-11-20): the scheduled nightly backup never ran (see Next up). Not done: browser click-through of the report, inbox and message screens; no real email or push was sent from the new admin features (code paths were tested with stand-ins); the first unattended nightly backup had not run yet.

Older sessions (Sept to Nov 2026, newest first) are in `docs/status-history.md`.
