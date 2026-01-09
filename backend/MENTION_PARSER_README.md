# Mention Parser & Character Caching System

Phase 2b implementation for WebSocket chat macros with @mention targeting and character stat caching.

## Overview

This system enables:
- **@mention targeting**: Players can target attacks with `/attack @goblin`
- **Character caching**: Stats loaded on connection, avoiding DB hits per macro
- **Story Weaver tracking**: Automatic role detection (SW vs player)
- **Unique name validation**: Prevent name collisions within parties

---

## Files Created/Modified

### New Files

1. **[backend/mention_parser.py](backend/mention_parser.py)**
   - Core mention parsing and validation logic
   - Reusable across all macro handlers

### Modified Files

1. **[routes/chat.py](routes/chat.py)**
   - Added `ConnectionManager` class with character caching
   - Updated WebSocket endpoint to accept `character_id` parameter
   - Improved connection tracking and metadata management

---

## Mention Parser API

### `parse_mentions(text, party_id, db_session)`

Extract and resolve all @mentions in text.

**Parameters:**
- `text` (str): Message text containing @mentions
- `party_id` (str): Party ID to scope the search
- `db_session` (Session): SQLAlchemy database session

**Returns:**
```python
[
    {"id": "uuid", "name": "Alice", "type": "character"},
    {"id": "uuid", "name": "Goblin", "type": "npc"}
]
```

**Raises:**
- `MentionParseError`: If mention not found or ambiguous

**Example:**
```python
from backend.mention_parser import parse_mentions
from backend.db import SessionLocal

db = SessionLocal()
mentions = parse_mentions("/attack @goblin", party_id, db)
# Returns: [{"id": "npc-uuid", "name": "Goblin", "type": "npc"}]
db.close()
```

---

### `resolve_single_mention(text, party_id, db_session, expected_type=None)`

Stricter version for commands expecting exactly one target.

**Parameters:**
- `text` (str): Message text
- `party_id` (str): Party ID
- `db_session` (Session): Database session
- `expected_type` (Optional[str]): Filter by "character" or "npc"

**Returns:**
```python
{"id": "uuid", "name": "Goblin", "type": "npc"}
```

**Raises:**
- `MentionParseError`: If no mentions, multiple mentions, or type mismatch

**Example:**
```python
from backend.mention_parser import resolve_single_mention, MentionParseError

try:
    target = resolve_single_mention("/attack @goblin", party_id, db, expected_type="npc")
    print(f"Attacking {target['name']}!")
except MentionParseError as e:
    print(f"Error: {e}")
```

---

### `validate_unique_name(name, party_id, db_session)`

Check if a name is unique within a party (for character/NPC creation).

**Parameters:**
- `name` (str): Name to validate
- `party_id` (str): Party ID
- `db_session` (Session): Database session

**Returns:**
- `True` if unique, `False` if name already exists

**Example:**
```python
from backend.mention_parser import validate_unique_name

if validate_unique_name("NewChar", party_id, db):
    # Create character
    pass
else:
    # Name already taken
    pass
```

---

### `get_all_party_names(party_id, db_session)`

Get all character and NPC names in a party (for `/who` command or autocomplete).

**Returns:**
```python
[
    {"id": "char-1", "name": "Alice", "type": "character", "visible": True},
    {"id": "npc-1", "name": "Goblin", "type": "npc", "visible": True},
    {"id": "npc-2", "name": "HiddenBoss", "type": "npc", "visible": False}
]
```

**Example:**
```python
from backend.mention_parser import get_all_party_names

names = get_all_party_names(party_id, db)
for entity in names:
    if entity["visible"]:
        print(f"{entity['name']} ({entity['type']})")
```

---

## ConnectionManager API

### `connection_manager.add_connection(party_id, ws, character_id=None)`

Add a WebSocket connection with character caching.

**Flow:**
1. Fetch character/NPC from database by `character_id`
2. Cache stats (PP, IP, SP, Edge, BAP, DP, etc.)
3. Determine if character is Story Weaver
4. Store connection with metadata

**Example:**
```python
# In WebSocket endpoint
await connection_manager.add_connection(party_id, websocket, character_id)
```

---

### `connection_manager.get_character_stats(party_id, character_id)`

Get cached character stats (avoids DB hit).

