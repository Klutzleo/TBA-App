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

    Args:
        text: The message text to parse

    Returns:
        List of mention names (without @ prefix)

    Examples:
        >>> extract_mentions("/attack @goblin with @sword")
        ['goblin', 'sword']
        >>> extract_mentions("No mentions here")
        []
    """
    pattern = r'@(\w+)'
    matches = re.findall(pattern, text)
    return matches


def parse_mentions(text: str, party_id: str, db_session: Session) -> List[Dict]:
    """
    Parse @mentions and resolve them to Character or NPC entities.

    Args:
        text: The message text containing @mentions
        party_id: The party ID to scope the search
        db_session: SQLAlchemy database session

    Returns:
        List of dicts with keys: id, name, type
        Example: [{"id": "uuid", "name": "Alice", "type": "character"}]

    Raises:
        MentionParseError: If mention is ambiguous or not found

    Examples:
        >>> parse_mentions("/attack @goblin", "party-123", session)
        [{"id": "npc-uuid", "name": "Goblin", "type": "npc"}]
    """
    mention_names = extract_mentions(text)
    if not mention_names:
        return []

    resolved = []

    for name in mention_names:
        # Case-insensitive lookup
        name_lower = name.lower()

        # Search in Characters (party members only)
        character_matches = (
            db_session.query(Character)
            .join(PartyMembership, PartyMembership.character_id == Character.id)
            .filter(PartyMembership.party_id == party_id)
            .filter(Character.name.ilike(name_lower))
            .all()
        )

        # Search in NPCs (for this party)
        npc_matches = (
            db_session.query(NPC)
            .filter(NPC.party_id == party_id)
            .filter(NPC.name.ilike(name_lower))
            .all()
        )

        # Combine results
        all_matches = []
        for char in character_matches:
            all_matches.append({
                "id": char.id,
                "name": char.name,
                "type": "character"
            })

        for npc in npc_matches:
            all_matches.append({
                "id": npc.id,
                "name": npc.name,
                "type": "npc"
            })

        # Validate results
        if len(all_matches) == 0:
            raise MentionParseError(
                f"@{name} not found in party. "
                f"Use /who to see available characters and NPCs."
            )

        if len(all_matches) > 1:
            # Ambiguous - multiple matches
            names = [f"{m['name']} ({m['type']})" for m in all_matches]
            raise MentionParseError(
                f"@{name} is ambiguous. Found: {', '.join(names)}. "
                f"Please be more specific."
            )

        # Exactly one match - success!
        resolved.append(all_matches[0])

    return resolved


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
