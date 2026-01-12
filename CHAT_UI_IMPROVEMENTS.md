# Chat UI Improvements - Command Echo & Better Formatting

## Summary

Improved the WebSocket chat UI to display user commands before results and format different message types with visual distinction.

## Problem

**Before:**
- User types `/roll 2d6+3` → Only sees result, not what they typed
- User types `/attack @Bob` → Only sees system message, not their command
- All messages looked similar (hard to distinguish commands from results)
- No visual hierarchy or grouping

**After:**
- User types `/roll 2d6+3` → Sees their command in green box, then formatted roll result below
- User types `/attack @Bob` → Sees their command in green box, then formatted attack card below
- Clear visual distinction between user commands, system messages, rolls, and attacks
- Results are clearly associated with the commands that triggered them

---

## Files Modified

### 1. [static/ws-test.html](static/ws-test.html)

---

## Changes Made

### 1. **CSS Additions** (Lines 25-130)

Added comprehensive styling for different message types:

#### User Command Echo Style
```css
.user-command {
  background: #f5f5f5;
  border-left: 3px solid #4CAF50;
  padding: 6px 10px;
  margin: 6px 0 2px 0;
  border-radius: 2px;
  font-family: monospace;
}
```

#### Roll Result Card Style
```css
.roll-result {
  background: #e8f5e9;
  border-left: 4px solid #2196F3;
  padding: 10px;
  margin: 2px 0 8px 0;
  border-radius: 2px;
}
```

#### Attack Result Card Style
```css
.attack-result {
  background: #fff3e0;
  border-left: 4px solid #ff5722;
  padding: 10px;
  margin: 2px 0 8px 0;
  border-radius: 2px;
}
```

#### System Message Style
```css
.system-message {
  background: #fafafa;
  border-left: 3px solid #999;
  padding: 6px 10px;
  margin: 4px 0;
  border-radius: 2px;
  color: #666;
  font-style: italic;
}
```

#### Chat Message Style
```css
.chat-message {
  background: #fff;
  border-left: 3px solid #2196F3;
  padding: 6px 10px;
  margin: 4px 0;
  border-radius: 2px;
}
```

---

### 2. **New Display Functions** (Lines 206-316)

#### `displayUserCommand(actor, text)` - Lines 207-223
Displays the user's command/message with green accent (local echo before server response):

```javascript
function displayUserCommand(actor, text) {
  const container = document.createElement('div');
  container.className = 'user-command';

  const actorSpan = document.createElement('span');
  actorSpan.className = 'actor-name';
  actorSpan.textContent = `[${actor}]`;

  const textSpan = document.createElement('span');
  textSpan.className = 'command-text';
  textSpan.textContent = ` ${text}`;

  container.appendChild(actorSpan);
  container.appendChild(textSpan);
  logEl.appendChild(container);
  logEl.scrollTop = logEl.scrollHeight;
}
```

**Example output:**
```
[Alice] /roll 2d6+3
```

---

#### `displayRollResult(actor, formula, breakdown, total)` - Lines 226-258
Formats dice roll results as structured cards:

```javascript
function displayRollResult(actor, formula, breakdown, total) {
  const container = document.createElement('div');
  container.className = 'roll-result';

  const header = document.createElement('div');
  header.className = 'roll-header';
  header.textContent = '🎲 DICE ROLL';
  container.appendChild(header);

  // ... adds formula, breakdown, total sections
}
```

**Example output:**
```
┌─────────────────────
│ 🎲 DICE ROLL
│ Formula: 2d6+3
│ Rolls: (3 + 1) + 3
│ Total: 7
└─────────────────────
```

---

#### `displayAttackResult(attacker, target, targetType, status)` - Lines 261-289
Formats attack commands as structured cards:

```javascript
function displayAttackResult(attacker, target, targetType, status) {
  const container = document.createElement('div');
  container.className = 'attack-result';

  const header = document.createElement('div');
  header.className = 'attack-header';
  header.textContent = '⚔️ ATTACK';
  container.appendChild(header);

  // ... adds attacker, target, status sections
}
```

**Example output:**
```
┌─────────────────────
│ ⚔️ ATTACK
│ Attacker: Alice
│ Target: Bob (character)
│ Status: Combat resolution pending
└─────────────────────
```

---