**Returns:**
```python
{
    "id": "char-uuid",
    "name": "Alice",
    "type": "character",
    "pp": 3,
    "ip": 2,
    "sp": 1,
    "edge": 2,
    "bap": 3,
    "level": 5,
    "dp": 30,
    "max_dp": 30,
    "attack_style": "3d4",
    "defense_die": "1d8"
}
```

**Example:**
```python
stats = connection_manager.get_character_stats(party_id, character_id)
if stats:
    pp = stats["pp"]
    edge = stats["edge"]
    # Use for macro calculations
```

---

### `connection_manager.get_party_sw(party_id)`

Get the Story Weaver character ID for a party.

**Returns:**
- Character ID (str) or `None`

**Example:**
```python
sw_id = connection_manager.get_party_sw(party_id)
if character_id == sw_id:
    print("You are the Story Weaver!")
```

---

### `connection_manager.is_story_weaver(party_id, character_id)`

Check if a character is the Story Weaver.

**Returns:**
- `True` or `False`

**Example:**
```python
if connection_manager.is_story_weaver(party_id, character_id):
    # Allow SW-only commands like /spawn
    pass
```

---

## WebSocket Connection URL

### Without Character (Legacy)
```
ws://localhost:8000/api/chat/party/test-party
```

### With Character Caching (Phase 2b)
```
ws://localhost:8000/api/chat/party/test-party?character_id=char-uuid-123
```

**Benefits:**
- Automatic role detection (SW or player)
- Character stats cached on connection
- Join/leave notifications with character name
- Ready for `/attack`, `/initiative`, `/pp` macros with real stats

---

## Integration Examples

### Example 1: `/attack` Macro Handler

```python
async def handle_attack_macro(party_id: str, attacker_id: str, text: str, db_session):
    """Handle /attack @target macro."""
    from backend.mention_parser import resolve_single_mention, MentionParseError

    try:
        # Parse target from @mention
        target = resolve_single_mention(text, party_id, db_session)

        # Get attacker stats from cache
        attacker_stats = connection_manager.get_character_stats(party_id, attacker_id)
        if not attacker_stats:
            return {"type": "system", "text": "Error: Your character stats not found"}

        # Get defender stats (from cache or DB)
        defender_stats = connection_manager.get_character_stats(party_id, target["id"])
        if not defender_stats:
            # Not cached (defender not connected) - fetch from DB
            if target["type"] == "character":
                defender = db_session.query(Character).filter(Character.id == target["id"]).first()
            else:
                defender = db_session.query(NPC).filter(NPC.id == target["id"]).first()
            # Convert to stats dict...

        # Use roll_logic to resolve attack
        from backend.roll_logic import resolve_multi_die_attack
        result = resolve_multi_die_attack(
            attacker=attacker_stats,
            defender=defender_stats,
            attacker_die_str=attacker_stats["attack_style"],
            stat_type="PP",
            stat_value=attacker_stats["pp"],
            edge=attacker_stats["edge"]
        )

        return {
            "type": "combat_result",
            "attacker": attacker_stats["name"],
            "defender": target["name"],
            "damage": result["total_damage"],
            "narrative": result["narrative"]
        }

    except MentionParseError as e:
        return {"type": "system", "text": str(e)}
```

---

### Example 2: `/spawn` Macro (SW Only)

```python
async def handle_spawn_macro(party_id: str, character_id: str, text: str, db_session):
    """Handle /spawn NpcName level=2 pp=3 ip=1 sp=2 (SW only)."""
    from backend.mention_parser import validate_unique_name

    # Check if user is Story Weaver
    if not connection_manager.is_story_weaver(party_id, character_id):
        return {"type": "system", "text": "Only the Story Weaver can spawn NPCs"}

    # Parse command: /spawn Goblin level=2 pp=3 ip=1 sp=2
    parts = text.split()
    if len(parts) < 2:
        return {"type": "system", "text": "Usage: /spawn NpcName level=X pp=X ip=X sp=X"}

    npc_name = parts[1]

    # Validate unique name
    if not validate_unique_name(npc_name, party_id, db_session):
        return {"type": "system", "text": f"Name '{npc_name}' already exists in party"}

    # Parse stats from key=value pairs
    # ... (parsing logic)

    # Create NPC in database
    npc = NPC(
        party_id=party_id,
        name=npc_name,
        # ... stats
        created_by=character_id
    )
    db_session.add(npc)
    db_session.commit()

    return {
        "type": "system",
        "text": f"Spawned {npc_name} (Level {npc.level}, {npc.npc_type})"
    }
```

