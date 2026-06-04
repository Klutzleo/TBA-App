TOOLS FOR THE BAD ASS
Achievement System Design
Version 0.4 — WORKING DRAFT
Now with Broadcast Flags, Rarity, UX Spec & Firsts
GameOctane.com
v0.4 LOCKED: Broadcast flags per achievement, rarity display spec, UX spec (toast/bell/drawer), 
GameOctane flame confirmed for Founding badge, Firsts achievements added. SW name pass and 
broadcast flags per SW achievement still pending.
CRITICAL FEATURE: STAT CHECK TRACKING

REQUIRED BEFORE ACHIEVEMENT LAUNCH
Stat checks (PP/IP/SP rolls outside combat) currently happen verbally and nothing gets logged. This 
blocks 10+ achievements from shipping. See separate CC prompt for full feature spec. Short version: 
/check PP, /check IP, /check SP commands that route through the platform like combat rolls.
Achievements blocked until stat check tracking ships:
•  Put... the Candle... Back! — roll a 1 on PP
•  We Ain't Found Sh*t! — roll a 1 on IP
•  You Can't Handle the Truth — roll a 1 on SP
•  These Aren't the Droids You're Looking For — max roll on SP
•  Cinderella Story — max roll with stat 1 on a stat check
•  Do or Do Not — succeed while debuffed
•  That's No Moon... — roll 0 or below after debuffs
•  We Ain't Found Sh*t! (IP 1) — failed IP check
BADGE DISPLAY FEATURE


Players choose 3-5 earned achievements to display prominently on their profile. The ones that tell 
their story. Everyone sees your trophy case but YOU choose what leads.


"Badges? We Ain't Got No Badges!" — the achievement that unlocks the badge display feature. Earn 
enough badges, now you can show them off. The feature is the reward.





FOUNDING ACHIEVEMENTS


















Achievement
OG

Day One Early Adopter


















Trigger
Account created during alpha/beta (2025–2026)
Account created during launch month
Account created during launch year


















Tier
Founding Founding Founding


















Data Field
account_created_a t
account_created_a t
account_created_a t


















Notes
Frozen forever
































TIME-BASED ACHIEVEMENTS

Account Age








































Achievement
Welcome to TBA Part of Something Here to Stay Committed
True Believer








































Trigger
Account is 7 days old Account is 30 days old Account is 90 days old Account is 1 year old Account 
is 2 years old








































Tier
Easy Easy Medium Hard Prestige








































Data Field
account_created_a t
account_created_a t
account_created_a t
account_created_a t
account_created_a t








































Notes


Campaign Age (SW)



Achievement
The Story Begins Still Going
The Long Game Half a Year
Life Moves Pretty Fast...


One Year Strong The Epic
A Living World



Trigger
Campaign is 7 days old Campaign is 30 days old Campaign is 90 days old Campaign is 180 days old
Active campaign, player MIA 30+ days

Campaign is 1 year old Campaign is 2 years old Campaign is 3 years old



Tier
Easy Easy Medium Hard Narrative

Prestige Prestige Prestige



Data Field
campaign.created_ at
campaign.created_ at
campaign.created_ at
campaign.created_ at
campaign.created_ at + last_login

campaign.created_ at
campaign.created_ at
campaign.created_ at



Notes
SW only SW only SW only SW only
Ferris Bueller. Wake up.
SW only SW only SW only



























Character Age
Character age achievements only unlock if character started at level 1. Minimum 3 days per level 
required.


































Achievement
Newborn

Finding My Footing Seasoned
Veteran of Time The Old Guard Living Legend Timeless


































Trigger
Character is 7 days old Character is 30 days old Character is 90 days old Character is 180 days old 
Character is 1 year old Character is 2 years old Character is 3 years old


































Tier
Easy Easy Medium Hard Prestige Prestige Prestige


































Data Field
character.created_ at
character.created_ at
character.created_ at
character.created_ at
character.created_ at
character.created_ at
character.created_ at


































Notes
Must start level 1
Must start level 1
Must start level 1
Must start level 1
Must start level 1
Must start level 1
Must start level 1


