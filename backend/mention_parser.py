"""
Mention Parser for WebSocket Chat Macros

Handles @mention resolution for targeting in chat macros like /attack @goblin.

Features:
- Extract @mentions from text (e.g., "@goblin", "@Alice")
- Resolve mentions to Character or NPC IDs
- Case-insensitive matching
- Validate unique names within party scope
- Support for multiple mentions in one message

Usage:
    from backend.mention_parser import parse_mentions, validate_unique_name

    # Parse mentions from chat message
    mentions = parse_mentions("/attack @goblin", party_id, db_session)
    # Returns: [{"id": "uuid", "name": "Goblin", "type": "npc"}]

    # Validate new character name
    is_unique = validate_unique_name("NewChar", party_id, db_session)
"""

import re
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from backend.models import Character, PartyMembership, NPC


class MentionParseError(Exception):
    """Raised when mention parsing fails (ambiguous or not found)."""
    pass


def extract_mentions(text: str) -> List[str]:
    """
    Extract all @mentions from text.

    Supports multi-word names with underscores: @Goblin_Archer_1

    Args:
        text: The message text to parse

    Returns:
        List of mention names (without @ prefix)

    Examples:
        >>> extract_mentions("/attack @goblin with @sword")
        ['goblin', 'sword']
        >>> extract_mentions("@Goblin_Archer_1 attacks")
        ['Goblin_Archer_1']
        >>> extract_mentions("No mentions here")
        []
    """
    # Updated pattern to match @word or @word_word_word
    pattern = r'@(\w+(?:_\w+)*)'
    matches = re.findall(pattern, text)
    return matches


def parse_mentions(text: str, party_id: str, db_session: Session, sender_is_sw: bool = False, connection_manager=None) -> dict:
    """
    Parse @mentions and resolve them to Character or NPC entities.

    Supports multi-word names with underscores: @Goblin_Archer_1 → "Goblin Archer 1"

    Args:
        text: The message text containing @mentions
        party_id: The party ID to scope the search
        db_session: SQLAlchemy database session
        sender_is_sw: Whether sender is Story Weaver (can see hidden NPCs)
        connection_manager: Optional ConnectionManager instance to check cached characters

    Returns:
        {
            'original': original message,
            'mentions': [
                {
                    'raw': '@Goblin_Archer_1',
                    'name': 'Goblin Archer 1',
                    'id': 'uuid-here',
                    'type': 'npc' or 'character'
                }
            ],
            'unresolved': ['@NonexistentName']
        }

    Examples:
        >>> parse_mentions("/attack @goblin", "party-123", session)
        {
            'original': '/attack @goblin',
            'mentions': [{'raw': '@goblin', 'name': 'Goblin', 'id': 'npc-uuid', 'type': 'npc'}],
            'unresolved': []
        }
    """
    mention_names = extract_mentions(text)

    mentions = []
    unresolved = []

    for raw_mention in mention_names:
        # Normalize: replace underscores with spaces for matching
        normalized_name = raw_mention.replace('_', ' ')

        # PRIORITY 1: Check ConnectionManager cache for actively connected characters
        # This fixes the issue where WebSocket-connected characters aren't in PartyMembership yet
        found_in_cache = False
        if connection_manager:
            cached_chars = connection_manager.character_cache.get(party_id, {})
            for char_id, char_data in cached_chars.items():
                if char_data.get('name', '').lower() == normalized_name.lower():
                    # Found in cache!
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

        # PRIORITY 2: Search in Characters (party members in database)
        character = (
            db_session.query(Character)
            .join(PartyMembership, PartyMembership.character_id == Character.id)
            .filter(PartyMembership.party_id == party_id)
            .filter(Character.name.ilike(normalized_name))
            .first()
        )

        if character:
            mentions.append({
                'raw': f'@{raw_mention}',
                'name': character.name,
                'id': character.id,
                'type': 'character'
            })
            continue

        # PRIORITY 3: Search in NPCs (for this party)
        npc_query = db_session.query(NPC).filter(
            NPC.party_id == party_id,
            NPC.name.ilike(normalized_name)
        )

        # If sender is not Story Weaver, only show visible NPCs
        if not sender_is_sw:
            npc_query = npc_query.filter(NPC.visible_to_players == True)

        npc = npc_query.first()

        if npc:
            mentions.append({
                'raw': f'@{raw_mention}',
                'name': npc.name,
                'id': npc.id,
                'type': 'npc'
            })
            continue

        # Not found - add to unresolved
        unresolved.append(f'@{raw_mention}')

    return {
        'original': text,
        'mentions': mentions,
        'unresolved': unresolved
    }


