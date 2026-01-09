# Testing Character Caching on Railway

Guide for testing the mention parser and character caching system via Railway hosting.

## Prerequisites

1. **Run Migration** (if not already done):
   ```powershell
   # Local
   $env:API_KEY = 'devkey'
   python backend/migrations/001_add_sw_and_npcs.py
   ```

2. **Create Test Data** (via Swagger UI or API):
   - Create a Party
   - Create a Character and join the party
   - Note the `character_id` (UUID) - you'll need this for testing

---

## Test 1: Legacy Connection (No Character ID)

**What this tests:** Backward compatibility - connections without character caching

### Steps:

1. Open Railway test page:
   ```
   https://tba-app-production.up.railway.app/ws-test
   ```

2. Fill in connection details:
   - **Railway Base URL**: `https://tba-app-production.up.railway.app`
   - **Party ID**: `test-party`
   - **Actor**: `Alice`
   - **Role**: `Player`
   - **Character ID**: *Leave empty*
   - **API Key**: `devkey` (or your Railway API key)

3. Click **Connect**

4. Expected behavior:
   - Connection succeeds
   - No join notification (because no character_id provided)
   - Legacy actor name used in messages

5. Test macros:
   ```
   /roll 3d6+2
   /pp
   /initiative
   ```

6. Expected: Macros work with placeholder stats (Edge=1)

---

## Test 2: Connection With Character Caching

**What this tests:** Character stat caching and role detection

### Steps:

1. Get a Character UUID:
   ```bash
   # Via Swagger UI: GET /api/characters
   # Or via API:
   curl https://tba-app-production.up.railway.app/api/characters \
     -H "X-API-Key: devkey"
   ```

2. Open Railway test page:
   ```
   https://tba-app-production.up.railway.app/ws-test
   ```

3. Fill in connection details:
   - **Railway Base URL**: `https://tba-app-production.up.railway.app`
   - **Party ID**: `test-party` (use the party ID your character belongs to)
   - **Actor**: *Leave empty or set to character name*
   - **Role**: `Player`
   - **Character ID**: `<paste-your-character-uuid>`
   - **API Key**: `devkey`

4. Click **Connect**

5. Expected behavior:
   - Connection succeeds
   - Join notification appears: **"Alice (player) joined the party"**
   - Actor name automatically set to character name

6. Check cached data:
   ```bash
   curl https://tba-app-production.up.railway.app/api/chat/party/test-party/connections \
     -H "X-API-Key: devkey"
   ```

   Expected response:
   ```json
   {
     "party_id": "test-party",
     "connection_count": 1,
     "connections": [
       {
         "character_id": "char-uuid",
         "character_name": "Alice",
         "role": "player"
       }
     ],
     "story_weaver_id": null,
     "cached_characters": ["char-uuid"]
   }
   ```

---

## Test 3: Story Weaver Role Detection

**What this tests:** Automatic SW role assignment based on party.story_weaver_id

### Steps:

1. Set a character as Story Weaver (via API or Swagger):
   ```bash
   # Update party to set story_weaver_id
   curl -X PATCH https://tba-app-production.up.railway.app/api/parties/{party_id} \
     -H "X-API-Key: devkey" \
     -H "Content-Type: application/json" \
     -d '{"story_weaver_id": "your-character-uuid"}'
   ```

2. Connect with that character's ID:
   - **Character ID**: `<story-weaver-character-uuid>`

3. Expected behavior:
   - Join notification: **"Alice (SW) joined the party"**
   - Role automatically detected as SW

4. Check connections endpoint:
   ```json
   {
     "connections": [
       {
         "character_id": "char-uuid",
         "character_name": "Alice",
         "role": "SW"
       }
     ],
     "story_weaver_id": "char-uuid"
   }
   ```

---

## Test 4: Multiple Connections

**What this tests:** Multiple players connecting simultaneously with caching

### Steps:

1. Open **two browser tabs** to the test page

2. **Tab 1** - Connect as Player:
   - **Character ID**: `character-1-uuid`
   - **Actor**: `Alice`

3. **Tab 2** - Connect as SW:
   - **Character ID**: `character-2-uuid` (the SW)
   - **Actor**: `Bob`

4. Expected in both tabs:
   - "Alice (player) joined the party"
   - "Bob (SW) joined the party"