LEVEL ACHIEVEMENTS

ANTI-EXPLOIT
Level achievements only unlock if: (1) character started at level 1, AND (2) minimum 3 days per 
level elapsed.











Achievement
It's Alive... IT'S ALIVE

Level Up Halfway There Legendary Ascended True Legend











Trigger
Create your first character Reach level 2
Reach level 5

Reach level 10

Reach level 11

Reach level 15











Tier
Easy Easy Medium Hard Prestige Prestige











Data Field
character.created_ at
character.level + created_at
character.level + created_at
character.level + created_at
character.level + created_at
character.level + created_at











Notes
Frankenstein

First one feels special



Must start level 1
v3.0

v3.0. Nobody yet.
































COMBAT ACHIEVEMENTS

Attacks & Damage








































Achievement
Say Hello to My Little Friend
First Blood Keep Swingin’
…Maybe You’ll Give ‘Em a Cold
I Spent WHAT

War Machine Unstoppable








































Trigger
Cast first spell/technique

Land first attack Miss your first attack
Miss 10 attacks total
Miss while BAP active 100 attacks made
500 attacks made








































Tier
Easy

Easy Easy
Medium

Shame

Medium Hard








































Data Field
total_abilities_cast

total_attacks miss events
miss events

bap_miss_count*

total_attacks total_attacks








































Notes
Scarface



Mighty Ducks pt.1
Mighty Ducks pt.2
The real stinger


Wrath Incarnate

And I Took That Personally It's Good to Be the King

Deal 1000 total damage

Single hit exceeds target max DP
Initiate X battles as SW

Hard Narrative SW

total_damage_deal t
biggest_hit_dealt vs target max_dp
battles_initiated*



MJ. Overkill. Mel Brooks









Survival












Achievement
Survivor
Shaken, Not Stirred

Go Ahead, Make My Day Yo, Adrian
It Ain’t About How Hard You Hit
Houston, We Have a Problem
Failure Is Not an Option

Veteran Grizzled












Trigger
Survive first battle
Survive battle with whole party under 50% DP
Survive being attacked at 25% or less DP
Survive 10 battles taking 25%+ max DP damage
Survive 25 battles taking 25%+ max DP damage
Be last character standing in combat
WIN as last character standing

Survive 10 battles
Survive 25 battles












Tier
Easy Medium
Narrative Hard Prestige Narrative Hard
Medium Hard












Data Field battles_survived party_dp_tracking*
hp_at_attack + survived
damage_per_battl e*
damage_per_battl e*
party_dp_tracking* party_dp_tracking*
battles_survived battles_survived












Notes


James Bond Dirty Harry Rocky pt.1 Rocky pt.2 Apollo 13
Apollo 13 pt.2



































Enemy Levels






































Achievement
That’s No Bigger Than a Womp Rat
I Used to Bull’s-Eye Womp Rats Back Home






































Trigger
Defeat enemy 2+ levels below you
Defeat enemy 2+ levels above you






































Tier
Easy Prestige






































Data Field
enemy_level vs char_level*
enemy_level vs char_level*






































Notes
Star Wars. Bully.
Star Wars. Underdog.















































Abilities & BAP

















































Achievement Technique Master That Was Badass
Great Kid, Don’t Get Cocky

















































Trigger
Cast 100 abilities Receive BAP for first time
Receive BAP twice in single battle

















































Tier
Medium Easy Narrative

















































Data Field total_abilities_cast total_bap_used bap_per_battle*

















































Notes




Star Wars


Born For This        Receive BAP 50 times total    Hard     total_bap_used



Friendly Fire







Achievement
Gentlemen, You Can’t Fight in Here! This is the War Room!
Never Know What You’re Gonna Get







Trigger
Initiate combat vs party member


Hit ally with AOE ability







Tier
Narrative



Narrative







Data Field
pvp_combat_initiat ed*

aoe_ally_hit*







Notes
Dr. Strangelove

Forrest Gump. Direction TBD.





















DICE & ROLL ACHIEVEMENTS

Volume





























Achievement
You Had Me at /roll

Getting Started Dice Goblin
Committed to the Craft





























