---
phase: active
priority: high
category: app
progress: 72
focus: "Post-launch polish — analytics, Combo rules, grief tether fix"
next_milestone: "Grief tether weight SW-selectable + Combo cancellation rule"
milestone_distance: days
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

Shipping the remaining Combo rules (cancellation, triple) and grief tether fixes makes the game fully v3.0-spec-compliant. Ascension levels 11-15 and social features are the next unlock after that.

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

## Next up
- [ ] Fix grief tether weight — `routes/bonds.py:183` hardcodes -1; needs SW-selectable weight input in break-bond modal
- [ ] Combo cancellation rule — if proposer takes damage before combo fires → cancel; acceptor takes turn normally (`campaign_websocket.py`)
- [ ] Triple Combo — all 3 hold; fires on last acceptor's turn in initiative order; requires bilateral Bonds + all at L10+
- [ ] Ally auto-Combo — character + Ally get one Combo automatically at creation (not yet wired)
- [ ] The Called status system — death counter (1st-5th), nightmare/vision 1d6 table per rest
- [ ] Ascension levels 11-15 — rules locked; app level cap is currently 10; stats: L11 60DP/+5/+6 → L15 80DP/+7/+8
- [ ] Social & friends — follow players, friend activity feed
- [ ] Discord integration — account linking, community server role
- [ ] Age-gated experience — dual-mode (Tools for the Bad Ass / Tools for Being Awesome)
- [ ] Environmental damage tier system — SW hazard damage tool
- [ ] Lore & asset library — taggable homebrew content

## Blockers
Nothing hard blocking. All pending items are implementation work. Grief tether and Combo cancellation are small (hours). Triple Combo and Ascension are larger (days each).

## Resume here
**Immediate**: Fix grief tether weight in `routes/bonds.py:183`. The `break_bond` endpoint applies a hardcoded `"modifier": -1` for grief tether. The rules say "The SW sets the weight based on how significant the Bond was." Add a `weight` param to the break-bond request body and a numeric input to the break-bond modal in `game.html`.

**Then**: Combo cancellation in `campaign_websocket.py` — when a holding proposer takes damage (DP update WS message), check if `_pendingComboId` is set for that character, and if so cancel the combo and reset the acceptor's hold status.

**Then**: Triple Combo WS flow — extend `pending_combos` table with a second acceptor slot and add the triple-hold state machine.

First file to open: `routes/bonds.py` line 183.

## Last session
2026-06-26: Added Umami analytics (all 11 HTML pages). Fixed missing Lucide icons on campaign cards — `renderMyCampaigns()` wasn't calling `lucide.createIcons()` after injecting HTML. v3.0 Core Rules confirmed published to itch.io and Reddit. Bonds + Combo system fully deployed.