def resolve_single_mention(
    text: str,
    party_id: str,
    db_session: Session,
    expected_type: Optional[str] = None
) -> Dict:
    """
    Parse and resolve a single @mention (stricter version for commands expecting one target).

    Args:
        text: The message text containing exactly one @mention
        party_id: The party ID to scope the search
        db_session: SQLAlchemy database session
        expected_type: Optional filter - "character" or "npc"

    Returns:
        Dict with keys: id, name, type

    Raises:
        MentionParseError: If no mentions, multiple mentions, or type mismatch

    Examples:
        >>> resolve_single_mention("/attack @goblin", "party-123", session, expected_type="npc")
        {"id": "npc-uuid", "name": "Goblin", "type": "npc"}
    """
    mentions = parse_mentions(text, party_id, db_session)

    if len(mentions) == 0:
        raise MentionParseError("No target specified. Use @name to target a character or NPC.")

    if len(mentions) > 1:
        names = [m['name'] for m in mentions]
        raise MentionParseError(
            f"Multiple targets found: {', '.join(names)}. "
            f"This command expects exactly one target."
        )

    mention = mentions[0]

    # Validate expected type if specified
    if expected_type and mention['type'] != expected_type:
        raise MentionParseError(
            f"@{mention['name']} is a {mention['type']}, but this command expects a {expected_type}."
        )

    return mention


def validate_unique_name(name: str, party_id: str, db_session: Session) -> bool:
    """
    Check if a name is unique within a party (across both Characters and NPCs).

    Used when creating new characters or NPCs to prevent name collisions.

    Args:
        name: The name to validate
        party_id: The party ID to scope the search
        db_session: SQLAlchemy database session

    Returns:
        True if name is unique (no conflicts), False if name already exists

    Examples:
        >>> validate_unique_name("NewChar", "party-123", session)
        True
        >>> validate_unique_name("Alice", "party-123", session)  # Alice exists
        False
    """
    name_lower = name.lower()

    # Check Characters in this party
    character_exists = (
        db_session.query(Character)
        .join(PartyMembership, PartyMembership.character_id == Character.id)
        .filter(PartyMembership.party_id == party_id)
        .filter(Character.name.ilike(name_lower))
        .first()
    ) is not None

    if character_exists:
        return False

    # Check NPCs in this party
    npc_exists = (
        db_session.query(NPC)
        .filter(NPC.party_id == party_id)
        .filter(NPC.name.ilike(name_lower))
        .first()
    ) is not None

    if npc_exists:
        return False

    return True


def get_all_party_names(party_id: str, db_session: Session) -> List[Dict]:
    """
    Get all character and NPC names in a party (for /who command or autocomplete).

    Args:
        party_id: The party ID
        db_session: SQLAlchemy database session

    Returns:
        List of dicts with keys: id, name, type, visible
        visible=False for hidden NPCs (SW only)

    Examples:
        >>> get_all_party_names("party-123", session)
        [
            {"id": "char-1", "name": "Alice", "type": "character", "visible": True},
            {"id": "npc-1", "name": "Goblin", "type": "npc", "visible": True}
        ]
    """
    results = []

    # Get all characters in party
    characters = (
        db_session.query(Character)
        .join(PartyMembership, PartyMembership.character_id == Character.id)
        .filter(PartyMembership.party_id == party_id)
        .all()
    )

    for char in characters:
        results.append({
            "id": char.id,
            "name": char.name,
            "type": "character",
            "visible": True  # Characters always visible
        })

    # Get all NPCs in party
    npcs = (
        db_session.query(NPC)
        .filter(NPC.party_id == party_id)
        .all()
    )

    for npc in npcs:
        results.append({
            "id": npc.id,
            "name": npc.name,
            "type": "npc",
            "visible": npc.visible_to_players
        })

    return results


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison (lowercase, strip whitespace).

    Args:
        name: The name to normalize

    Returns:
        Normalized name string

    Examples:
        >>> normalize_name("  Alice  ")
        'alice'
        >>> normalize_name("GOBLIN")
        'goblin'
    """
    return name.strip().lower()