Trigger
Roll first stat check

Roll 100 dice total Roll 500 dice total Roll 1000 dice total





























Tier
Easy

Easy Medium Hard





























Data Field
total_stat_checks

total_rolls total_rolls total_rolls





























Notes
Jerry Maguire








































Natural Max Rolls











































Achievement
These Aren’t the Droids You’re Looking For


Blessed
Touched by the Gods
Cinderella Story. Outta Nowhere...











































Trigger
Natural max on SP check



Land 10 natural max rolls Land 25 natural max rolls
Natural max with stat 1 on a STAT CHECK











































Tier
Narrative




Medium Hard Prestige











































Data Field
sp_check_outcom es*


total_max_rolls total_max_rolls
stat_maxes + stat_value*











































Notes
Star Wars. Needs stat check tracking.




Caddyshack. Needs stat check tracking.


INCONCEIVABLE


Never Tell Me the Odds

Natural max with stat 1 in COMBAT

Natural max with stat 1 during The Calling

Prestige



Prestige

roll + stat_value


calling roll + stat_value*

Princess Bride. Sub 1%.
Han Solo. Highest stakes.










Critical Failures — Hall of Shame












Achievement
Keep Swingin’

Put... the Candle... Back!



You Can’t Handle the Truth


We Ain’t Found Sh*t!


That’s No Moon...


Cursed Legendarily Bad












Trigger
Miss first attack

Roll a 1 on PP check



Roll a 1 on SP check


Roll a 1 on IP check


Roll 0 or below after debuffs


Roll 10 ones total Roll 25 ones total












Tier
Easy Shame


Shame



Shame



Shame



Medium Hard












Data Field
miss events

pp_check_outcom es*


sp_check_outcom es*

ip_check_outcome s*

final_roll_total*


total_ones total_ones












Notes
Mighty Ducks pt.1
Young Frankenstein. Needs stat tracking.
A Few Good Men. Needs stat tracking.
Spaceballs. Needs stat tracking.
Star Wars. Needs stat tracking.


They keep going





































Stat-Specific Moments







































Achievement
I See Your Schwartz is as Big as Mine!
Do or Do Not


Sucking at Something...

...Is the First Step Towards Being Sorta Good
Now You See That Evil Will Always Triumph







































Trigger
Tie roll in combat

Succeed on a check while debuffed

Roll a failure on any check

Fail then immediately succeed same check type
SW deals more damage than party in one day







































Tier
Narrative Narrative

Easy Narrative SW







































Data Field
tie_roll_events*

checks_succeeded
_debuffed* any failed roll
consecutive check outcomes*
npc_damage vs party_damage*







































Notes
Spaceballs

Star Wars. Needs stat tracking.
Jake the Dog pt.1
Jake the Dog pt.2
Spaceballs. SW only.


THE CALLING ACHIEVEMENTS

DATA NOW LIVE
Calling outcome tracking shipped in migration 013. calling_survived_count and calling_failed_count 
are live. These achievements are ready to build.











Achievement
I’ll Be Back
Hasta La Vista, Baby Marked
Twice Marked


Death Knows My Name Death Wish
There’s No Crying in TBA I See Dead People

It Was Personal











Trigger
Survive The Calling once


Die in The Calling

Carry first Battle Scar
Carry 3 Battle Scars SIMULTANEOUSLY

Survive The Calling 5 times

Survive Calling with 3 Battle Scars active
Trigger Calling AND win encounter same turn
3 party members die in The Calling (player)

Invoke Tether AND survive Calling same day











Tier
Narrative



Narrative

Narrative Hard

Hard Prestige Narrative Hard

Prestige











Data Field
calling_survived_c ount

calling_failed_coun t
total_battle_scars
character.battle_sc ars.length*

calling_survived_c ount
calling_survived + active_scars*
calling + battle_won*
party_calling_deat hs*

tethers_invoked + calling_survived











Notes
Terminator. Cold but perfect.
Terminator pt.2. Ice cold.


Live count not lifetime total



Held together with tape
A League of Their Own
Sixth Sense. Player version.
The
shirt-worthy one. Data is live.











































