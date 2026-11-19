# Admin center and safety tools plan

Status: decisions made 2026-11-19. Phase A in progress. Jason is the only admin (`ADMIN_USER_IDS`), so no roles are needed yet.

## Why

A live community needs a way to handle problem players and to hear about bugs. Today there is no report-a-player button, no bug report, and
**Story Weavers cannot remove a player** (the only removal is a player leaving by choice). An account can't be suspended either: login and API
calls already reject `users.is_active = false`, but nothing sets it, and the live chat connection does not check it.

## Decisions (Jason, 2026-11-19)

1. **Privacy boundary.** The admin does not browse private messages. Evidence arrives through a report: the reported message plus surrounding
   lines. For harassment the admin can open the full conversation between the reporter and the reported person (whispers included), but only
   from inside that report, and every opening is written to an audit log. The report form says the admin may review the conversation involved.
2. **Two kinds of removal.** Table level: a Story Weaver can remove a player, optionally banning them from that campaign (a banned player
   cannot rejoin with the join code). Account level: the admin can suspend an account.
3. **Admin: only Jason.**
4. **Tell the Story Weaver when someone leaves** ("so and so left your campaign") with what they need to plan: which character, whether it is in
   the current encounter, and a way to deal with it. A leave already sends a toast and a push; this adds a lasting in-app notification with details.
5. **When a player is removed, their character** becomes an NPC the Story Weaver controls by default (uses the existing convert-to-NPC), with a
   choice to leave it as it is. (Jason said "I like that" to the NPC suggestion; confirm when it ships.)

## Phases (each shipped separately, with tests)

- **A. Table-level safety.** Richer "player left" notification (bell entry with the character and encounter details); Story Weaver
  "Remove player" and "Ban from this campaign" (`campaign_bans`, migration 040); the removed player's live connection is closed; the join
  code refuses a banned player.
- **B. Reports and the inbox.** "Report a player or message" and "Report a bug" buttons; an admin inbox page with statuses, notes, the
  evidence view (report-linked access only) and an audit log; email to `MODERATION_EMAIL`. Builds on `routes/moderation.py` and `admin-reports.html`.
- **C. Account suspension.** Admin can suspend an account; the live chat connection checks `is_active` too, so an open session is cut off.
- **D. Messaging.** Admin can send a push and email to a player or a whole campaign, with saved templates.
- **E. Security events and server errors.** Counters for blocked signups, failed logins, rate-limit hits; a feed of unhandled server errors.
- **F. System status.** Last backup, latest uptime result, deployed version, campaign health.

## Rules to keep

- No usage numbers on logged-out pages. The admin center is admin-only.
- Reporter identity is visible to the admin only, never to the reported person.
- Every admin action and every evidence view is logged.
- No em-dashes in user-facing copy.
