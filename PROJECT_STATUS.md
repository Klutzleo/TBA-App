---
phase: active
priority: high
category: app
progress: 83
focus: "LBA Stage 0 shipped. Deliberately pausing growth features — Ascension is next, then a possible rules revision, then LBA Stage 0.5"
next_milestone: "Ascension levels 11-15, once Jason's NPC/Ally leveling write-up is ready"
milestone_distance: weeks
community_pressure: low
excitement: high
strategic: true
momentum: rolling
audience: "TTRPG players who want an online platform for async/live play — families, indie creators, adults"
uniqueness: first-mover
viral_potential: medium
mvp_distance: days
---

## Why this exists
A live TTRPG platform built for the TBA ruleset — real-time combat, Bonds, Combos, and expressive narration in the browser so you can run sessions without a table.

## Strategic picture
TBA is live at tba-rpg.com. The v3.0 Core Rules dropped on itch.io and Reddit (Jun 2026). The app implements the full ruleset — combat, abilities, initiative, Bonds, Combo attacks, achievements, public profiles. Post-launch traffic via Reddit is the current growth lever. Umami analytics just added to all 11 pages.

The game is now fully v3.0-spec-compliant on the rules side — Combo rules (cancellation, triple), grief tether weight, and The Called status system are all shipped and verified against `Rulebook.md`. The mobile/desktop UI also got a real pass (phone header, chat toolbar, sidebar merge) after Jason's own phone testing surfaced crowding issues. Ascension levels 11-15 is scoped but on hold — Jason wants NPCs (and possibly Allies) levelable past 10 too, not just PCs, and is writing up that fuller design before implementation starts.

Growth direction: Jason is thinking bigger than just TBA — a shared cross-game identity/achievement system ("GO ID") spanning TBA plus other GameOctane projects in the pipe (a Godot 16-bit RPG, FlipperRPG for Flipper Zero, ~15 more early-stage). Key decision made 2026-09-29: GO ID owns the canonical account; Discord is an optional *linked* identity (via a `linked_identities`-style table), never a login method — avoids making the whole universe's auth depend on a third party, and fits FlipperRPG's hardware (no browser for OAuth). Still in the concept/design stage, not scoped yet. In the meantime, the concrete, shippable piece of the "notifications reach people reliably" problem — email digest for your-turn/@mention, max twice a day — shipped this session and doesn't depend on GO ID or Discord at all.

## What's shipped
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
- ✅ The Called status system — full Calling roll-off (SW-vs-player, level-scaled difficulty die, margin outcomes), Marked by Death scars → optional Tether, Memory Echo on death, 5th-Calling permadeath, Called Check 1d6 table, cleansing. See "Called status — known gaps" below for the small pieces still missing.
- ✅ Mobile/desktop UI pass (Sep 2026) — phone header collapsed to a bell + ⋯ menu, chat toolbar stays one row, sidebar merged into Session/Campaign tabs with initiative round counter, connection-down buttons now say so instead of failing silently
- ✅ Email digest notifications (Sep 2026) — your-turn / @mention, max twice a day (9am/6pm ET), skips anyone already online or already-seen, live-revalidates "your turn" before sending, 2-day staleness cutoff, opt-out toggle + one-click unsubscribe. Live in prod as of 2026-09-29 (the Railway platform incident that briefly queued the deploy resolved; confirmed via `railway deployment list`).
- ✅ Bug/security audit (2026-09-29) over everything since the last documented security pass — found and fixed a High-severity account-takeover hole in the digest's unsubscribe token (was signed with the same key as real login tokens, no expiry; confirmed via a read-only prod query that it was never actually exploited — no digest had sent a real token yet), plus 6 more real correctness bugs (a Postgres-only naive/aware datetime crash that would have silently killed the whole digest feature, a notification-trim data-loss bug, a public-profile privacy leak, a tether-PATCH crash risk, and two initiative-round-counter bugs). See memory `email-digest-notifications.md` / `bug-audit-cadence.md` for full detail. Also worked through the audit's lower-priority reuse/simplification/efficiency findings the same session.
- ✅ Ally auto-Combo (2026-09-29) — `create_ally` now auto-creates the Bond between a character and their new Ally (the mechanism a Combo actually needs), matching the rulebook's "get one Combo automatically at creation." `combo_name` stays blank for the SW to fill in later via the existing bond-update endpoint, same as any other bond.
- ✅ LBA Stage 0 (2026-09-30, pushed 2026-10-01) — "Lore for the Bad-Ass / Lore for Being Awesome": SWs write structured, taggable story packages (`LbaPackage`) — title/tagline/format/party-size/content-rating/genre (multi-select)/tags, plus real linked NPCs (with abilities) and items, side quests, story/world text. Two visibility tiers: a public no-login "window shopping" teaser (`routes/public_lba.py`, `static/lba.html`) and a login-gated full tier behind an explicit spoiler click-through ("Story Weaver, not player" — real public content can't be technically spoiler-proofed, same as a published adventure module). **Start Campaign** is the real feature: clones the package's NPCs (with their abilities — the detail that makes a clone actually runnable), clones items, seeds the new campaign's SW notes with story/side-quests/homebrew (private) and the Lore tab with world text only (spoiler-free, all members can read it — this split was deliberately corrected mid-build after realizing the Lore tab isn't SW-only), and increments `adoption_count` — the real popularity signal, not raw page views. Authoring UI lives in `game.html` (header menu → Publish to LBA); public page restyled to genuinely match the real landing page's design tokens. Verified via 11 new automated tests (76 total passing) plus full real-browser runs of the anonymous→login→reveal→Start-Campaign flow and the multi-select filter UI.

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
- [ ] **Ascension levels 11-15 — next up.** Rules locked for PCs; on hold pending Jason's write-up on whether NPCs/Allies also go past 10 (Allies have their own separate, lower stat table that doesn't extend without new numbers). Also: Triple Combo's level gate is `== 10` in both `campaign_websocket.py` and `game.html` — needs to become `>= 10` whenever Ascension ships, or an Ascended character loses Triple Combo the moment they level past 10. Full technical inventory already done, see plan doc.
- [ ] Possible broader rules revision — mentioned 2026-10-01, no detail yet, Jason to scope whenever ready.
- [ ] LBA Stage 0.5 — Lore Builder, cloning/attribution, NPC/PC-level publishing, moderation. Fully designed in the plan doc, deliberately paused — see sequencing decision above.
- [ ] LBA Stage 1 — lightweight reactions, SW/admin-curated "featured" picks, character-concept browser. Gate: ~25-50 published entries (soft, not a hard wall — real demand overrides the number). Comes after Stage 0.5, not before.
- [ ] Social & friends — follow players, friend activity feed
- [ ] GO ID — cross-game identity + achievement trophy case spanning GameOctane's projects (TBA, a Godot RPG, FlipperRPG, others still early). Discord becomes one optional *linked* identity (server role while in a live session, DM notifications), never a login method. Concept stage only — see "Strategic picture" above.
- [ ] Age-gated experience — dual-mode (Tools for the Bad Ass / Tools for Being Awesome)
- [x] Environmental damage tier system — SW "Env Check" tool (v3.0 tiers, players
      roll to resist, can trigger The Calling). Replaced the /env command. Also
      shipped: multi-target Stat Checks. Achievement placeholder names still TBD.