#### `displaySystemMessage(text)` - Lines 292-298
Displays system messages with gray italic styling:

```javascript
function displaySystemMessage(text) {
  const container = document.createElement('div');
  container.className = 'system-message';
  container.textContent = text;
  logEl.appendChild(container);
  logEl.scrollTop = logEl.scrollHeight;
}
```

**Example output:**
```
Usage: /attack @target (e.g., /attack @goblin)
```

---

#### `displayChatMessage(actor, text)` - Lines 301-316
Displays regular chat messages with blue accent:

```javascript
function displayChatMessage(actor, text) {
  const container = document.createElement('div');
  container.className = 'chat-message';

  const actorSpan = document.createElement('span');
  actorSpan.className = 'actor-name';
  actorSpan.textContent = `[${actor}]`;

  const textSpan = document.createElement('span');
  textSpan.textContent = ` ${text}`;

  container.appendChild(actorSpan);
  container.appendChild(textSpan);
  logEl.appendChild(container);
  logEl.scrollTop = logEl.scrollHeight;
}
```

**Example output:**
```
[Alice] Hello everyone!
```

---

### 3. **Updated Message Handler** (Lines 411-456)

Enhanced `ws.onmessage` to intelligently route different message types to appropriate display functions:

#### System Message Parsing (Lines 416-442)
```javascript
else if (data.type === 'system') {
  const text = data.text || '';

  // Check if it's an attack result
  if (text.includes('⚔️') && text.includes('attacks')) {
    const attackMatch = text.match(/⚔️\s+(.+?)\s+attacks\s+(.+?)\s+\((.+?)\)!\s*(.*)$/);
    if (attackMatch) {
      const [, attacker, target, targetType, status] = attackMatch;
      displayAttackResult(attacker, target, targetType, status.replace(/[\[\]]/g, ''));
    }
  }
  // Check if it's a /who command result
  else if (text.includes('📋') && text.includes('Available Targets')) {
    displaySystemMessage(text);
  }
  // Check if it's a usage/error message
  else if (text.toLowerCase().includes('usage:') || text.toLowerCase().includes('not found')) {
    displaySystemMessage(text);
  }
  // Generic system message
  else {
    displaySystemMessage(text);
  }
}
```

**What it does:**
- Parses attack messages: `"⚔️ Alice attacks Bob (character)! [Status]"` → Attack card
- Detects `/who` results → System message
- Detects errors/usage → System message
- Everything else → Generic system message

#### Roll Result Parsing (Lines 443-456)
```javascript
else if (data.type === 'dice_roll') {
  const formula = data.dice || '';
  const breakdown = Array.isArray(data.breakdown) ? data.breakdown.join(' + ') : '';
  const total = data.result;

  displayRollResult(data.actor, formula, breakdown, total);
}
else if (data.type === 'stat_roll') {
  const formula = data.dice || '';
  const breakdown = Array.isArray(data.breakdown) ? data.breakdown.join(' + ') : '';
  const total = data.result;

  displayRollResult(data.actor, formula, breakdown, total);
}
```

**What it does:**
- Extracts formula, breakdown, and total from roll data
- Passes to `displayRollResult()` for formatting
- Works for both `/roll` and stat rolls (`/pp`, `/ip`, `/sp`)

---

### 4. **Updated Send Button Handler** (Lines 524-546)

Added **local echo** - displays user's command immediately before sending to server:

```javascript
sendBtn.addEventListener('click', () => {
  const text = msgInput.value.trim();
  const actor = actorEl.value.trim() || 'User';
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  // Echo user's command immediately (local echo)
  if (text.startsWith('/')) {
    // It's a command - display it
    displayUserCommand(actor, text);
  } else {
    // Regular chat message - display it
    displayChatMessage(actor, text);
  }

  // Send to server
  const payload = { type: 'message', actor, text };
  // ... rest of send logic
});
```

**What it does:**
1. User types message
2. **Immediately display** in chat (green for commands, blue for messages)
3. Send to server
4. Server response appears below the echoed command

---

## Visual Examples

### Before vs After

#### **Before** - `/roll 2d6+3`:
```
🎲 User (2d6+3): 2d6+3 → (3 + 1) + 3 = 7
```

