"""
Character creation and level-up utilities for TBA v1.5.
Auto-calculates Edge, BAP, max DP from CORE_RULESET.
"""

from schemas.loader import CORE_RULESET


# DP progression by level (from TBA v1.5 rules)
DP_BY_LEVEL = {
    1: 10,
    2: 15,
    3: 20,
    4: 25,
    5: 30,
    6: 35,
    7: 40,
    8: 45,
    9: 50,
    10: 55
}


def calculate_level_stats(level: int) -> dict:
    """
    Calculate Edge, BAP, and max_dp for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        {
            "edge": int (0-5),
            "bap": int (1-5),
            "max_dp": int (10-55)
        }
    
    Raises:
        ValueError: If level is outside 1-10 range
    """
    if level < 1 or level > 10:
        raise ValueError(f"Level must be 1-10, got {level}")
    
    level_str = str(level)
    level_data = CORE_RULESET.get("character_leveling", {}).get(level_str, {})
    
    return {
        "edge": level_data.get("Edge", 0),
        "bap": level_data.get("BAP", 1),
        "max_dp": DP_BY_LEVEL.get(level, 10)
    }


def get_available_attack_styles(level: int) -> list[str]:
    """
    Get available weapon die options for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        List of available attack die strings (e.g., ["3d4", "2d6", "1d8"])
    """
    if level <= 2:
        return ["1d4"]
    elif level <= 4:
        return ["2d4", "1d6"]
    elif level <= 6:
        return ["3d4", "2d6", "1d8"]
    elif level <= 8:
        return ["4d4", "3d6", "2d8", "1d10"]
    else:  # 9-10
        return ["5d4", "4d6", "3d8", "2d10", "1d12"]


def get_defense_die(level: int) -> str:
    """
    Get fixed defense die for a given level.
    
    Args:
        level: Character level (1-10)
    
    Returns:
        Defense die string (e.g., "1d8")
    """
    if level <= 2:
        return "1d4"
    elif level <= 4:
        return "1d6"
    elif level <= 6:
        return "1d8"
    elif level <= 8:
        return "1d10"
    else:  # 9-10
        return "1d12"


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