STORY & NARRATIVE ACHIEVEMENTS
















































Achievement
Once Upon a Time In Character
















































Trigger
Send first Story message

Send 10 IC messages in one day
















































Tier
Easy Easy
















































Data Field
total_messages_s ent
daily_messages
















































Notes



Async-friendl y


Finding My Voice The Voice
Whisper Secrets Keep @Mentioned
Called Out Ghost Story

Night Owl

A Party Forms


Full House

You’re Gonna Need a Bigger Boat

Send 100 messages total Send 500 messages total
Send first whisper Send 10 whispers total
Get @mentioned by another player
Get @mentioned 10 times

Send message after midnight local time

Send 50 messages after midnight
4+ players simultaneously connected

6+ players simultaneously connected
Campaign hits max player count

Medium Hard
Easy Medium Easy
Medium Narrative

Hard Narrative

Prestige Narrative

total_messages_s ent
total_messages_s ent
whispers_sent* whispers_sent*
mentions_received
*
mentions_received
*
message timestamp

message timestamp
concurrent_connec tions*

concurrent_connec tions*
campaign.player_c ount













Jason has this one already



Communal. Everyone gets it.
Rare. A SW flex.
Jaws
































LOOT & ITEM ACHIEVEMENTS





































Achievement
My Precious

I’m Gonna Make Him an Offer He Can’t Refuse
Generous (SW)





































Trigger
Receive first item from Loot Pool
Submit character for SW approval
Gift item to a player





































Tier
Easy Easy Easy





































Data Field
items_received

character_submitte d
items_gifted





































Notes
Lord of the Rings
Godfather SW only


















































PLATFORM EXPLORATION

Achievement        Trigger              Tier     Data Field      Notes


If You Build It, They Will Come
Welcome to the Party, Pal It’s a Trap!


Lurker Lorekeeper Archivist Prepared Treasure Hunter All In
Heads Up

Quick Reference By The Rules
Badges? We Ain’t Got No Badges!

Create first campaign

Join a campaign
Roll initiative as first action in campaign

Open OOC tab first time Open Lore tab first time Open Images tab first time Open Notes tab first 
time Open Loot Pool tab first time Open every tab in one day Enable notifications
Open ? help panel Click Rules button
Unlock badge display feature

Easy

Easy Narrative


Easy Easy Easy Easy Easy Medium Easy
Easy Easy Medium

campaigns_create d
campaigns_joined first_action_type*


tab_opened* tab_opened* tab_opened* tab_opened* tab_opened* tab_opened*
notification_enable d
help_opened* rules_opened*
achievement_coun t threshold

Field of Dreams
Die Hard
Star Wars. Immediate combat.


















Sierra Madre. Unlocks profile badge equip.

































COMPANION ACHIEVEMENTS





































Achievement
Bonded You Called?
Never Alone

I See Dead People (SW)





































Trigger
Acquire an Ally
Fire a summon first time
Have Ally and summon active simultaneously
Preside over 3 player deaths in campaigns





































Tier
Easy Easy Medium
Hard





































Data Field ally_created summons_fired*
ally + summon tracking*
calling_deaths_in_ campaigns*





































Notes







Sixth Sense. SW version.




















































STORY WEAVER ACHIEVEMENTS


PENDING: SW NAME PASS
SW achievements exist and are fully designed but have not received the movie quote / personality 
name treatment yet. All other categories have been named. SW names are harder — they need to feel 
like a GM flexing, not a player celebrating. Flagged for next session.







Achievement
If You Build It, They Will Come
The Architect

Universe
Open For Business They Talk About You The Community
Cast of Thousands They Have Names The Villain
Boss Fight The Setup Atmosphere Scene Setter
The World Lives Lore Keeper The Library
Show Don’t Tell Visual Storyteller
Secrets and Lies The Puppet Master
NPC Whisperer







Trigger
Create first campaign Run 3 campaigns
Run 5 simultaneous campaigns Public campaign with 4+ players
10 unique players across campaigns
25 unique players across campaigns
Create 10 NPCs
Create 25 NPCs
Deal damage as NPC

