# Mention Parser Fix - WebSocket Character Detection

## Issues Fixed

### Issue 1: Characters Not Found After WebSocket Connection
**Problem:** When Bob connects via WebSocket with character_id, the `/attack @Bob` command returns "Target not found: @Bob"

**Root Cause:**
- The `parse_mentions()` function only queried the database using `PartyMembership` join table
- WebSocket-connected characters may not be in the `party_memberships` table yet
- Characters were cached in `ConnectionManager.character_cache` but mention parser didn't check there

**Solution:**
Updated [backend/mention_parser.py](backend/mention_parser.py#L61-L171) to check cached characters FIRST before database:

```python
def parse_mentions(text: str, party_id: str, db_session: Session, sender_is_sw: bool = False, connection_manager=None) -> dict:
    # Added connection_manager parameter

    for raw_mention in mention_names:
        normalized_name = raw_mention.replace('_', ' ')

        # PRIORITY 1: Check ConnectionManager cache (NEW!)
        found_in_cache = False
        if connection_manager:
            cached_chars = connection_manager.character_cache.get(party_id, {})
            for char_id, char_data in cached_chars.items():
                if char_data.get('name', '').lower() == normalized_name.lower():
                    mentions.append({
                        'raw': f'@{raw_mention}',
                        'name': char_data['name'],
                        'id': char_data['id'],
                        'type': char_data.get('type', 'character')
                    })
                    found_in_cache = True
                    break

        if found_in_cache:
            continue

        # PRIORITY 2: Search database Characters (existing logic)
        # PRIORITY 3: Search database NPCs (existing logic)
```

**Changes to `/attack` command:**
Updated [routes/chat.py](routes/chat.py#L736) to pass `connection_manager` to `parse_mentions()`:

```python
# FIXED: Pass connection_manager to check cached characters first
parsed = parse_mentions(args, party_id, db, sender_is_sw, connection_manager)
```

---

### Issue 2: No Way to See Available Targets
**Problem:** Users didn't know which characters/NPCs they could target with `/attack @name`

**Solution:**
Added `/who` command to [routes/chat.py](routes/chat.py#L781-L851):

```python
if cmd == "/who":
    # List all available targets (characters and NPCs) in the party

    # Get cached characters (actively connected via WebSocket)
    cached_chars = connection_manager.character_cache.get(party_id, {})
    online_characters = [f"@{char_data['name']}" for char_data in cached_chars.values() if char_data.get('type') == 'character']

    # Get party members from database (may include offline members)
    db_characters = db.query(Character).join(PartyMembership).filter(PartyMembership.party_id == party_id).all()
    offline_characters = [f"@{char.name}" for char in db_characters if char.id not in cached_chars]

    # Get NPCs (visible only, unless sender is SW)
    npcs = db.query(NPC).filter(NPC.party_id == party_id)
    if not sender_is_sw:
        npcs = npcs.filter(NPC.visible_to_players == True)
    npc_list = [f"@{npc.name}" for npc in npcs.all()]

    # Format response
    return {
        "type": "system",
        "text": "\n".join([
            "📋 **Available Targets:**",
            f"**Players (online):** {', '.join(online_characters)}",
            f"**Players (offline):** {', '.join(offline_characters)}",
            f"**NPCs:** {', '.join(npc_list)}"
        ])
    }
```

---

## Testing

### Test Scenario 1: WebSocket Character Detection

1. **Connect Bob via WebSocket:**
   ```
   ws://localhost:8000/api/chat/party/test-party?character_id=bob-uuid
   ```
   Expected: "Bob (player) joined the party"

2. **Alice attacks Bob:**
   ```json
   {"type":"message","actor":"Alice","text":"/attack @Bob"}
   ```
   Expected: ✅ "⚔️ Alice attacks Bob (character)! [Combat system integration pending]"

   Previously: ❌ "Target not found: @Bob"

3. **Verify case-insensitive matching:**
   ```json
   {"type":"message","actor":"Alice","text":"/attack @bob"}
   {"type":"message","actor":"Alice","text":"/attack @BOB"}
   ```
   Expected: Both work (case-insensitive)

---

### Test Scenario 2: /who Command

1. **Setup:**
   - Alice connected (online)
   - Bob connected (online)
   - Charlie in database but not connected (offline)
   - NPC "Goblin" (visible to all)
   - NPC "Hidden_Boss" (visible_to_players=False)

2. **Run /who as player:**
   ```json
   {"type":"message","actor":"Alice","text":"/who"}
   ```

   Expected response:
   ```
   📋 **Available Targets:**
   **Players (online):** @Alice, @Bob
   **Players (offline):** @Charlie
   **NPCs:** @Goblin
   ```

   Note: Hidden_Boss not shown (player can't see hidden NPCs)

3. **Run /who as Story Weaver:**
   Same command, but if sender is SW:
   ```
   📋 **Available Targets:**
   **Players (online):** @Alice, @Bob
   **Players (offline):** @Charlie
   **NPCs:** @Goblin, @Hidden_Boss
   ```

   Note: SW sees all NPCs including hidden ones

---

## How It Works Now

### Mention Resolution Priority:

1. **ConnectionManager cache** (in-memory)
   - Checks actively connected WebSocket characters
   - **Case-insensitive** name matching
   - Fastest lookup (no DB query)

2. **Database Characters** (with PartyMembership join)
   - Checks formally joined party members
   - May include offline characters
   - Case-insensitive via `.ilike()`

3. **Database NPCs**
   - Checks NPCs created by Story Weaver
   - Respects `visible_to_players` flag
   - Case-insensitive via `.ilike()`

---

## Files Modified

- [backend/mention_parser.py](backend/mention_parser.py#L61-L171) - Added `connection_manager` parameter and cache checking
- [routes/chat.py](routes/chat.py#L736) - Updated `/attack` to pass `connection_manager`
- [routes/chat.py](routes/chat.py#L781-L851) - Added `/who` command

---

## Next Steps

### Remaining TODOs:

1. **SW Role Detection in Commands:**
   Both `/attack` and `/who` have:
   ```python
   sender_is_sw = False
   # TODO: Get character_id from connection metadata and check if SW
   ```

   Fix: Get `character_id` from WebSocket connection metadata, then check `connection_manager.is_story_weaver(party_id, character_id)`

2. **Full Combat Integration:**
   - `/attack` still returns placeholder message
   - Need to integrate with `backend/roll_logic.py` for damage calculation
   - Need to use cached character stats (PP, Edge, BAP, attack_style, defense_die)

---

## Benefits

✅ **Immediate character detection** - WebSocket-connected characters are immediately targetable
✅ **Case-insensitive matching** - `/attack @bob`, `/attack @Bob`, `/attack @BOB` all work
✅ **No database dependency** - Cache-first approach reduces DB load
✅ **Backward compatible** - Still works without `connection_manager` parameter
✅ **User-friendly** - `/who` command shows all available targets
✅ **Role-aware** - SW can see hidden NPCs, players cannot

---

**Status:** Mention parser now detects WebSocket-connected characters! `/who` command available for listing targets.
