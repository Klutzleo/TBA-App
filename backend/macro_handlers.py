"""
Macro Handlers for TBA Chat System (Phase 2b Task 4)

Handles chat macro commands: /roll, /attack, /initiative, /defend, etc.
Integrates with mention parser, character cache, and combat turn tracker.
"""

import re
import random
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from backend.mention_parser import parse_mentions
from backend.models import Character, NPC, PartyMembership

logger = logging.getLogger(__name__)


def roll_dice(dice_notation: str) -> Dict[str, Any]:
    """
    Roll dice based on standard notation (e.g., "1d6", "2d8+3", "3d4-2").

    Args:
        dice_notation: String in format "XdY+Z" or "XdY-Z" where:
            X = number of dice (1-20)
            Y = die size (4, 6, 8, 10, 12, 20)
            Z = modifier (optional)

    Returns:
        Dict with:
            - notation: Original notation
            - rolls: List of individual roll results
            - modifier: The modifier value (0 if none)
            - total: Sum of rolls + modifier
            - breakdown: Human-readable string like "(4+5)+3 = 12"
    """
    # Parse dice notation
    pattern = r'^(\d+)d(\d+)([+\-]\d+)?$'
    match = re.match(pattern, dice_notation.strip(), re.IGNORECASE)

    if not match:
        raise ValueError(f"Invalid dice notation: {dice_notation}")

    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier_str = match.group(3) or "+0"
    modifier = int(modifier_str)

    # Validate number of dice
    if num_dice < 1 or num_dice > 20:
        raise ValueError(f"Number of dice must be between 1 and 20, got {num_dice}")

    # Validate die size
    valid_sizes = [4, 6, 8, 10, 12, 20]
    if die_size not in valid_sizes:
        raise ValueError(f"Die size must be one of {valid_sizes}, got {die_size}")

    # Roll the dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    # Create breakdown string
    if len(rolls) == 1:
        if modifier == 0:
            breakdown = f"{rolls[0]} = {total}"
        elif modifier > 0:
            breakdown = f"{rolls[0]}+{modifier} = {total}"
        else:
            breakdown = f"{rolls[0]}{modifier} = {total}"
    else:
        rolls_str = "+".join(str(r) for r in rolls)
        if modifier == 0:
            breakdown = f"({rolls_str}) = {total}"
        elif modifier > 0:
            breakdown = f"({rolls_str})+{modifier} = {total}"
        else:
            breakdown = f"({rolls_str}){modifier} = {total}"

    return {
        "notation": dice_notation,
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
        "breakdown": breakdown
    }


