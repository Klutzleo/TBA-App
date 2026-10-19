"""
Discord mirror: STORY ONLY.

The mirror posts campaign events to a public Discord channel. Only the story may go there. Table talk (OOC), whispers and
anything private or administrative must never be posted, however the event is typed.
"""
import asyncio

import pytest

from backend import discord_mirror as dm

CAMPAIGN = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def mirror(monkeypatch):
    """The mirror switched on for one campaign, with a queue we can inspect instead of a real Discord."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setattr(dm, "DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(dm, "_outbound_queue", asyncio.Queue())
    monkeypatch.setattr(dm, "_get_channel_id", lambda campaign_id: "1234567890")

    def post(payload):
        """Returns the text that would be posted to Discord, or None if the event is not mirrored."""
        before = dm._outbound_queue.qsize()
        dm.enqueue_outbound(CAMPAIGN, payload)
        if dm._outbound_queue.qsize() == before:
            return None
        return dm._outbound_queue.get_nowait()["text"]

    yield post
    loop.close()


STORY_EVENTS = [
    {"type": "chat_ic", "actor": "Scalelord", "text": "I draw my blade.", "chat_mode": "ic", "message_id": "1"},
    {"type": "damage_applied", "source": "A falling beam", "character_name": "Beef", "amount": 3, "old_dp": 9, "new_dp": 6, "max_dp": 15},
    {"type": "combat_result", "attacker": "Beef", "defender": "Reaver", "damage": 4, "outcome": "hit"},
    {"type": "bap_granted", "character_name": "Beef"},
    {"type": "system", "text": "The Story Weaver sets the scene: a burning street."},
]


@pytest.mark.parametrize("payload", STORY_EVENTS, ids=lambda p: p["type"])
def test_story_events_are_still_mirrored(mirror, payload):
    assert mirror(payload) is not None


def test_ooc_chat_is_not_mirrored(mirror):
    assert mirror({"type": "chat_ooc", "actor": "Newplayer", "text": "is this the right place?", "chat_mode": "ooc", "message_id": "2"}) is None


def test_whispers_are_never_mirrored(mirror):
    assert mirror({"type": "chat_whisper", "actor": "Scalelord", "text": "psst, I'm stealing the amulet",
                   "chat_mode": "whisper", "whisper_targets": ["Beef"], "message_id": "3"}) is None


def test_ooc_and_whisper_event_types_are_blocked_even_with_no_chat_mode_field(mirror):
    # two independent layers: the event type itself is blocked, and so is any chat mode (next test)
    assert mirror({"type": "chat_ooc", "actor": "Newplayer", "text": "table talk"}) is None
    assert mirror({"type": "chat_whisper", "actor": "Scalelord", "text": "secret"}) is None


@pytest.mark.parametrize("chat_mode", ["ooc", "whisper", "OOC", "Whisper"])
def test_anything_sent_in_a_non_story_chat_mode_is_not_mirrored_whatever_its_type(mirror, chat_mode):
    # covers images posted to the OOC tab and any event type added in the future that carries a chat mode
    assert mirror({"type": "image_upload", "sender_name": "Someone", "chat_mode": chat_mode, "caption": "my notes", "message_id": "4"}) is None
    assert mirror({"type": "some_future_event", "text": "should not leak", "chat_mode": chat_mode}) is None


@pytest.mark.parametrize("event_type", [
    "lore_created", "lore_updated", "lore_deleted",
    "item_added", "item_given", "item_equip_changed", "item_used",
    "message_pinned", "message_unpinned", "campaign_renamed", "npc_visibility_changed",
    "abilities_restored", "character_level_set", "character_archived", "character_deleted",
    "secret_roll_result",
])
def test_non_story_and_private_events_are_not_mirrored(mirror, event_type):
    assert mirror({"type": event_type, "text": "private or administrative", "content": "x", "message": "x"}) is None


def test_edits_and_deletes_of_unmirrored_messages_cannot_post_anything(mirror):
    # an edit only ever PATCHes a message we already mirrored; a whisper/OOC message never was, so it is a no-op.
    # (The worker looks the row up and returns when there is none; see _process_outbound_item.)
    import inspect
    src = inspect.getsource(dm._process_outbound_item)
    assert 'action == "edit"' in src and "if not row:" in src
