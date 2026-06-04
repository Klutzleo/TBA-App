"""
backend/achievements.py
Achievement engine — all conditions hardcoded here.

Achievement fields:
  name         Display name
  description  Player-facing description
  icon         Lucide icon name
  section      Profile grouping — one of:
                 founding / platform / time / character /
                 combat / calling / dice / shame / story / companions / sw
  difficulty   easy / medium / hard / prestige / None (Founding has no difficulty)
  category     standard / narrative / shame / founding / sw
  broadcast    personal / campaign / global
  points       Point value (baked in at build time)

Point scale:
  Standard:   easy=5   medium=15  hard=30   prestige=100  narrative=25
  Shame:      easy=10  medium=15  hard=30
  SW:         easy=10  medium=20  hard=30   prestige=100  narrative=25
  Founding:   50 (flat, no difficulty)

Broadcast rules:
  easy / shame / time-based           → personal
  medium / hard / narrative / sw      → campaign
  prestige / founding / first-evers   → global

To add an achievement:
  1. Add metadata to ACHIEVEMENTS.
  2. If data exists, add award() call in check_and_award() under the right block.
  3. If data is missing, add the ID to _FUTURE_IDS — it displays but won't fire.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Founding window — accounts created in this range earn OG
FOUNDING_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
FOUNDING_END   = datetime(2027, 7, 31, 23, 59, 59, tzinfo=timezone.utc)

# Badge showcase unlocks at this points total
BADGE_SHOWCASE_THRESHOLD = 150


ACHIEVEMENTS = {

    # ── FOUNDING ──────────────────────────────────────────────────────────────
    "og": {
        "name": "OG",
        "description": "Created your account during the alpha/beta period (2025–2027).",
        "icon": "flame",
        "section": "founding",
        "difficulty": None,
        "category": "founding",
        "broadcast": "global",
        "points": 50,
    },
    "day_one": {
        "name": "Day One",
        "description": "Created your account during launch month.",
        "icon": "flame",
        "section": "founding",
        "difficulty": None,
        "category": "founding",
        "broadcast": "global",
        "points": 50,
    },
    "early_adopter": {
        "name": "Early Adopter",
        "description": "Created your account during the launch year.",
        "icon": "flame",
        "section": "founding",
        "difficulty": None,
        "category": "founding",
        "broadcast": "global",
        "points": 50,
    },

    # ── PROFILE & PLATFORM ────────────────────────────────────────────────────
    "look_at_this_photograph": {
        "name": "Look at This Photograph",
        "description": "Upload a profile picture.",
        "icon": "camera",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "here_looking_at_you": {
        "name": "Here's Looking at You, Kid",
        "description": "Upload your first character portrait.",
        "icon": "image",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "if_you_build_it": {
        "name": "If You Build It, They Will Come",
        "description": "Create your first campaign.",
        "icon": "map",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "welcome_to_the_party": {
        "name": "Welcome to the Party, Pal",
        "description": "Join your first campaign.",
        "icon": "door-open",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "badges_we_aint_got": {
        "name": "Badges? We Ain't Got No Badges!",
        "description": f"Earn {BADGE_SHOWCASE_THRESHOLD} points to unlock your badge showcase.",
        "icon": "award",
        "section": "platform",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "heads_up": {
        "name": "Heads Up",
        "description": "Enable push notifications.",
        "icon": "bell",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "lurker": {
        "name": "Lurker",
        "description": "Open the OOC tab for the first time.",
        "icon": "eye",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "lorekeeper_tab": {
        "name": "Lorekeeper",
        "description": "Open the Lore tab for the first time.",
        "icon": "book",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "archivist": {
        "name": "Archivist",
        "description": "Open the Images tab for the first time.",
        "icon": "image",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "prepared": {
        "name": "Prepared",
        "description": "Open the Notes tab for the first time.",
        "icon": "notebook",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "treasure_hunter": {
        "name": "Treasure Hunter",
        "description": "Open the Loot Pool tab for the first time.",
        "icon": "package",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "all_in": {
        "name": "All In",
        "description": "Open every tab in one day.",
        "icon": "layout-grid",
        "section": "platform",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "quick_reference": {
        "name": "Quick Reference",
        "description": "Open the help panel.",
        "icon": "help-circle",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "for_those_about_to_rock": {
        "name": "For Those About to Rock (We Salute You)",
        "description": "Join a 4-person party, or run a public campaign with 4+ players.",
        "icon": "users",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    "a_party_forms": {
        "name": "A Party Forms",
        "description": "4 or more players simultaneously connected in a campaign.",
        "icon": "users",
        "section": "platform",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "full_house": {
        "name": "Full House",
        "description": "6 or more players simultaneously connected.",
        "icon": "users",
        "section": "platform",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "bigger_boat": {
        "name": "You're Gonna Need a Bigger Boat",
        "description": "Your campaign hits max player count.",
        "icon": "anchor",
        "section": "platform",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    # Referral — ships when friend system is built
    "let_me_tell_you": {
        "name": "Let Me Tell You About My Beeeeest Friend",
        "description": "Refer a friend to TBA.",
        "icon": "user-plus",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "somebodys_watching": {
        "name": "Why Does It Feel Like Somebody's Watching Me",
        "description": "Join via a friend's referral link.",
        "icon": "eye",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "little_help": {
        "name": "With a Little Help From My Friends",
        "description": "Join a campaign where a friend is already playing.",
        "icon": "heart-handshake",
        "section": "platform",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },

    # ── TIME & CONSISTENCY ────────────────────────────────────────────────────
    "welcome_to_tba": {
        "name": "Welcome to TBA",
        "description": "Account is 7 days old.",
        "icon": "clock",
        "section": "time",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "part_of_something": {
        "name": "Part of Something",
        "description": "Account is 30 days old.",
        "icon": "clock",
        "section": "time",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "here_to_stay": {
        "name": "Here to Stay",
        "description": "Account is 90 days old.",
        "icon": "calendar",
        "section": "time",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "committed_account": {
        "name": "Committed",
        "description": "Account is 1 year old.",
        "icon": "calendar",
        "section": "time",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "true_believer": {
        "name": "True Believer",
        "description": "Account is 2 years old.",
        "icon": "star",
        "section": "time",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "im_back_baby": {
        "name": "I'm Back, Baby",
        "description": "Return to TBA after 30 days away.",
        "icon": "rotate-ccw",
        "section": "time",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "life_moves_pretty_fast": {
        "name": "Life Moves Pretty Fast...",
        "description": "Go MIA for 30+ days while your campaign is still active.",
        "icon": "wind",
        "section": "time",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "personal",
        "points": 25,
    },
    "ghost_story": {
        "name": "Ghost Story",
        "description": "Send a message after midnight local time.",
        "icon": "moon",
        "section": "time",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "personal",
        "points": 25,
    },
    "night_owl": {
        "name": "Night Owl",
        "description": "Send 50 messages after midnight.",
        "icon": "moon",
        "section": "time",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "i_play_for_keeps": {
        "name": "I Play for Keeps",
        "description": "Active in a campaign 7 days straight.",
        "icon": "flame",
        "section": "time",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "campaign",
        "points": 15,
    },
    "dont_stop_me_now": {
        "name": "Don't Stop Me Now",
        "description": "Active every week for a month.",
        "icon": "zap",
        "section": "time",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "campaign",
        "points": 15,
    },

    # ── CHARACTER & LEVELING / CURRENCY / LOOT ────────────────────────────────
    "its_alive": {
        "name": "It's Alive... IT'S ALIVE",
        "description": "Create your first character.",
        "icon": "user",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "godfather": {
        "name": "I'm Gonna Make Him an Offer He Can't Refuse",
        "description": "Submit a character for Story Weaver approval.",
        "icon": "file-check",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "level_up": {
        "name": "Level Up",
        "description": "Reach level 2.",
        "icon": "trending-up",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    "halfway_there": {
        "name": "Halfway There",
        "description": "Reach level 5.",
        "icon": "trending-up",
        "section": "character",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "campaign",
        "points": 15,
    },
    "legendary_level": {
        "name": "Legendary",
        "description": "Reach level 10.",
        "icon": "crown",
        "section": "character",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "ascended": {
        "name": "Ascended",
        "description": "Reach level 11.",
        "icon": "sparkles",
        "section": "character",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "true_legend": {
        "name": "True Legend",
        "description": "Reach level 15.",
        "icon": "sparkles",
        "section": "character",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "treat_yourself": {
        "name": "Treat Yourself",
        "description": "Receive currency for the first time.",
        "icon": "coins",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "mo_money": {
        "name": "Mo Money Mo Problems",
        "description": "Spend currency for the first time.",
        "icon": "coins",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "my_precious": {
        "name": "My Precious",
        "description": "Receive your first item from the Loot Pool.",
        "icon": "package",
        "section": "character",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },

    # ── COMBAT & SURVIVAL ─────────────────────────────────────────────────────
    # --- Firsts (folded into combat) ---
    "its_a_trap": {
        "name": "It's a Trap!",
        "description": "Roll initiative as your very first action in a campaign.",
        "icon": "alert-triangle",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "bad_feeling": {
        "name": "I've Got a Bad Feeling About This",
        "description": "Enter your first combat.",
        "icon": "shield-alert",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    "may_the_odds": {
        "name": "May the Odds Be Ever in Your Favor",
        "description": "Win your first initiative roll.",
        "icon": "target",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "youre_a_wizard": {
        "name": "You're a Wizard, Harry",
        "description": "Use BAP for the first time.",
        "icon": "wand",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    "thats_no_moon_death": {
        "name": "That's No Moon... Oh Wait, It Is",
        "description": "Die in your very first combat.",
        "icon": "skull",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    # --- Core combat ---
    "say_hello": {
        "name": "Say Hello to My Little Friend",
        "description": "Cast your first ability or technique.",
        "icon": "sparkles",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "first_blood": {
        "name": "First Blood",
        "description": "Land your first attack.",
        "icon": "sword",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "war_machine": {
        "name": "War Machine",
        "description": "Make 100 attacks.",
        "icon": "shield",
        "section": "combat",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "unstoppable": {
        "name": "Unstoppable",
        "description": "Make 500 attacks.",
        "icon": "shield",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "wrath_incarnate": {
        "name": "Wrath Incarnate",
        "description": "Deal 1,000 total damage.",
        "icon": "flame",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "took_that_personally": {
        "name": "And I Took That Personally",
        "description": "Deal a single hit that exceeds the target's max DP.",
        "icon": "zap",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "technique_master": {
        "name": "Technique Master",
        "description": "Cast 100 abilities.",
        "icon": "sparkles",
        "section": "combat",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "that_was_badass": {
        "name": "That Was Badass",
        "description": "Receive BAP for the first time.",
        "icon": "zap",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "campaign",
        "points": 5,
    },
    "great_kid": {
        "name": "Great Kid, Don't Get Cocky",
        "description": "Receive BAP twice in a single battle.",
        "icon": "zap",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "born_for_this": {
        "name": "Born For This",
        "description": "Receive BAP 50 times total.",
        "icon": "zap",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "war_room": {
        "name": "Gentlemen, You Can't Fight in Here! This is the War Room!",
        "description": "Initiate PvP combat.",
        "icon": "swords",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    # --- Survival (folded into combat) ---
    "survivor": {
        "name": "Survivor",
        "description": "Survive your first battle.",
        "icon": "heart",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "veteran_battles": {
        "name": "Veteran",
        "description": "Survive 10 battles.",
        "icon": "shield",
        "section": "combat",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "grizzled": {
        "name": "Grizzled",
        "description": "Survive 25 battles.",
        "icon": "shield",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "make_my_day": {
        "name": "Go Ahead, Make My Day",
        "description": "Survive being attacked while at 25% or less DP.",
        "icon": "heart-pulse",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "yo_adrian": {
        "name": "Yo, Adrian",
        "description": "Survive 10 battles taking 25%+ of max DP in damage.",
        "icon": "heart-pulse",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "it_aint_about_how_hard": {
        "name": "It Ain't About How Hard You Hit",
        "description": "Survive 25 battles taking 25%+ of max DP in damage.",
        "icon": "heart-pulse",
        "section": "combat",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "houston": {
        "name": "Houston, We Have a Problem",
        "description": "Be the last character standing in combat.",
        "icon": "radio",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "failure_not_option": {
        "name": "Failure Is Not an Option",
        "description": "Win a combat as the last character standing.",
        "icon": "trophy",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "shaken_not_stirred": {
        "name": "Shaken, Not Stirred",
        "description": "Survive a battle with the whole party under 50% DP.",
        "icon": "wine",
        "section": "combat",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "campaign",
        "points": 15,
    },
    "womp_rat": {
        "name": "That's No Bigger Than a Womp Rat",
        "description": "Defeat an enemy 2+ levels below you.",
        "icon": "chevrons-down",
        "section": "combat",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "bulls_eye_womp_rats": {
        "name": "I Used to Bull's-Eye Womp Rats Back Home",
        "description": "Defeat an enemy 2+ levels above you.",
        "icon": "chevrons-up",
        "section": "combat",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },

    # ── THE CALLING ───────────────────────────────────────────────────────────
    "ill_be_back": {
        "name": "I'll Be Back",
        "description": "Survive The Calling once.",
        "icon": "refresh-cw",
        "section": "calling",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "hasta_la_vista": {
        "name": "Hasta La Vista, Baby",
        "description": "Die in The Calling.",
        "icon": "skull",
        "section": "calling",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "marked": {
        "name": "Marked",
        "description": "Carry your first Battle Scar.",
        "icon": "badge-alert",
        "section": "calling",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "personal",
        "points": 25,
    },
    "twice_marked": {
        "name": "Twice Marked",
        "description": "Carry 3 Battle Scars simultaneously.",
        "icon": "badge-alert",
        "section": "calling",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "death_knows_my_name": {
        "name": "Death Knows My Name",
        "description": "Survive The Calling 5 times.",
        "icon": "skull",
        "section": "calling",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "death_wish": {
        "name": "Death Wish",
        "description": "Survive The Calling while carrying 3 active Battle Scars.",
        "icon": "skull",
        "section": "calling",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "no_crying_in_tba": {
        "name": "There's No Crying in TBA",
        "description": "Trigger The Calling AND win the encounter in the same turn.",
        "icon": "trophy",
        "section": "calling",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "it_was_personal": {
        "name": "It Was Personal",
        "description": "Invoke a tether AND survive The Calling in the same day.",
        "icon": "link",
        "section": "calling",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },

    # ── DICE & ROLLS ──────────────────────────────────────────────────────────
    "you_had_me_at_roll": {
        "name": "You Had Me at /roll",
        "description": "Roll your first stat check.",
        "icon": "dice-6",
        "section": "dice",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "brute_force": {
        "name": "Brute Force",
        "description": "Roll your first PP (Physical) check.",
        "icon": "dumbbell",
        "section": "dice",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "elementary": {
        "name": "Elementary",
        "description": "Roll your first IP (Intellect) check.",
        "icon": "brain",
        "section": "dice",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "speak_softly": {
        "name": "Speak Softly",
        "description": "Roll your first SP (Social) check.",
        "icon": "message-square",
        "section": "dice",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "getting_started": {
        "name": "Getting Started",
        "description": "Roll 100 dice total.",
        "icon": "dice-6",
        "section": "dice",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "dice_goblin": {
        "name": "Dice Goblin",
        "description": "Roll 500 dice total.",
        "icon": "dice-6",
        "section": "dice",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "committed_to_craft": {
        "name": "Committed to the Craft",
        "description": "Roll 1,000 dice total.",
        "icon": "dice-6",
        "section": "dice",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "blessed": {
        "name": "Blessed",
        "description": "Land 10 natural max rolls.",
        "icon": "sparkles",
        "section": "dice",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "touched_by_gods": {
        "name": "Touched by the Gods",
        "description": "Land 25 natural max rolls.",
        "icon": "sparkles",
        "section": "dice",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "inconceivable": {
        "name": "INCONCEIVABLE",
        "description": "Roll a natural max with a stat of 1 in combat.",
        "icon": "star",
        "section": "dice",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "cinderella_story": {
        "name": "Cinderella Story. Outta Nowhere...",
        "description": "Roll a natural max with a stat of 1 on a stat check.",
        "icon": "star",
        "section": "dice",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "never_tell_me_odds": {
        "name": "Never Tell Me the Odds",
        "description": "Roll a natural max with a stat of 1 during The Calling.",
        "icon": "star",
        "section": "dice",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
    "not_the_droids": {
        "name": "These Aren't the Droids You're Looking For",
        "description": "Roll a natural max on an SP check.",
        "icon": "sparkles",
        "section": "dice",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "schwartz": {
        "name": "I See Your Schwartz is as Big as Mine!",
        "description": "Tie a roll in combat.",
        "icon": "equal",
        "section": "dice",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "do_or_do_not": {
        "name": "Do or Do Not",
        "description": "Succeed on a check while debuffed.",
        "icon": "check-circle",
        "section": "dice",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },

    # ── HALL OF SHAME ─────────────────────────────────────────────────────────
    "keep_swingin": {
        "name": "Keep Swingin'",
        "description": "Miss your first attack.",
        "icon": "x-circle",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "maybe_give_em_cold": {
        "name": "...Maybe You'll Give 'Em a Cold",
        "description": "Miss 10 attacks total.",
        "icon": "x-circle",
        "section": "shame",
        "difficulty": "medium",
        "category": "shame",
        "broadcast": "personal",
        "points": 15,
    },
    "i_spent_what": {
        "name": "I Spent WHAT",
        "description": "Miss while BAP is active.",
        "icon": "zap-off",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "cursed": {
        "name": "Cursed",
        "description": "Roll 10 ones total.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "medium",
        "category": "shame",
        "broadcast": "personal",
        "points": 15,
    },
    "legendarily_bad": {
        "name": "Legendarily Bad",
        "description": "Roll 25 ones total.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "hard",
        "category": "shame",
        "broadcast": "personal",
        "points": 30,
    },
    "put_candle_back": {
        "name": "Put... the Candle... Back!",
        "description": "Roll a 1 on a PP check.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "we_aint_found_sht": {
        "name": "We Ain't Found Sh*t!",
        "description": "Roll a 1 on an IP check.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "cant_handle_truth": {
        "name": "You Can't Handle the Truth",
        "description": "Roll a 1 on an SP check.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "thats_no_moon_shame": {
        "name": "That's No Moon...",
        "description": "Roll a total of 0 or below after debuffs on a stat check.",
        "icon": "frown",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "sucking_at_something": {
        "name": "Sucking at Something...",
        "description": "Fail any check.",
        "icon": "thumbs-down",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "first_step": {
        "name": "...Is the First Step Towards Being Sorta Good",
        "description": "Fail a check then immediately succeed the same check type.",
        "icon": "trending-up",
        "section": "shame",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "allow_myself": {
        "name": "Allow Myself to Introduce... Myself",
        "description": "Miss as an NPC.",
        "icon": "x-circle",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },
    "broke_and_loving_it_shame": {
        "name": "Broke and Loving It",
        "description": "Spend down to zero currency after having had some.",
        "icon": "piggy-bank",
        "section": "shame",
        "difficulty": "easy",
        "category": "shame",
        "broadcast": "personal",
        "points": 10,
    },

    # ── STORY & NARRATIVE ─────────────────────────────────────────────────────
    "once_upon_a_time": {
        "name": "Once Upon a Time",
        "description": "Send your first Story message, or write your first lore entry as a SW.",
        "icon": "book",
        "section": "story",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "finding_my_voice": {
        "name": "Finding My Voice",
        "description": "Send 100 messages total.",
        "icon": "message-square",
        "section": "story",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "the_voice": {
        "name": "The Voice",
        "description": "Send 500 messages total.",
        "icon": "message-square",
        "section": "story",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "personal",
        "points": 30,
    },
    "whisper_achievement": {
        "name": "Whisper",
        "description": "Send your first whisper.",
        "icon": "message-circle",
        "section": "story",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "secrets_keep": {
        "name": "Secrets Keep",
        "description": "Send 10 whispers total.",
        "icon": "message-circle",
        "section": "story",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "at_mentioned": {
        "name": "@Mentioned",
        "description": "Get mentioned by another player.",
        "icon": "at-sign",
        "section": "story",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "called_out": {
        "name": "Called Out",
        "description": "Get mentioned 10 times.",
        "icon": "at-sign",
        "section": "story",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },
    "in_character": {
        "name": "In Character",
        "description": "Send 10 IC messages in one day.",
        "icon": "message-square",
        "section": "story",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },

    # ── COMPANIONS ────────────────────────────────────────────────────────────
    "you_have_my_sword": {
        "name": "You Have My Sword",
        "description": "Use an Ally for the first time.",
        "icon": "users",
        "section": "companions",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "bonded": {
        "name": "Bonded",
        "description": "Acquire your first Ally.",
        "icon": "users",
        "section": "companions",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "you_called": {
        "name": "You Called?",
        "description": "Fire a summon for the first time.",
        "icon": "wand",
        "section": "companions",
        "difficulty": "easy",
        "category": "standard",
        "broadcast": "personal",
        "points": 5,
    },
    "never_alone": {
        "name": "Never Alone",
        "description": "Have an Ally and a summon active simultaneously.",
        "icon": "users",
        "section": "companions",
        "difficulty": "medium",
        "category": "standard",
        "broadcast": "personal",
        "points": 15,
    },

    # ── STORY WEAVER ──────────────────────────────────────────────────────────
    "sw_if_you_build_it": {
        "name": "If You Build It, They Will Come",
        "description": "Create your first campaign as a Story Weaver.",
        "icon": "map",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_oh_baby_triple": {
        "name": "Oh Baby! A Triple!",
        "description": "Run 3 campaigns.",
        "icon": "map",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_all_work_no_play": {
        "name": "All Work and No Play Makes Jack a Dull Boy",
        "description": "Run 5 simultaneous campaigns.",
        "icon": "layout-grid",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_for_those_about_to_rock": {
        "name": "For Those About to Rock (We Salute You)",
        "description": "Run a public campaign with 4+ players.",
        "icon": "users",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_up_to_eleven": {
        "name": "It Goes Up to 11",
        "description": "Have 11 unique players across your campaigns.",
        "icon": "users",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_another_brick": {
        "name": "Another Brick in the Wall",
        "description": "Have 25 unique players across your campaigns.",
        "icon": "users",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_usual_suspects": {
        "name": "Assemble the Usual Suspects",
        "description": "Create 10 NPCs.",
        "icon": "user-x",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_names_tombstones": {
        "name": "Names Are for Tombstones Baby",
        "description": "Create 25 NPCs.",
        "icon": "user-x",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_allow_me": {
        "name": "Allow Me to Introduce Myself",
        "description": "Land your first hit as an NPC.",
        "icon": "sword",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_i_can_do_this": {
        "name": "I Can Do This All Day",
        "description": "Keep an NPC alive for 3 rounds against the full party.",
        "icon": "shield",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_bohemian_rhapsody": {
        "name": "Bohemian Rhapsody",
        "description": "Speak as 5 different NPCs in one day.",
        "icon": "mic",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_thunderstruck": {
        "name": "You've Been... Thunderstruck",
        "description": "Use environmental damage for the first time.",
        "icon": "zap",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_good_bad_ugly": {
        "name": "The Good, the Bad, and the Ugly",
        "description": "Use 3 different environmental damage tiers in one campaign.",
        "icon": "layers",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_let_there_be_light": {
        "name": "Let There Be Light",
        "description": "Set your first scene.",
        "icon": "sun",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_changes": {
        "name": "Ch-Ch-Changes",
        "description": "Update a scene 25 times.",
        "icon": "refresh-cw",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_once_upon_a_time": {
        "name": "Once Upon a Time",
        "description": "Write your first lore entry.",
        "icon": "book-open",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_sacred_texts": {
        "name": "The Sacred Texts!",
        "description": "Write 10 lore entries.",
        "icon": "book-open",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_are_you_visualizing": {
        "name": "Are You Visualizing This??",
        "description": "Share your first image in a session.",
        "icon": "image",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_every_picture": {
        "name": "Every Picture Tells a Story",
        "description": "Share 10 images across campaigns.",
        "icon": "image",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_i_have_a_secret": {
        "name": "I Have a Secret",
        "description": "Send your first whisper to a player.",
        "icon": "message-circle",
        "section": "sw",
        "difficulty": "easy",
        "category": "sw",
        "broadcast": "campaign",
        "points": 10,
    },
    "sw_pay_no_attention": {
        "name": "Pay No Attention to That Man Behind the Curtain!",
        "description": "Whisper to every player in one session.",
        "icon": "eye-off",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_evil_triumph": {
        "name": "Now You See That Evil Will Always Triumph",
        "description": "Deal more damage as NPCs than the party did in one day.",
        "icon": "skull",
        "section": "sw",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "sw_good_to_be_king": {
        "name": "It's Good to Be the King",
        "description": "Initiate 10 battles.",
        "icon": "crown",
        "section": "sw",
        "difficulty": "medium",
        "category": "sw",
        "broadcast": "campaign",
        "points": 20,
    },
    "sw_hes_dead_jim": {
        "name": "He's Dead, Jim",
        "description": "A player dies in The Calling in your campaign.",
        "icon": "skull",
        "section": "sw",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "sw_im_still_standing": {
        "name": "I'm Still Standing",
        "description": "A player survives The Calling in your campaign.",
        "icon": "heart",
        "section": "sw",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "sw_unlimited_power": {
        "name": "Unlimited Power!",
        "description": "A player reaches level 10 in your campaign.",
        "icon": "zap",
        "section": "sw",
        "difficulty": "prestige",
        "category": "sw",
        "broadcast": "global",
        "points": 100,
    },
    "sw_neverending_story": {
        "name": "The NeverEnding Story",
        "description": "Your campaign hits 100+ story messages.",
        "icon": "book",
        "section": "sw",
        "difficulty": "hard",
        "category": "sw",
        "broadcast": "campaign",
        "points": 30,
    },
    "sw_roads": {
        "name": "Roads? Where We're Going We Don't Need Roads",
        "description": "Keep a campaign alive for 1 year.",
        "icon": "calendar",
        "section": "sw",
        "difficulty": "prestige",
        "category": "sw",
        "broadcast": "global",
        "points": 100,
    },

    # ── v3.0 PLACEHOLDERS — DO NOT EVALUATE ───────────────────────────────────
    "v30_bonded": {
        "name": "Bonded",
        "description": "Form your first player Bond.",
        "icon": "link",
        "section": "companions",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "v30_the_move": {
        "name": "The Move",
        "description": "Fire a named Combo for the first time.",
        "icon": "zap",
        "section": "combat",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "v30_legendary_pair": {
        "name": "Legendary Pair",
        "description": "Fire 10 Combos with the same partner.",
        "icon": "users",
        "section": "combat",
        "difficulty": "hard",
        "category": "standard",
        "broadcast": "campaign",
        "points": 30,
    },
    "v30_gone_but_not_forgotten": {
        "name": "Gone But Not Forgotten",
        "description": "Lose a Bond partner.",
        "icon": "heart-crack",
        "section": "companions",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "v30_as_you_wish": {
        "name": "As You Wish",
        "description": "Respond to a SW scene post in-character within 2 minutes.",
        "icon": "clock",
        "section": "story",
        "difficulty": None,
        "category": "narrative",
        "broadcast": "campaign",
        "points": 25,
    },
    "v30_the_move_evolved": {
        "name": "The Move Evolved",
        "description": "Fire an Ascension Combo.",
        "icon": "sparkles",
        "section": "combat",
        "difficulty": "prestige",
        "category": "standard",
        "broadcast": "global",
        "points": 100,
    },
}


# ── IDs with missing tracking data ────────────────────────────────────────────
# These are in the dict (so they display on profiles) but check_and_award()
# skips them. Remove an ID from here once the tracking field ships.
_FUTURE_IDS: set[str] = {
    # Founding — launch date not yet defined
    "day_one", "early_adopter",
    # Profile/platform — UI event tracking not built
    "heads_up", "lurker", "lorekeeper_tab", "archivist", "prepared",
    "treasure_hunter", "all_in", "quick_reference",
    # Profile pic — avatar_url tracking not wired to awards yet (checked inline below)
    # Concurrent connections not tracked
    "a_party_forms", "full_house", "bigger_boat", "for_those_about_to_rock",
    # Referral system not built
    "let_me_tell_you", "somebodys_watching", "little_help",
    # Streak / return / midnight tracking not built
    "i_play_for_keeps", "dont_stop_me_now",
    "im_back_baby", "life_moves_pretty_fast",
    "ghost_story", "night_owl", "in_character",
    # Currency system tracking not built
    "treat_yourself", "mo_money", "broke_and_loving_it", "broke_and_loving_it_shame",
    # Loot tracking not built
    "my_precious",
    # Character firsts — need new per-event tracking
    "its_a_trap", "may_the_odds", "youre_a_wizard", "thats_no_moon_death",
    # BAP per-battle not tracked
    "great_kid",
    # PvP not tracked
    "war_room",
    # Per-battle DP snapshots not tracked
    "make_my_day", "yo_adrian", "it_aint_about_how_hard",
    "houston", "failure_not_option", "shaken_not_stirred",
    # Enemy level comparison not tracked
    "womp_rat", "bulls_eye_womp_rats",
    # Needs hit-vs-target-max-DP at time of hit
    "took_that_personally",
    # Active scar count checked via character below — only blocked without character_id
    # "twice_marked", "death_wish" — evaluated when character_id provided
    # Same-day tether+calling comparison not tracked
    "it_was_personal", "no_crying_in_tba",
    # Consecutive check outcome tracking not built
    "sucking_at_something", "first_step",
    # Tie roll tracking not built
    "schwartz",
    # Prestige roll+stat=1 tracking not built
    "inconceivable", "never_tell_me_odds",
    # Whisper / mention tracking not built
    "whisper_achievement", "secrets_keep", "at_mentioned", "called_out",
    # Ally tracking not built
    "you_have_my_sword", "bonded", "never_alone",
    # SW data gaps
    "sw_all_work_no_play", "sw_up_to_eleven", "sw_another_brick",
    "sw_i_can_do_this", "sw_bohemian_rhapsody",
    "sw_thunderstruck", "sw_good_bad_ugly",
    "sw_i_have_a_secret", "sw_pay_no_attention",
    "sw_evil_triumph", "sw_hes_dead_jim", "sw_im_still_standing",
    "sw_neverending_story", "sw_roads", "sw_for_those_about_to_rock",
    "allow_myself",
    # Godfather — needs character submission event tracking
    "godfather",
    # Bad feeling — needs battles_entered tracking
    "bad_feeling",
    # v3.0
    "v30_bonded", "v30_the_move", "v30_legendary_pair",
    "v30_gone_but_not_forgotten", "v30_as_you_wish", "v30_the_move_evolved",
}


def check_and_award(user_id, db: Session, character_id=None, silent=False) -> list[str]:
    """
    Evaluate all achievement conditions for a user and award any newly earned ones.
    Returns the list of newly-awarded achievement IDs.

    Pass character_id when calling from a character action — unlocks portrait
    and active battle-scar checks.
    """
    from backend.models import UserStats, UserAchievement, User, Character, UserProfile

    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        # Create a zero-stats row so time/founding checks can still run
        stats = UserStats(user_id=user_id)
        db.add(stats)
        db.flush()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []

    earned = {
        row.achievement_id
        for row in db.query(UserAchievement.achievement_id)
        .filter(UserAchievement.user_id == user_id)
        .all()
    }

    newly_awarded: list[str] = []

    def award(achievement_id: str):
        if achievement_id in _FUTURE_IDS:
            return
        if achievement_id not in earned:
            db.add(UserAchievement(user_id=user_id, achievement_id=achievement_id))
            earned.add(achievement_id)
            newly_awarded.append(achievement_id)

    # ── FOUNDING ──────────────────────────────────────────────────────────────
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if FOUNDING_START <= created_at <= FOUNDING_END:
        award("og")

    # ── ACCOUNT AGE ───────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    age_days = (now - created_at).days
    if age_days >= 7:
        award("welcome_to_tba")
    if age_days >= 30:
        award("part_of_something")
    if age_days >= 90:
        award("here_to_stay")
    if age_days >= 365:
        award("committed_account")
    if age_days >= 730:
        award("true_believer")

    # ── PROFILE & PLATFORM ────────────────────────────────────────────────────
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile and profile.avatar_url:
        award("look_at_this_photograph")

    if stats.campaigns_created >= 1:
        award("if_you_build_it")
    if stats.campaigns_joined >= 1:
        award("welcome_to_the_party")

    # ── CHARACTER ─────────────────────────────────────────────────────────────
    # Check if the user has created any character at all
    has_character = db.query(Character.id).filter(
        Character.user_id == user_id, Character.is_npc == False
    ).first()
    if has_character:
        award("its_alive")

    if character_id:
        char = db.query(Character).filter(Character.id == character_id).first()
        if char:
            if char.portrait_url:
                award("here_looking_at_you")
            # Active battle scar count (live array length, not lifetime total)
            active_scars = len(char.battle_scars) if char.battle_scars else 0
            if active_scars >= 3:
                award("twice_marked")
                # Death wish: survived calling with 3 active scars
                # We award this opportunistically — if they have 3 scars and
                # have survived at least one calling, it likely fired during one
                if stats.callings_survived >= 1:
                    award("death_wish")

    # Level achievements use highest_level_reached (anti-exploit compatible)
    if stats.highest_level_reached >= 2:
        award("level_up")
    if stats.highest_level_reached >= 5:
        award("halfway_there")
    if stats.highest_level_reached >= 10:
        award("legendary_level")
    if stats.highest_level_reached >= 11:
        award("ascended")
    if stats.highest_level_reached >= 15:
        award("true_legend")

    # ── COMBAT ────────────────────────────────────────────────────────────────
    if stats.total_abilities_cast >= 1:
        award("say_hello")
    if stats.total_attacks >= 1:
        award("first_blood")
    if stats.total_attacks >= 100:
        award("war_machine")
    if stats.total_attacks >= 500:
        award("unstoppable")
    if stats.total_damage_dealt >= 1000:
        award("wrath_incarnate")
    if stats.total_abilities_cast >= 100:
        award("technique_master")
    if stats.total_bap_used >= 1:
        award("that_was_badass")
    if stats.total_bap_used >= 50:
        award("born_for_this")

    # ── SURVIVAL ──────────────────────────────────────────────────────────────
    if stats.battles_survived >= 1:
        award("survivor")
    if stats.battles_survived >= 10:
        award("veteran_battles")
    if stats.battles_survived >= 25:
        award("grizzled")

    # ── THE CALLING ───────────────────────────────────────────────────────────
    if stats.callings_survived >= 1:
        award("ill_be_back")
    if stats.callings_died >= 1:
        award("hasta_la_vista")
    if stats.total_battle_scars >= 1:
        award("marked")
    if stats.callings_survived >= 5:
        award("death_knows_my_name")

    # ── DICE & ROLLS ──────────────────────────────────────────────────────────
    if stats.total_stat_checks >= 1:
        award("you_had_me_at_roll")
    if stats.total_pp_checks >= 1:
        award("brute_force")
    if stats.total_ip_checks >= 1:
        award("elementary")
    if stats.total_sp_checks >= 1:
        award("speak_softly")
    if stats.total_rolls >= 100:
        award("getting_started")
    if stats.total_rolls >= 500:
        award("dice_goblin")
    if stats.total_rolls >= 1000:
        award("committed_to_craft")
    if stats.total_max_rolls >= 10:
        award("blessed")
    if stats.total_max_rolls >= 25:
        award("touched_by_gods")
    if stats.sp_check_maxes >= 1:
        award("not_the_droids")
    if stats.stat_one_check_maxes >= 1:
        award("cinderella_story")
    if stats.checks_while_debuffed_won >= 1:
        award("do_or_do_not")

    # ── HALL OF SHAME ─────────────────────────────────────────────────────────
    if stats.miss_count >= 1:
        award("keep_swingin")
    if stats.miss_count >= 10:
        award("maybe_give_em_cold")
    if stats.bap_miss_count >= 1:
        award("i_spent_what")
    if stats.total_ones >= 10:
        award("cursed")
    if stats.total_ones >= 25:
        award("legendarily_bad")
    if stats.pp_check_ones >= 1:
        award("put_candle_back")
    if stats.ip_check_ones >= 1:
        award("we_aint_found_sht")
    if stats.sp_check_ones >= 1:
        award("cant_handle_truth")
    if stats.checks_total_zero_or_below >= 1:
        award("thats_no_moon_shame")

    # ── STORY & NARRATIVE ─────────────────────────────────────────────────────
    # Shared trigger: first story message (player) OR first lore entry (SW)
    if stats.total_messages_sent >= 1 or stats.lore_entries_created >= 1:
        award("once_upon_a_time")
    if stats.total_messages_sent >= 100:
        award("finding_my_voice")
    if stats.total_messages_sent >= 500:
        award("the_voice")

    # ── COMPANIONS ────────────────────────────────────────────────────────────
    if stats.summons_fired >= 1:
        award("you_called")

    # ── STORY WEAVER ──────────────────────────────────────────────────────────
    if stats.campaigns_created >= 1:
        award("sw_if_you_build_it")
    if stats.campaigns_created >= 3:
        award("sw_oh_baby_triple")
    if stats.npcs_created >= 10:
        award("sw_usual_suspects")
    if stats.npcs_created >= 25:
        award("sw_names_tombstones")
    if stats.npc_damage_dealt >= 1:
        award("sw_allow_me")
    if stats.scene_updates >= 1:
        award("sw_let_there_be_light")
    if stats.scene_updates >= 25:
        award("sw_changes")
    if stats.lore_entries_created >= 1:
        award("sw_once_upon_a_time")
    if stats.lore_entries_created >= 10:
        award("sw_sacred_texts")
    if stats.images_shared >= 1:
        award("sw_are_you_visualizing")
    if stats.images_shared >= 10:
        award("sw_every_picture")
    if stats.battles_initiated >= 10:
        award("sw_good_to_be_king")

    # ── BADGE SHOWCASE UNLOCK ─────────────────────────────────────────────────
    # Calculate total points from all earned achievements (including this session)
    all_earned = earned | set(newly_awarded)
    total_points = sum(
        ACHIEVEMENTS[aid]["points"]
        for aid in all_earned
        if aid in ACHIEVEMENTS and aid != "badges_we_aint_got"
    )
    if total_points >= BADGE_SHOWCASE_THRESHOLD:
        award("badges_we_aint_got")

    if newly_awarded:
        db.commit()
        # Create notification rows for each newly earned achievement
        try:
            from backend.notification_center import notify_achievement
            for aid in newly_awarded:
                notify_achievement(db, user_id, aid, silent=silent)
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"notify_achievement failed: {e}")

    return newly_awarded