#### **After** - `/roll 2d6+3`:
```
┌─ [Alice] /roll 2d6+3 ────────────────────────── (green box)
│
└─ 🎲 DICE ROLL ──────────────────────────────── (blue card)
   Formula: 2d6+3
   Rolls: (3 + 1) + 3
   Total: 7
```

---

#### **Before** - `/attack @Bob`:
```
⚔️ User attacks Bob (character)! [Combat system integration pending]
```

#### **After** - `/attack @Bob`:
```
┌─ [Alice] /attack @Bob ──────────────────────── (green box)
│
└─ ⚔️ ATTACK ─────────────────────────────────── (orange card)
   Attacker: Alice
   Target: Bob (character)
   Status: Combat resolution pending
```

---

#### **Before** - `/who`:
```
[system] system: 📋 Available Targets:
Players (online): @Alice, @Bob
NPCs: @Goblin
```

#### **After** - `/who`:
```
┌─ [Alice] /who ──────────────────────────────── (green box)
│
└─ 📋 Available Targets: ────────────────────── (gray system message)
   Players (online): @Alice, @Bob
   NPCs: @Goblin
```

---

#### **Before** - Regular chat:
```
[message] Alice: Hello everyone!
```

#### **After** - Regular chat:
```
[Alice] Hello everyone! ────────────────────────── (blue chat message)
```

---

## Color Scheme

| Message Type | Border Color | Background | Use Case |
|-------------|-------------|-----------|----------|
| User Command | Green (#4CAF50) | Light gray (#f5f5f5) | Commands typed by user (`/roll`, `/attack`) |
| Roll Result | Blue (#2196F3) | Light green (#e8f5e9) | Dice roll results |
| Attack Result | Orange-red (#ff5722) | Light orange (#fff3e0) | Attack command results |
| System Message | Gray (#999) | Very light gray (#fafafa) | Errors, usage, notifications |
| Chat Message | Blue (#2196F3) | White (#fff) | Regular chat messages |
| Combat Event | Red (#d00) | Light red (#ffe8e8) | Full combat events (existing) |

---

## Benefits

✅ **Improved UX** - Users see what they typed before seeing results
✅ **Visual Hierarchy** - Clear distinction between commands, results, and messages
✅ **Better Context** - Results are visually grouped with the commands that triggered them
✅ **Reduced Confusion** - No more "what did I just do?" moments
✅ **Cleaner Layout** - Structured cards instead of inline text
✅ **Accessible** - Color + border + layout (not just color)

---

## Testing

### Test Scenario 1: Roll Command
1. Type `/roll 2d6+3`
2. Press Send

**Expected:**
```
[Alice] /roll 2d6+3           ← Green command echo
🎲 DICE ROLL                  ← Blue roll card
Formula: 2d6+3
Rolls: (3 + 1) + 3
Total: 7
```

---

### Test Scenario 2: Attack Command
1. Type `/attack @Bob`
2. Press Send

**Expected:**
```
[Alice] /attack @Bob          ← Green command echo
⚔️ ATTACK                     ← Orange attack card
Attacker: Alice
Target: Bob (character)
Status: Combat resolution pending
```

---

### Test Scenario 3: Who Command
1. Type `/who`
2. Press Send

**Expected:**
```
[Alice] /who                  ← Green command echo
📋 Available Targets:         ← Gray system message
Players (online): @Alice, @Bob
NPCs: @Goblin
```

---

### Test Scenario 4: Error Handling
1. Type `/attack` (no target)
2. Press Send

**Expected:**
```
[Alice] /attack               ← Green command echo
Usage: /attack @target        ← Gray system message (error)
```

---

### Test Scenario 5: Regular Chat
1. Type `Hello everyone!`
2. Press Send

**Expected:**
```
[Alice] Hello everyone!       ← Blue chat message
```

---

## Future Improvements

### Potential Enhancements:
1. **Timestamps** - Add optional timestamps to messages
2. **User Avatars** - Small avatar/icon next to actor names
3. **Collapsible Roll Details** - Hide/show breakdown (already exists for some rolls)
4. **Command History** - Up arrow to recall previous commands
5. **Autocomplete** - Suggest @mentions as user types
6. **Rich Markdown** - Support bold, italic, code blocks in chat
7. **Message Reactions** - React to messages with emojis
8. **Edit/Delete** - Allow editing/deleting recent messages

---

**Status:** Chat UI improvements complete! Commands are echoed immediately with clear visual formatting for all message types.