NPC survives 3 rounds vs full party
Use environmental damage first time
Use 3 env damage tiers in one campaign
Update Scene description first time
Update Scene 25 times Write a Lore entry Write 10 Lore entries
Share image in session
Share 10 images across campaigns
Send first whisper to player
Whisper to every player in one session
Speak as 5 NPCs in one day







Tier
Easy Medium
Hard Medium
Hard Prestige
Medium Hard Easy
Hard Easy Medium Easy Hard Easy Medium
Easy Medium
Easy Hard
Medium







Data Field
campaigns_create d
campaigns_create d
active_campaigns
campaign.player_c ount
unique_players unique_players
npcs_created npcs_created
npc_damage_dealt
*
npc_rounds_surviv ed*
env_damage_used env_damage_tiers scene_updated*
scene_update_cou nt*
lore_entries_create d
lore_entries_create d
images_shared images_shared
sw_whispers_sent* sw_whispers_sent*
npc_messages*







Notes
Field of Dreams


Now You See That Evil Will Always Triumph
It’s Good to Be the King Cruel But Fair

They Lived Master Weaver
You Made Something Real The Legend
Roads? Where We’re Going We Don’t Need Roads

SW deals more damage than party in one day
Initiate X battles as SW
Player dies in The Calling in your campaign
Player survives The Calling in your campaign
Player reaches level 10 in your campaign
Campaign hits 100+ story messages
Campaign reaches 1 year old

Campaign outlasts expected lifespan (1 year+)

Narrative

Medium Narrative

Narrative Prestige Hard Prestige Prestige

npc_damage vs party_damage*
battles_initiated*
calling_failed_coun t
calling_survived_c ount
max_player_level

campaign_messag e_count
campaign.created_ at
campaign.created_ at

Spaceballs Mel Brooks












Back to the Future

























BROADCAST SPECIFICATION

Every achievement has a broadcast tier that determines how and where it announces. This is baked in 
at build time alongside point values — not configurable post-launch.

































Broadcast Tier
Personal (Silent) Campaign Global

































How It Fires
Toast slides up bottom-right, fades after 5 seconds
Slides in above chat input, visible 10 seconds, no channel pollution
Notification bell gets red dot, grouped in dedicated feed page

































Who Sees It
Only you

Your entire active campaign party All TBA players on the platform












































Tier
Easy / Onboarding Shame
Time-based Medium Hard
Narrative drops












































Broadcast Level Personal (Silent) Personal (Silent) Personal (Silent) Campaign Campaign Campaign












































Rationale
Nobody needs to know you opened the Lore tab Hall of Shame is between you and the dice Account age 
milestones are noise to others Your party cares, strangers don't yet
Commitment required — your table earned this moment too
It Was Personal, Houston We Have a Problem — the table was there


Two-part arc completions
SW achievements Prestige Founding / OG First-ever unlocks

Campaign

Campaign Global Global Global

The punchline lands best at your own table

Your players should see you hit Master Weaver INCONCEIVABLE and True Legend are platform moments 
Historic — announce at cutoff
First player EVER to earn True Legend gets a global broadcast












CAMPAIGN BROADCAST FORMAT
Slides in ABOVE the chat input — not inside any channel. Stays 10 seconds then dissolves. The story 
channel stays clean. This is a system-level event, not a chat message.



GLOBAL BROADCAST FORMAT
Notification bell gets red dot. On login, notifications are GROUPED — not individual spam. Example: 
"While you were away: 3 campaign achievements, 1 global prestige unlock, 2 new players joined your 
campaign." Expandable if you want details. Dedicated feed page shows platform-wide prestige 
moments.





RARITY DISPLAY SPECIFICATION

Every achievement badge displays the percentage of all TBA players who have earned it. This number 
IS the bragging right. A 0.031% badge hits different than a 45% badge. Three decimal places on 
ultra rare.







































Rarity Tier Common Uncommon Rare
Ultra Rare Legendary







































Threshold
> 25% of players 10% – 25%
1% – 10%
< 1%
< 0.1%







































Visual Treatment
No special treatment — just the percentage number Subtle gold tint on the percentage
Percentage glows
Different color entirely — three decimal places shown Special badge treatment — animated border or 
pulse

















