5. Check connections:
   ```bash
   curl https://tba-app-production.up.railway.app/api/chat/party/test-party/connections \
     -H "X-API-Key: devkey"
   ```

   Expected:
   ```json
   {
     "connection_count": 2,
     "connections": [
       {"character_name": "Alice", "role": "player"},
       {"character_name": "Bob", "role": "SW"}
     ],
     "cached_characters": ["char-1-uuid", "char-2-uuid"]
   }
   ```

---

## Test 5: Mention Parser (Manual API Test)

**What this tests:** @mention resolution for future `/attack @target` macros

### Setup:

1. Create test data:
   - Party: `test-party`
   - Character: `Alice`
   - NPC: `Goblin` (in the same party)

### Test via Python:

```python
from backend.db import SessionLocal
from backend.mention_parser import parse_mentions, MentionParseError

db = SessionLocal()
party_id = "your-party-uuid"

# Test 1: Valid mention
mentions = parse_mentions("/attack @goblin", party_id, db)
print(mentions)
# Expected: [{"id": "npc-uuid", "name": "Goblin", "type": "npc"}]

# Test 2: Case-insensitive
mentions = parse_mentions("/attack @GOBLIN", party_id, db)
print(mentions)
# Expected: Same as above

# Test 3: Not found
try:
    mentions = parse_mentions("/attack @unknownname", party_id, db)
except MentionParseError as e:
    print(f"Error (expected): {e}")
    # Expected: "@unknownname not found in party. Use /who to see available characters and NPCs."

# Test 4: Multiple mentions
mentions = parse_mentions("/attack @goblin and @alice", party_id, db)
print(mentions)
# Expected: [{"id": "npc-uuid", "name": "Goblin", "type": "npc"}, {"id": "char-uuid", "name": "Alice", "type": "character"}]

db.close()
```

---

## Test 6: Character Cache Invalidation

**What this tests:** Cache cleanup on disconnect

### Steps:

1. Connect with character_id
2. Verify character is cached (via connections endpoint)
3. Disconnect
4. Check connections endpoint again

Expected:
- After disconnect, `cached_characters` array should be empty
- `connection_count` should be 0
- Party should be cleaned up from in-memory cache

---

## Test 7: NPC Connection (SW Only)

**What this tests:** SW can connect as an NPC to test NPC stats

### Prerequisites:
- Create an NPC via API (SW-only operation)
- Note the NPC's UUID

### Steps:

1. Connect as SW first (to have permission)
2. Then connect with:
   - **Character ID**: `<npc-uuid>`
   - Expected: NPC stats cached, role shows "SW" if creator

---

## Expected WebSocket URLs

### Legacy (no character):
```
wss://tba-app-production.up.railway.app/api/chat/party/test-party?api_key=devkey
```

### With Character Caching:
```
wss://tba-app-production.up.railway.app/api/chat/party/test-party?character_id=char-uuid&api_key=devkey
```

### Minimal (just character):
```
wss://tba-app-production.up.railway.app/api/chat/party/test-party?character_id=char-uuid
```

---

## Troubleshooting

### Character not found
- **Error in logs**: "Failed to cache character {id}"
- **Cause**: Character ID doesn't exist or not in party
- **Fix**: Verify character UUID via `/api/characters` endpoint

### Role not detected as SW
- **Symptom**: Shows "player" instead of "SW"
- **Cause**: `party.story_weaver_id` doesn't match character_id
- **Fix**: Update party via PATCH `/api/parties/{id}` with correct `story_weaver_id`

### Cache not clearing
- **Symptom**: Connections endpoint still shows cached characters after disconnect
- **Cause**: Multiple tabs open or WebSocket not cleanly closed
- **Fix**: Close all tabs, wait 10 seconds, check again

### Migration not run
- **Error**: Column 'story_weaver_id' doesn't exist
- **Fix**: Run migration: `python backend/migrations/001_add_sw_and_npcs.py`

---

## Next Steps After Testing

Once character caching is verified working:

1. **Wire existing macros** to use cached stats:
   - Update `/pp`, `/ip`, `/sp`, `/initiative` to use real Edge/BAP values

2. **Implement combat macros**:
   - `/attack @target` - Uses mention parser + cached stats
   - `/defend @attacker` - Defensive actions

3. **SW-only macros**:
   - `/spawn NpcName level=2 pp=3 ip=1 sp=2`
   - `/hide @npc` - Set visible_to_players=False
   - `/reveal @npc` - Set visible_to_players=True

4. **Utility macros**:
   - `/who` - List all party members and NPCs
   - `/stats @name` - Show character/NPC stats
   - `/heal @target 10` - Restore DP

All of these will leverage the character cache and mention parser system you just tested!
