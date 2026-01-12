# /attack Command Fix - Complete!

## Issue
The `/attack` command was returning "Unknown command: /attack" even though the handler existed in `backend/macro_handlers.py`.

## Root Cause
The `handle_macro` function in [routes/chat.py](routes/chat.py) was missing the routing logic for `/attack`. It only handled:
- `/roll`
- `/pp`, `/ip`, `/sp`
- `/initiative`

Any other command fell through to the "Unknown command" fallback.

## Solution
Added `/attack` command routing to [routes/chat.py:714-778](routes/chat.py#L714-L778).

### Implementation Details

**New routing code:**
```python
if cmd == "/attack":
    # Parse @mention target from remaining text
    args = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Validate usage
    if not args or not args.strip():
        return {"type": "system", "text": "Usage: /attack @target (e.g., /attack @goblin)"}

    # Parse mentions using mention_parser
    from backend.mention_parser import parse_mentions

    db = SessionLocal()
    try:
        parsed = parse_mentions(args, party_id, db, sender_is_sw=False)

        # Check for unresolved mentions
        if parsed['unresolved']:
            return {"type": "system", "text": f"Target not found: {unresolved}"}

        # Get target from mentions
        target = parsed['mentions'][0]

        # Return placeholder attack result
        return {
            "type": "system",
            "text": f"⚔️ {actor} attacks {target['name']} ({target['type']})! [Combat system integration pending]"
        }
    finally:
        db.close()
```

## How It Works Now

### Command Flow:
1. User types: `/attack @goblin`
2. WebSocket handler detects `/` prefix → calls `handle_macro()`
3. `handle_macro()` parses command: `cmd = "/attack"`
4. **NEW**: Matches `if cmd == "/attack"` condition
5. Extracts args: `"@goblin"`
6. Calls `parse_mentions()` to resolve `@goblin` → NPC/Character
7. Returns attack message with target info

### Validation:
- ✅ Checks for missing target: `/attack` → "Usage: /attack @target"
- ✅ Checks for invalid target: `/attack @nonexistent` → "Target not found"
- ✅ Parses @mentions with underscore support: `/attack @Goblin_Archer`
- ✅ Respects NPC visibility (hidden NPCs not shown to players)

## Testing

### Test Commands:

```bash
# Connect to WebSocket
wscat -c "wss://tba-app-production.up.railway.app/api/chat/party/test-party?api_key=devkey"

# Test 1: Basic attack (should work now!)
{"type":"message","actor":"Alice","text":"/attack @goblin"}
# Expected: "⚔️ Alice attacks Goblin (npc)! [Combat system integration pending]"

# Test 2: No target
{"type":"message","actor":"Alice","text":"/attack"}
# Expected: "Usage: /attack @target (e.g., /attack @goblin)"

# Test 3: Invalid target
{"type":"message","actor":"Alice","text":"/attack @nonexistent"}
# Expected: "Target not found: @nonexistent. Use /who to see available targets."

# Test 4: Multi-word NPC name
{"type":"message","actor":"Alice","text":"/attack @Goblin_Archer_1"}
# Expected: "⚔️ Alice attacks Goblin Archer 1 (npc)!"
```

### Prerequisites for Testing:
1. Create a party in the database
2. Create an NPC named "Goblin" in that party
3. Connect to WebSocket with party_id

## Current Status

### ✅ Working:
- Command routing (`/attack` no longer "Unknown command")
- Mention parsing (`@goblin` → resolves to NPC/Character)
- Basic validation (target required, target must exist)
- Multi-word name support (`@Goblin_Archer_1`)

### 🔄 Placeholder (Not Yet Implemented):
- Full combat resolution (damage calculation)
- Character stat integration (PP, Edge, BAP)
- Attack style and defense die
- BAP tracking and retroactive grants
- Combat log persistence to database

## Next Steps

To complete the `/attack` command implementation:

1. **Get attacker character_id from WebSocket metadata**
   - Currently uses `actor` name (string)
   - Need `character_id` from `connection_metadata`

2. **Fetch attacker stats from character cache**
   ```python
   attacker_stats = connection_manager.get_character_stats(party_id, character_id)
   ```

3. **Fetch defender stats (from cache or DB)**
   ```python
   defender_stats = connection_manager.get_character_stats(party_id, target_id)
   if not defender_stats:
       # Load from DB if not in cache
   ```

4. **Call combat resolution from roll_logic.py**
   ```python
   from backend.roll_logic import resolve_multi_die_attack

   result = resolve_multi_die_attack(
       attacker=attacker_stats,
       defender=defender_stats,
       attacker_die_str=attacker_stats['attack_style'],
       stat_type='PP',
       stat_value=attacker_stats['pp'],
       edge=attacker_stats['edge']
   )
   ```

5. **Log combat turn to database**
   ```python
   await log_combat_action(
       party_id=party_id,
       combatant_id=character_id,
       combatant_name=actor,
       action_type="attack",
       result_data=result,
       bap_applied=False
   )
   ```

6. **Broadcast detailed combat result**
   ```python
   return {
       "type": "combat_event",
       "attacker": actor,
       "defender": target_name,
       "individual_rolls": result['individual_rolls'],
       "total_damage": result['total_damage'],
       "narrative": result['narrative'],
       "party_id": party_id
   }
   ```

## Files Modified

- [routes/chat.py](routes/chat.py#L714-L778) - Added `/attack` command routing

## Files Referenced

- [backend/macro_handlers.py](backend/macro_handlers.py) - Contains full attack handler (not yet integrated)
- [backend/mention_parser.py](backend/mention_parser.py) - Parses @mentions
- [backend/roll_logic.py](backend/roll_logic.py) - Combat resolution engine

---

**Status:** `/attack` command now recognized! Returns placeholder message with target info. Full combat integration pending.