def handle_macro(
    command: str,
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """
    Main router for macro commands.

    Args:
        command: The macro command (e.g., "/roll", "/attack")
        args: Arguments for the command
        character_id: ID of the character executing the command
        db: Database session
        connection_manager: WebSocket connection manager
        log_combat_action: Function to log combat actions

    Returns:
        Dict with command execution result
    """
    handlers = {
        "/roll": handle_roll,
        "/attack": handle_attack,
        "/initiative": handle_initiative,
        "/initiative-roll": handle_initiative_roll,
        "/defend": handle_defend,
        "/next-turn": handle_next_turn,
        "/end-combat": handle_end_combat
    }

    handler = handlers.get(command.lower())
    if not handler:
        return {
            "success": False,
            "error": f"Unknown command: {command}"
        }

    try:
        return handler(args, character_id, db, connection_manager, log_combat_action)
    except Exception as e:
        logger.error(f"Error handling macro {command}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def handle_roll(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle generic dice roll command."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    if not args or not args.strip():
        return {"success": False, "error": "Please specify dice notation (e.g., /roll 1d6)"}

    try:
        result = roll_dice(args.strip())
        broadcast = f"🎲 **{character.name}** rolled {result['notation']}: {result['breakdown']}"

        return {
            "success": True,
            "command": "/roll",
            "result": result,
            "broadcast": broadcast
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


def handle_attack(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle attack command with target mention."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is in an active encounter
    encounter = connection_manager.get_active_encounter(character.party_id)
    if not encounter:
        return {"success": False, "error": "No active encounter in this party"}

    # Parse mentions to find target
    mentions = parse_mentions(args, db)
    if not mentions or len(mentions) == 0:
        return {"success": False, "error": "Please mention a target (e.g., /attack @Goblin)"}

    target = mentions[0]
    target_name = target.get("name", "Unknown")
    target_type = target.get("type", "unknown")

    # Get weapon and calculate attack roll
    weapon = character.weapon or "1d6"
    pp = character.pp or 0
    edge = character.edge or 0

    # Parse weapon notation and add modifiers
    weapon_match = re.match(r'^(\d+d\d+)([+\-]\d+)?$', weapon, re.IGNORECASE)
    if not weapon_match:
        return {"success": False, "error": f"Invalid weapon notation: {weapon}"}

    base_dice = weapon_match.group(1)
    weapon_mod = int(weapon_match.group(2) or "0")
    total_modifier = weapon_mod + pp + edge

    if total_modifier >= 0:
        attack_notation = f"{base_dice}+{total_modifier}"
    else:
        attack_notation = f"{base_dice}{total_modifier}"

    try:
        result = roll_dice(attack_notation)

        # Log combat action
        log_combat_action(
            encounter_id=encounter["id"],
            character_id=character_id,
            action_type="attack",
            target_name=target_name,
            dice_notation=attack_notation,
            roll_result=result["total"],
            db=db
        )

        broadcast = (
            f"⚔️ **{character.name}** attacks **{target_name}**!\n"
            f"Roll: {result['notation']} = {result['breakdown']}\n"
            f"Damage: **{result['total']}**"
        )

        return {
            "success": True,
            "command": "/attack",
            "result": result,
            "target": target_name,
            "broadcast": broadcast
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


def handle_initiative(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle initiative command (SW only) to start an encounter."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is SW
    if not character.is_sw:
        return {"success": False, "error": "Only the Storyteller can start initiative"}

    # Check if there's already an active encounter
    existing_encounter = connection_manager.get_active_encounter(character.party_id)
    if existing_encounter:
        return {"success": False, "error": "There is already an active encounter. Use /end-combat first."}

    # Get all party members
    party_members = db.query(Character).join(PartyMembership).filter(
        PartyMembership.party_id == character.party_id,
        Character.is_sw == False
    ).all()

    # Parse NPCs from args (if any mentioned)
    npcs = []
    if args and args.strip():
        mentions = parse_mentions(args, db)
        for mention in mentions:
            if mention["type"] == "npc":
                npc = db.query(NPC).filter(NPC.id == mention["id"]).first()
                if npc:
                    npcs.append(npc)

    # Create encounter with all combatants
    combatants = []

    # Add party members
    for member in party_members:
        combatants.append({
            "type": "character",
            "id": member.id,
            "name": member.name,
            "initiative": 0,
            "pp": member.pp or 0,
            "edge": member.edge or 0
        })

    # Add NPCs
    for npc in npcs:
        combatants.append({
            "type": "npc",
            "id": npc.id,
            "name": npc.name,
            "initiative": 0,
            "pp": npc.pp or 0,
            "edge": npc.edge or 0
        })

    if not combatants:
        return {"success": False, "error": "No combatants found for initiative"}

    # Create encounter
    encounter = connection_manager.start_encounter(character.party_id, combatants)

    combatant_list = ", ".join([c["name"] for c in combatants])
    broadcast = (
        f"⚔️ **Initiative Started!**\n"
        f"Combatants: {combatant_list}\n"
        f"Use /initiative-roll to roll initiative for all combatants."
    )

    return {
        "success": True,
        "command": "/initiative",
        "result": {"encounter_id": encounter["id"], "combatants": combatants},
        "broadcast": broadcast
    }


def handle_initiative_roll(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle initiative roll command to roll for all combatants."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is SW
    if not character.is_sw:
        return {"success": False, "error": "Only the Storyteller can roll initiative"}

    # Get active encounter
    encounter = connection_manager.get_active_encounter(character.party_id)
    if not encounter:
        return {"success": False, "error": "No active encounter. Use /initiative first."}

    # Roll initiative for each combatant
    results = []
    for combatant in encounter["combatants"]:
        pp = combatant.get("pp", 0)
        edge = combatant.get("edge", 0)
        modifier = pp + edge

        if modifier >= 0:
            notation = f"1d6+{modifier}"
        else:
            notation = f"1d6{modifier}"

        roll_result = roll_dice(notation)
        combatant["initiative"] = roll_result["total"]

        results.append({
            "name": combatant["name"],
            "roll": roll_result["breakdown"],
            "initiative": roll_result["total"]
        })

    # Sort combatants by initiative (highest first)
    encounter["combatants"].sort(key=lambda x: x["initiative"], reverse=True)

    # Set first turn
    if encounter["combatants"]:
        encounter["current_turn"] = 0

    # Update encounter
    connection_manager.update_encounter(character.party_id, encounter)

    # Format broadcast
    results_str = "\n".join([
        f"**{r['name']}**: {r['roll']} = {r['initiative']}"
        for r in sorted(results, key=lambda x: x["initiative"], reverse=True)
    ])

    current_combatant = encounter["combatants"][0]["name"] if encounter["combatants"] else "Unknown"

    broadcast = (
        f"🎲 **Initiative Rolls:**\n{results_str}\n\n"
        f"**Turn Order Established!**\n"
        f"Current turn: **{current_combatant}**"
    )

    return {
        "success": True,
        "command": "/initiative-roll",
        "result": {"rolls": results, "turn_order": encounter["combatants"]},
        "broadcast": broadcast
    }


def handle_defend(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle defend command."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is in an active encounter
    encounter = connection_manager.get_active_encounter(character.party_id)
    if not encounter:
        return {"success": False, "error": "No active encounter in this party"}

    # Get defense die and calculate defense roll
    defense_die = character.defense_die or "1d6"
    pp = character.pp or 0
    edge = character.edge or 0

    # Parse defense notation and add modifiers
    defense_match = re.match(r'^(\d+d\d+)([+\-]\d+)?$', defense_die, re.IGNORECASE)
    if not defense_match:
        return {"success": False, "error": f"Invalid defense die notation: {defense_die}"}

    base_dice = defense_match.group(1)
    defense_mod = int(defense_match.group(2) or "0")
    total_modifier = defense_mod + pp + edge

    if total_modifier >= 0:
        defense_notation = f"{base_dice}+{total_modifier}"
    else:
        defense_notation = f"{base_dice}{total_modifier}"

    try:
        result = roll_dice(defense_notation)

        # Log combat action
        log_combat_action(
            encounter_id=encounter["id"],
            character_id=character_id,
            action_type="defend",
            target_name=None,
            dice_notation=defense_notation,
            roll_result=result["total"],
            db=db
        )

        broadcast = (
            f"🛡️ **{character.name}** defends!\n"
            f"Roll: {result['notation']} = {result['breakdown']}\n"
            f"Defense: **{result['total']}**"
        )

        return {
            "success": True,
            "command": "/defend",
            "result": result,
            "broadcast": broadcast
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


def handle_next_turn(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle next turn command (SW only)."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is SW
    if not character.is_sw:
        return {"success": False, "error": "Only the Storyteller can advance turns"}

    # Get active encounter
    encounter = connection_manager.get_active_encounter(character.party_id)
    if not encounter:
        return {"success": False, "error": "No active encounter. Use /initiative first."}

    if not encounter["combatants"]:
        return {"success": False, "error": "No combatants in encounter"}

    # Advance turn
    current_turn = encounter.get("current_turn", 0)
    current_turn = (current_turn + 1) % len(encounter["combatants"])
    encounter["current_turn"] = current_turn

    # Increment round if we wrapped around
    if current_turn == 0:
        encounter["round"] = encounter.get("round", 1) + 1

    # Update encounter
    connection_manager.update_encounter(character.party_id, encounter)

    current_combatant = encounter["combatants"][current_turn]
    round_num = encounter.get("round", 1)

    broadcast = (
        f"⏭️ **Turn Advanced!**\n"
        f"Round: {round_num}\n"
        f"Current turn: **{current_combatant['name']}**"
    )

    return {
        "success": True,
        "command": "/next-turn",
        "result": {"round": round_num, "current_turn": current_combatant},
        "broadcast": broadcast
    }


def handle_end_combat(
    args: str,
    character_id: int,
    db: Session,
    connection_manager: Any,
    log_combat_action: Any
) -> Dict[str, Any]:
    """Handle end combat command (SW only)."""
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        return {"success": False, "error": "Character not found"}

    # Check if character is SW
    if not character.is_sw:
        return {"success": False, "error": "Only the Storyteller can end combat"}

    # Get active encounter
    encounter = connection_manager.get_active_encounter(character.party_id)
    if not encounter:
        return {"success": False, "error": "No active encounter to end"}

    # End encounter
    connection_manager.end_encounter(character.party_id)

    broadcast = "✅ **Combat Ended!** The encounter has been closed."

    return {
        "success": True,
        "command": "/end-combat",
        "result": {"encounter_id": encounter["id"]},
        "broadcast": broadcast
    }