Rarity is calculated live from real player data. It shifts over time — a badge that was Rare at 
launch may become Uncommon as more players earn it. The percentage shown is always current.


EXAMPLE
INCONCEIVABLE (natural max with stat 1 in combat, sub 1% base probability) will show something like 
"0.031%" at launch — gold, glowing, three decimals. That number on your profile is the flex.





LOG DRAWER — PERMANENT RECORD

A persistent drawer (slides from the right) serves as the permanent record of everything the 
platform does. It is the session receipt and the source of truth.


















What Gets Logged All die rolls Achievement unlocks Level ups
BAP grants
Effects applied and expired Loot awarded
Scene changes Player joins / leaves


















Notes
Stat checks, combat, The Calling — every single roll With rarity % at the moment it fired — 
preserved forever


































The drawer is NOT a channel — it does not pollute Story or OOC. It is accessed via a scroll/history 
icon in the header. Click it, the drawer slides out from the right. Invisible when you don't need 
it.


WHY THIS MATTERS
"Did I actually roll that?" arguments are dead forever. Session recaps write themselves. 
Achievement hunters can review their roll history. The rarity % on every achievement is preserved 
at the exact moment it fired. The Log Drawer is the reason achievement tracking is trustworthy.





BADGE DISPLAY & SHAPE SPECIFICATION


Players choose 3–5 earned achievements to display prominently on their profile. The badge shapes 
are baked into each category — you see the shape and instantly know the category before reading a 
word.






Category
Combat
Story / Narrative Shame / Hall of Shame The Calling
Dice / Rolls Founding / OG

Prestige
SW (Story Weaver) Time-based
Platform / Exploration Companions / Ally
Level
v3.0 Bonds / Combos






Badge Shape Burst / impact Speech bubble Broken die Cracked hourglass d6 shape
GameOctane blue flame

Crown Open book Hourglass Compass Two figures
Mountain peak Interlocked rings






Notes
Action, aggression — works in any genre Words, moments, connection
You know what you did Death adjacent. Heavy. Obviously a die
SVG asset confirmed in hand — ships as actual brand mark
Reserved. Only the hardest achievements. The craft of running
Clean, universal
You found something


Upward, earned Requires v3.0






























FOUNDING BADGE CONFIRMED
The GameOctane SVG (GOcontMR.svg) has been located and confirmed. It is a proper vector asset
— scales perfectly at any size. CC should extract the flame mark and ship it as the Founding badge. 
Someone who was here in 2025 gets the actual GameOctane brand mark on their profile forever.



GRAPHICS TIER PLAN
Tier 1 (launch): Lucide icon + category color + correct shape. Fast to build, consistent, looks 
intentional. Tier 2 (post-launch): Custom illustrated badges for the iconic ones — INCONCEIVABLE, 
It Was Personal, Death Knows My Name, OG. Commission or generate as the game grows.


"Badges? We Ain’t Got No Badges!" — the achievement that UNLOCKS the badge display feature. Earn 
enough badges, now you can show them off. The feature is the reward.




FIRSTS ACHIEVEMENTS


Every player has a true first time for everything. These fire once, never again. They are the 
onboarding layer that makes the platform feel alive from turn one.





Achievement
"Welcome to the Party, Pal"


"I’m Gonna Make Him an Offer He Can’t Refuse"


"Say Hello to My Little Friend"

"First Blood"

"You Had Me at /roll"



"It’s a Trap!"


"My Precious"



"I’ll Be Back"


"I’ve Got a Bad Feeling About This"


"May the Odds Be Ever in Your Favor"


"You’re a Wizard, Harry"



"Elementary"



"Speak Softly"





Trigger
Join your first campaign



Submit first character for SW approval


Cast first ability / technique


Land first attack Roll first stat check


Roll initiative as first action in campaign

Receive first item from Loot Pool


Survive The Calling for the first time

Enter first combat



Win your first initiative roll



Use BAP for the first time



Roll first IP (Intellect) check



Roll first SP (Social) check





Tier
Easy




Easy




Easy



