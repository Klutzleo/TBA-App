EFFECTS = {
    "fireball": {
        "type": "damage",
        "base": 10,
        "status": "burned",
        "area": True,
        "narration": "{actor} hurls a fireball, dealing {damage} damage and igniting the battlefield."
    },
    "heal": {
        "type": "healing",
        "base": 8,
        "status": "restored",
        "area": False,
        "narration": "{actor} channels healing light, restoring {damage} HP and soothing wounds."
    },
    "stun": {
        "type": "control",
        "base": 0,
        "status": "stunned",
        "area": False,
        "narration": "{actor} unleashes a concussive blast, stunning the target and halting their advance."
    }
}