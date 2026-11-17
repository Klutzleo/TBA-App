"""
Character creation and level-up utilities (rules v3.1).
Edge, BAP, max DP, uses, weapon and defense dice all come from schemas/leveling_v3_1.json via backend.leveling.
"""

from backend.leveling import CHARACTER_LEVELS, level_stats, weapon_options, ally_stats, ally_weapon_options

# DP progression by level (v3.1: 8 at level 1, +2 per level). Derived, never edited here.
DP_BY_LEVEL = {lvl: row["max_dp"] for lvl, row in CHARACTER_LEVELS.items()}


def calculate_level_stats(level: int) -> dict:
    """
    Calculate Edge, BAP, and max_dp for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        {
            "edge": int (0-5),
            "bap": int (1-5),
            "max_dp": int (8-26)
        }
    
    Raises:
        ValueError: If level is outside 1-10 range
    """
    if level < 1 or level > 10:
        raise ValueError(f"Level must be 1-10, got {level}")
    
    row = level_stats(level)
    return {
        "edge": row["edge"],
        "bap": row["bap"],
        "max_dp": row["max_dp"],
    }


def get_available_attack_styles(level: int) -> list[str]:
    """
    Get available weapon die options for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        List of available attack die strings, single die first (e.g., ["1d8", "2d6"])
    """
    return weapon_options(level)


def get_defense_die(level: int) -> str:
    """
    Get fixed defense die for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        Defense die string (e.g., "1d8")
    """
    return level_stats(level)["defense_die"]


def validate_stats(pp: int, ip: int, sp: int) -> bool:
    """
    Validate TBA v1.5 stat distribution.
    
    Args:
        pp, ip, sp: Character stats (1-3 each)
    
    Returns:
        True if valid, raises ValueError otherwise
    """
    if not all(1 <= stat <= 3 for stat in [pp, ip, sp]):
        raise ValueError("Each stat (PP, IP, SP) must be between 1 and 3")
    
    if pp + ip + sp != 6:
        raise ValueError(f"Stats must sum to 6, got {pp + ip + sp}")
    
    return True


def validate_attack_style(level: int, attack_style: str) -> bool:
    """
    Validate attack style is available for character's level.
    
    Args:
        level: Character level
        attack_style: Chosen attack die (e.g., "3d4")
    
    Returns:
        True if valid, raises ValueError otherwise
    """
    available = get_available_attack_styles(level)
    if attack_style not in available:
        raise ValueError(
            f"Attack style '{attack_style}' not available at level {level}. "
            f"Available: {', '.join(available)}"
        )
    return True


def calculate_ally_stats(level: int) -> dict:
    """Edge, BAP and max DP for an Ally of this level (rules v3.1: their own table, about half a player's DP)."""
    row = ally_stats(level)
    return {"edge": row["edge"], "bap": row["bap"], "max_dp": row["max_dp"]}


def validate_ally_attack_style(level: int, attack_style: str) -> bool:
    """An Ally's weapon is a single die from the Ally table."""
    available = ally_weapon_options(level)
    if attack_style not in available:
        raise ValueError(f"Attack style '{attack_style}' not available to an Ally at level {level}. "
                         f"Available: {', '.join(available)}")
    return True