### Called status — known gaps (small, optional; core mechanic is done)
- No escalating trigger cadence by `times_called` — rulebook says 1st Calling = rests only, 2nd = rests+adventuring, 3rd-4th = +battle. App has one manual SW "Called Check" button, usable anytime regardless of count.
- The Called Check's ±1 result is narrative-only — never mechanically applied to a subsequent roll. No wiring to the Tether/Active-Effects modifier system.
- No nightmare/vision flavor-text table — one static sentence per outcome (nightmare/peaceful/vision) rather than a bank of prompts to roll from.
- Cosmetic: `Character.is_called`/`times_called` column comments in `backend/models.py:227-228` say "summoned" (stale, reused-column leftover).
- `backend/achievements.py:819-822` "Death Knows My Name" (survive Calling ×5) is unreachable — the 5th Calling is always permadeath (no roll offered). Dead achievement, needs renaming/retiring or the condition changed to ×4.

## Blockers
Nothing hard blocking. Ascension is blocked on Jason's NPC/Ally leveling design (not a technical blocker). GO ID is concept-stage, blocked on nothing but scoping time. Everything else is ordinary implementation work.

## Resume here
**Ascension levels 11-15 is next** — do not jump to LBA Stage 0.5 even
though it's fully designed, see the sequencing decision above. Resume once
Jason shares his NPC/Ally leveling write-up; full technical inventory
(every level-10-cap site in the codebase) is already done in the plan doc,
so that session should move straight from his design doc to a file-by-file
plan, not need to re-research the codebase.

First file to open: none yet — waiting on Jason's Ascension write-up.

## Last session
2026-10-01: Pushed LBA Stage 0 to `main`. Designed Stage 0.5 (Lore Builder,
cloning/attribution, NPC/PC-level publishing, moderation) in full, including
a security/bug-risk pass per Jason's explicit request — see the plan doc.
Then deliberately decided *not* to build it next — see "Deliberate
sequencing decision" above. Order going forward: Ascension → possible rules
revision → LBA Stage 0.5.

2026-09-30: Built LBA Stage 0 — see "What's shipped" above and the plan doc (`C:\Users\jgermino\.claude\plans\hashed-seeking-pudding.md`, LBA section) for the full staged roadmap (Stage 1 curation, Stage 2 social/spectating, Stage 3 monetization, and a separate ungated AI-Game-Master track). Scope grew substantially through live back-and-forth with Jason before any code was written — worth reading the plan doc's revision history for why the data model ended up shaped the way it did (structured fields over freeform prose, real linked NPCs/items over copied text, the story-vs-lore visibility split caught and fixed mid-build). Verified end-to-end via real Playwright browser runs, not just unit tests.

2026-09-29: Shipped email digest notifications (your-turn/@mention, max 2/day, live turn-revalidation, opt-out), then a bug/security audit over everything since the last security pass (found + fixed a High-severity account-takeover hole plus 6 more correctness bugs — see memory `email-digest-notifications.md` for full detail), then Ally auto-Combo. Adopted a standing practice going forward (memory `bug-audit-cadence.md`): adversarial self-review while writing code that touches auth/tokens, new endpoints, data visibility, Postgres-vs-SQLite-sensitive code, or shared invariants — not just an after-the-fact audit — plus a before/after report for each such change so Jason can see what was actually checked. Also discussed and roughed out "GO ID," a cross-game identity/achievement concept spanning GameOctane's game portfolio (see "Strategic picture") — concept stage, not scoped.

2026-09-28: Audited three "Next up" items marked incomplete and found all three already shipped in prior sessions (grief tether weight, Triple Combo, The Called status system) — `PROJECT_STATUS.md` had drifted from the code. Corrected this doc accordingly; real gaps in The Called system are small and optional (listed above). Scoped Ascension levels 11-15, then paused it at Jason's request pending his NPC/Ally leveling design. Prior session (2026-09-25) shipped a mobile/desktop UI pass (phone header ⋯ menu, one-row chat toolbar, sidebar merged into Session/Campaign tabs, initiative round counter) and cleaned up test data that had leaked into the production DB during browser testing — see memory `sidebar-session-redesign.md` and `no-test-data-in-prod.md` for full detail.
