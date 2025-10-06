import random

def roll_initiative(actor):
    return {
        "name": actor["name"],
        "roll": random.randint(1, 6) + actor.get("edge", 0),
        "pp": actor["stats"].get("PP", 0),
        "ip": actor["stats"].get("IP", 0),
        "sp": actor["stats"].get("SP", 0)
    }

def resolve_initiative(actors):
    rolls = [roll_initiative(a) for a in actors]
    rolls.sort(key=lambda x: (x["roll"], x["pp"], x["ip"], x["sp"]), reverse=True)
    return [r["name"] for r in rolls]