---

### Example 3: `/who` Macro (List Party Members)

```python
async def handle_who_macro(party_id: str, character_id: str, db_session):
    """Handle /who macro - list all party members and NPCs."""
    from backend.mention_parser import get_all_party_names

    is_sw = connection_manager.is_story_weaver(party_id, character_id)

    entities = get_all_party_names(party_id, db_session)
    visible_entities = []

    for entity in entities:
        # Show hidden NPCs only to SW
        if entity["visible"] or is_sw:
            visible_entities.append(f"{entity['name']} ({entity['type']})")

    if not visible_entities:
        return {"type": "system", "text": "No characters or NPCs in party"}

    return {
        "type": "system",
        "text": f"Party members: {', '.join(visible_entities)}"
    }
```

---

## Error Handling

### MentionParseError Examples

```python
# Mention not found
"/attack @unknownname"
→ MentionParseError: "@unknownname not found in party. Use /who to see available characters and NPCs."

# Ambiguous mention (multiple matches)
"/attack @gob"  # Matches "Goblin" and "Goblin2"
→ MentionParseError: "@gob is ambiguous. Found: Goblin (npc), Goblin2 (npc). Please be more specific."

# Wrong type
resolve_single_mention("/attack @alice", party_id, db, expected_type="npc")
→ MentionParseError: "@alice is a character, but this command expects a npc."

# Multiple targets in single-target command
resolve_single_mention("/attack @goblin @orc", party_id, db)
→ MentionParseError: "Multiple targets found: Goblin, Orc. This command expects exactly one target."
```

---

## Testing

### Test Mention Parser

```python
# Run Python shell
python

from backend.db import SessionLocal
from backend.mention_parser import parse_mentions, validate_unique_name

db = SessionLocal()
party_id = "test-party-id"

# Test mention parsing
mentions = parse_mentions("/attack @goblin", party_id, db)
print(mentions)

# Test unique name validation
print(validate_unique_name("NewChar", party_id, db))

db.close()
```

### Test Character Caching

```python
# Connect to WebSocket with character_id
wscat -c "ws://localhost:8000/api/chat/party/test-party?character_id=char-uuid"

# Check connections endpoint
curl http://localhost:8000/api/chat/party/test-party/connections

# Expected response:
{
  "party_id": "test-party",
  "connection_count": 1,
  "connections": [
    {
      "character_id": "char-uuid",
      "character_name": "Alice",
      "role": "SW"
    }
  ],
  "story_weaver_id": "char-uuid",
  "cached_characters": ["char-uuid"]
}
```

---

## Next Steps

With mention parser and character caching in place, you can now implement:

1. **`/attack @target` macro** - Full combat resolution with real stats
2. **`/spawn NpcName` macro** - SW creates NPCs directly from chat
3. **`/who` macro** - List all party members and NPCs
4. **`/stats @name` macro** - Show character/NPC stats
5. **`/heal @target` macro** - Restore DP
6. **Custom macros** - Player-defined shortcuts stored in Character model

All macros will have access to:
- Cached character stats (no DB hit)
- Story Weaver permissions
- @mention resolution
- Real PP/IP/SP/Edge/BAP values for calculations

---

## Architecture Benefits

### Performance
- **Character stats cached on connect** → No DB hit per macro
- **Party metadata cached** → Fast SW role checks
- **In-memory lookups** → Sub-millisecond stat retrieval

### Developer Experience
- **Reusable parser** → Same logic for all macros
- **Type-safe mention resolution** → Clear error messages
- **Backward compatible** → Legacy connections still work

### User Experience
- **Natural targeting** → `/attack @goblin` feels intuitive
- **Automatic role detection** → SW sees hidden NPCs
- **Clear error messages** → "@gob is ambiguous" with suggestions
- **Join/leave notifications** → "Alice (SW) joined the party"

---

## Migration Path

The system is designed for gradual migration:

1. **Phase 1 (Current)**: Mention parser and caching ready
2. **Phase 2**: Update existing macros (`/pp`, `/ip`, `/sp`, `/initiative`) to use cached stats
3. **Phase 3**: Implement combat macros (`/attack`, `/defend`)
4. **Phase 4**: SW-only macros (`/spawn`, `/hide`, `/reveal`)
5. **Phase 5**: Custom macros stored in Character model

All phases maintain backward compatibility with connections that don't provide `character_id`.