Easy Easy


Narrative



Easy




Narrative



Easy




Easy




Easy




Easy




Easy





Data Field
campaigns_joined



character_submitte d


total_abilities_cast


total_attacks total_stat_checks


first_action_type*


items_received



calling_survived_c ount

battles_entered_co unt*


initiative_wins*



bap_used_first_tim e*


ip_checks_total*



sp_checks_total*





Notes
Die Hard. Already exists — confirmed.
Godfather. Already exists — confirmed.
Scarface. Already exists.
Already exists.
Jerry Maguire. Already exists.
Star Wars. Already exists.
Lord of the Rings.
Already exists.
Terminator. Already exists.
Star Wars. New — needs data field.
Hunger Games. New
— needs data field.
Harry Potter. New — needs data field.
Holmes. New
— needs stat check tracking.
Theodore Roosevelt. New — needs stat




"Brute Force"



"You Have My Sword"



"That’s No Moon… Oh Wait, It Is"



Roll first PP (Physical) check



Use an Ally for the first time



Die in your first combat



Easy




Easy




Easy



pp_checks_total*



ally_used_first*



first_combat_death
*

check tracking.
New — needs stat check tracking.
Lord of the Rings. New
— needs ally tracking.
Star Wars. New — first death ever, not The Calling.





















v3.0 ACHIEVEMENTS — PLACEHOLDER

REQUIRES v3.0
Requires Bond, Combo, and Ascension tracking from v3.0 expansion. Do not implement until those 
systems ship.
































Achievement Bonded (Bond) The Move Legendary Pair
Gone But Not Forgotten As You Wish

True Legend (Achieve) The Move Evolved
































Trigger
Form first player Bond
Fire named Combo first time
Fire 10 Combos with same partner
Lose a Bond partner

SW sets scene, player responds IC within 2 min

Reach level 15

Fire Ascension Combo
































Tier Narrative Narrative Hard

Narrative Narrative

Prestige Prestige
































Data Field bonds_formed combos_fired combos_per_pair
bonds_broken

sw_post + ic_response timing*
character.level

ascension_combos
_fired
































Notes v3.0 v3.0 v3.0
v3.0. The sad one.
Princess Bride. v3.0 era.
v3.0. Nobody yet.
v3.0






















































DATA GAPS — TRACKING NEEDED


ALREADY CLOSED
Calling outcome tracking (migration 013) and level-up events (total_level_ups, 
highest_level_reached) are live as of today.


Still needed (* in tables above):









Achievement
Stat check outcomes


Miss events


Debuff received


Per-battle damage Concurrent connections Whisper tracking Mention tracking

Tab open events


BAP miss

Summons fired NPC damage dealt Scene update count
Enemy level tracking Party DP tracking Tie roll events
PvP combat events Battle initiated count









Trigger
pp/ip/sp_check_outcomes[]


miss_count + bap_miss_count


debuffs_received_count


damage_taken_per_battle[]

max_concurrent per campaign/day
whispers_sent/received mentions_received_count

tab_open_history


bap_miss_count

summons_fired_count npc_damage_dealt scene_update_count
enemy_level per encounter party_dp_snapshot per battle tie_roll_count
pvp_initiated battles_initiated by SW









Tier
Critical



High



High



High Medium Medium Medium

Low



Medium

Low Low Low
Medium Medium Low Low Low









Data Field
Blocks 10+ achievements

Blocks Keep Swingin arc + I Spent WHAT
Blocks Do or Do Not, That's No Moon
Blocks Yo Adrian arc
Blocks Full House, A Party Forms
Blocks whisper achievements
Blocks @Mentioned achievements
Blocks platform exploration achievements
Blocks I Spent WHAT
Blocks You Called? Blocks The Villain
Blocks The World Lives
Blocks Womp Rat achievements
Blocks Shaken Not Stirred, Houston
Blocks Schwartz achievement
Blocks War Room achievement
Blocks It's Good to Be the King









Notes
See CC feature prompt



















Frontend event

Miss during BAP window

TBA Achievement System v0.2 — GameOctane.com
Designed on a Monday afternoon — Built with Claude
