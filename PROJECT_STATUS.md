---
phase: active
priority: high
category: app
progress: 78
focus: "Post-launch polish — mobile UI pass shipped; growth features next"
next_milestone: "Pick one growth feature (social/friends, Discord account linking, age-gated mode, or lore library) and scope it"
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

The game is now fully v3.0-spec-compliant on the rules side — Combo rules (cancellation, triple), grief tether weight, and The Called status system are all shipped and verified against `Rulebook.md`. The mobile/desktop UI also got a real pass (phone header, chat toolbar, sidebar merge) after Jason's own phone testing surfaced crowding issues. Ascension levels 11-15 is scoped but on hold — Jason wants NPCs (and possibly Allies) levelable past 10 too, not just PCs, and is writing up that fuller design before implementation starts. Social/growth features (friends, Discord account linking, age-gated mode, lore library) are the next intentional push.

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

## Next up
- [ ] Ally auto-Combo — character + Ally get one Combo automatically at creation (not yet wired)
- [ ] Ascension levels 11-15 — rules locked for PCs; on hold pending Jason's write-up on whether NPCs/Allies also go past 10 (Allies have their own separate, lower stat table that doesn't extend without new numbers). Also: Triple Combo's level gate is `== 10` in both `campaign_websocket.py` and `game.html` — needs to become `>= 10` whenever Ascension ships, or an Ascended character loses Triple Combo the moment they level past 10.
- [ ] Social & friends — follow players, friend activity feed
- [ ] Discord integration — account linking, community server role (separate from the live campaign→Discord mirror, which already ships)
- [ ] Age-gated experience — dual-mode (Tools for the Bad Ass / Tools for Being Awesome)
- [x] Environmental damage tier system — SW "Env Check" tool (v3.0 tiers, players
      roll to resist, can trigger The Calling). Replaced the /env command. Also
      shipped: multi-target Stat Checks. Achievement placeholder names still TBD.
- [ ] Lore & asset library — taggable homebrew content

### Called status — known gaps (small, optional; core mechanic is done)
- No escalating trigger cadence by `times_called` — rulebook says 1st Calling = rests only, 2nd = rests+adventuring, 3rd-4th = +battle. App has one manual SW "Called Check" button, usable anytime regardless of count.
- The Called Check's ±1 result is narrative-only — never mechanically applied to a subsequent roll. No wiring to the Tether/Active-Effects modifier system.
- No nightmare/vision flavor-text table — one static sentence per outcome (nightmare/peaceful/vision) rather than a bank of prompts to roll from.
- Cosmetic: `Character.is_called`/`times_called` column comments in `backend/models.py:227-228` say "summoned" (stale, reused-column leftover).
- `backend/achievements.py:819-822` "Death Knows My Name" (survive Calling ×5) is unreachable — the 5th Calling is always permadeath (no roll offered). Dead achievement, needs renaming/retiring or the condition changed to ×4.

## Blockers
Nothing hard blocking. Ascension is blocked on Jason's NPC/Ally leveling design (not a technical blocker). Everything else is ordinary implementation work.

## Resume here
Pick a growth feature (social/friends, Discord account linking, age-gated mode, or lore library) and scope it — that's the intentional next push per Jason (2026-09-28). Ally auto-Combo is a good small warm-up if wanted first. Ascension resumes once Jason shares his NPC/Ally leveling write-up — see the Called-status gaps above for optional cleanup that could be folded into whichever session touches Bonds/Calling code next.

First file to open: none picked yet — depends which growth feature gets chosen.

## Last session
2026-09-28: Audited three "Next up" items marked incomplete and found all three already shipped in prior sessions (grief tether weight, Triple Combo, The Called status system) — `PROJECT_STATUS.md` had drifted from the code. Corrected this doc accordingly; real gaps in The Called system are small and optional (listed above). Scoped Ascension levels 11-15, then paused it at Jason's request pending his NPC/Ally leveling design. Prior session (2026-09-25) shipped a mobile/desktop UI pass (phone header ⋯ menu, one-row chat toolbar, sidebar merged into Session/Campaign tabs, initiative round counter) and cleaned up test data that had leaked into the production DB during browser testing — see memory `sidebar-session-redesign.md` and `no-test-data-in-prod.md` for full detail.
