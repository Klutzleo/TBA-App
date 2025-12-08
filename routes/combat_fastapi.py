"""
TBA v1.5 Combat API endpoints (Phase 1 MVP).
FastAPI router with async handlers, request_id preservation, multi-die combat resolution.
"""

from fastapi import APIRouter, Body, Request, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
from routes.schemas.combat import (
    CombatReplayRequest,
    CombatEchoRequest,
    AttackRequest,
    AttackResult,
    InitiativeRequest,
    InitiativeResult,
    InitiativeRoll,
    Encounter1v1Request,
    Encounter1v1Result,
    RoundAction,
    IndividualRollResult
)
from backend.roll_logic import resolve_multi_die_attack, roll_die
import logging
import random
import re
from schemas.loader import CORE_RULESET
from backend.utils.storage import store_roll  # Keep this if backend/utils/storage.py exists

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/combat", tags=["Combat"])

# Temporary in-memory store for combat logs
combat_log_store: List[Dict[str, Any]] = []

# Pydantic schema for a combat log entry
class CombatLogEntry(BaseModel):
    actor: str
    timestamp: str
    context: str | None = None
    triggered_by: str | None = None
    narration: str | None = None
    action: Dict[str, Any] | None = None
    roll: Dict[str, Any] | None = None
    outcome: str | None = None
    tethers: List[str] | None = None
    log: List[Dict[str, Any]] | None = None

# POST endpoint to record a combat log entry
@router.post("/log", response_model=Dict[str, Any])
async def post_combat_log(entry: CombatLogEntry = Body(...)):
    combat_log_store.append(entry.model_dump())
    return {
        "message": "Combat log entry recorded",
        "entry": entry.model_dump(),
        "total_entries": len(combat_log_store)
    }

# GET endpoint to retrieve the most recent combat logs
@router.get("/log/recent", response_model=Dict[str, Any])
async def get_recent_combat_logs():
    return {
        "entries": combat_log_store[-10:]
    }

@router.post("/replay", response_model=Dict[str, Any])
async def replay_combat(data: CombatReplayRequest = Body(...)):
    filtered = []

    for entry in combat_log_store:
        if data.actor and entry.get("actor") != data.actor:
            continue
        if data.encounter_id and entry.get("context") != data.encounter_id:
            continue
        if data.since and entry.get("timestamp") < data.since:
            continue
        filtered.append(entry)

    narration = []
    for e in filtered:
        narration.append(e.get("narration") or f"{e['actor']} acted at {e['timestamp']}.")

    return {
        "count": len(filtered),
        "narration": narration,
        "entries": filtered
    }

@router.post("/echoes", response_model=Dict[str, Any])
async def combat_echoes(data: CombatEchoRequest = Body(...)):
    echoes = []

    for entry in combat_log_store:
        if data.actor and entry.get("actor") != data.actor:
            continue
        if data.encounter_id and entry.get("encounter_id") != data.encounter_id:
            continue
        if data.since and entry.get("timestamp") < data.since:
            continue
        if data.tether and data.tether not in (entry.get("tethers") or []):
            continue

        echoes.append({
            "source": entry.get("timestamp"),
            "actor": entry.get("actor"),
            "tether": data.tether,
            "narration": entry.get("narration"),
            "bonus_hint": f"Echo from '{data.tether}' may grant advantage or emotional surge."
        })

    return {
        "count": len(echoes),
        "echoes": echoes
    }


@router.post("/attack", response_model=AttackResult)
async def attack(request: Request, req: AttackRequest):
    """
    Resolve multi-die attack (TBA v1.5).
    
    Each attacker die rolls individually vs defender's defense die.
    Damage = sum of positive margins.
    
    Example:
        Attacker: 3d4, Defender: 1d8
        Roll 1: 2 vs 7 → -5 → 0 damage
        Roll 2: 4 vs 2 → +2 → 2 damage
        Roll 3: 4 vs 1 → +3 → 3 damage
        Total: 5 damage
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Attack request: {req.attacker.name} vs {req.defender.name}")
    
    try:
        # Extract attacker stat value based on technique type
        attacker_stat_value = getattr(req.attacker.stats, req.stat_type.lower())
        defender_stat_value = getattr(req.defender.stats, req.stat_type.lower())
        
        # Get weapon bonus (Phase 2 feature, currently 0)
        weapon_bonus = req.attacker.weapon.bonus_damage if req.attacker.weapon else 0
        
        # Resolve multi-die attack
        result = resolve_multi_die_attack(
            attacker={"name": req.attacker.name},
            attacker_die_str=req.attacker.attack_style,
            attacker_stat_value=attacker_stat_value,
            defender={"name": req.defender.name},
            defense_die_str=req.defender.defense_die,
            defender_stat_value=defender_stat_value,
            edge=req.attacker.edge,
            bap_triggered=req.bap_triggered,
            weapon_bonus=weapon_bonus
        )
        
        # Apply damage to defender
        new_dp = max(0, req.defender.dp - result["total_damage"])
        
        logger.info(
            f"[{request_id}] {req.attacker.name} dealt {result['total_damage']} damage "
            f"to {req.defender.name} (DP: {req.defender.dp} → {new_dp})"
        )
        
        # Map to Pydantic response
        return AttackResult(
            type=result["type"],
            attacker_name=result["attacker_name"],
            defender_name=result["defender_name"],
            individual_rolls=[
                IndividualRollResult(**roll) for roll in result["individual_rolls"]
            ],
            total_damage=result["total_damage"],
            outcome=result["outcome"],
            narrative=result["narrative"],
            defender_new_dp=new_dp,
            details=result["details"]
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Attack error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Attack resolution failed: {str(e)}")


@router.post("/roll-initiative", response_model=InitiativeResult)
async def roll_initiative_endpoint(request: Request, req: InitiativeRequest):
    """
    Roll initiative for multiple combatants (TBA v1.5).
    
    Formula: 1d6 + Edge
    Tiebreakers: PP → IP → SP (highest wins)
    
    Returns initiative order (highest to lowest).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Initiative request for {len(req.combatants)} combatants")
    
    try:
        rolls = []
        
        for combatant in req.combatants:
            initiative_roll = roll_die("1d6")
            total = initiative_roll + combatant.edge
            
            rolls.append(
                InitiativeRoll(
                    name=combatant.name,
                    initiative_roll=initiative_roll,
                    edge=combatant.edge,
                    total=total,
                    pp=combatant.stats.pp,
                    ip=combatant.stats.ip,
                    sp=combatant.stats.sp
                )
            )
        
        # Sort by total (desc), then PP → IP → SP (desc)
        rolls.sort(key=lambda r: (-r.total, -r.pp, -r.ip, -r.sp))
        
        initiative_order = [r.name for r in rolls]
        
        logger.info(f"[{request_id}] Initiative order: {', '.join(initiative_order)}")
        
        return InitiativeResult(
            initiative_order=initiative_order,
            rolls=rolls
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Initiative error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Initiative roll failed: {str(e)}")


@router.post("/encounter-1v1", response_model=Encounter1v1Result)
async def encounter_1v1(request: Request, req: Encounter1v1Request):
    """
    Simulate full 1v1 encounter (multi-round combat).
    
    - Rolls initiative
    - Alternates attacks until one combatant reaches 0 DP or max_rounds exceeded
    - Returns round-by-round breakdown + final outcome
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(
        f"[{request_id}] 1v1 encounter: {req.attacker.name} vs {req.defender.name} "
        f"(max {req.max_rounds} rounds)"
    )
    
    try:
        # Roll initiative
        combatants = [req.attacker, req.defender]
        initiative_rolls = []
        
        for combatant in combatants:
            initiative_roll = roll_die("1d6")
            total = initiative_roll + combatant.edge
            initiative_rolls.append({
                "name": combatant.name,
                "roll": initiative_roll,
                "edge": combatant.edge,
                "total": total,
                "pp": combatant.stats.pp,
                "ip": combatant.stats.ip,
                "sp": combatant.stats.sp
            })
        
        # Sort by initiative
        initiative_rolls.sort(key=lambda r: (-r["total"], -r["pp"], -r["ip"], -r["sp"]))
        initiative_order = [r["name"] for r in initiative_rolls]
        
        logger.info(f"[{request_id}] Initiative: {', '.join(initiative_order)}")
        
        # Track DP
        attacker_dp = req.attacker.dp
        defender_dp = req.defender.dp
        
        rounds = []
        round_num = 1
        
        while round_num <= req.max_rounds and attacker_dp > 0 and defender_dp > 0:
            round_actions = []
            
            for actor_name in initiative_order:
                if attacker_dp <= 0 or defender_dp <= 0:
                    break
                
                # Determine actor and target
                if actor_name == req.attacker.name:
                    actor = req.attacker
                    target = req.defender
                    actor_current_dp = attacker_dp
                    target_current_dp = defender_dp
                else:
                    actor = req.defender
                    target = req.attacker
                    actor_current_dp = defender_dp
                    target_current_dp = attacker_dp
                
                # Resolve attack
                attacker_stat_value = getattr(actor.stats, req.stat_type.lower())
                defender_stat_value = getattr(target.stats, req.stat_type.lower())
                weapon_bonus = actor.weapon.bonus_damage if actor.weapon else 0
                
                result = resolve_multi_die_attack(
                    attacker={"name": actor.name},
                    attacker_die_str=actor.attack_style,
                    attacker_stat_value=attacker_stat_value,
                    defender={"name": target.name},
                    defense_die_str=target.defense_die,
                    defender_stat_value=defender_stat_value,
                    edge=actor.edge,
                    bap_triggered=False,
                    weapon_bonus=weapon_bonus
                )
                
                damage = result["total_damage"]
                
                # Apply damage
                if actor_name == req.attacker.name:
                    defender_dp = max(0, defender_dp - damage)
                    target_current_dp = defender_dp
                else:
                    attacker_dp = max(0, attacker_dp - damage)
                    target_current_dp = attacker_dp
                
                round_actions.append(
                    RoundAction(
                        actor_name=actor.name,
                        target_name=target.name,
                        technique=req.technique_name,
                        damage=damage,
                        narrative=result["narrative"],
                        actor_dp=actor_current_dp,
                        target_dp=target_current_dp
                    )
                )
                
                logger.info(
                    f"[{request_id}] Round {round_num}: {actor.name} → {target.name} "
                    f"({damage} damage, DP: {target_current_dp})"
                )
            
            rounds.append(round_actions)
            round_num += 1
        
        # Determine outcome
        if attacker_dp > defender_dp:
            outcome = "attacker_wins"
            summary = f"{req.attacker.name} defeats {req.defender.name} after {len(rounds)} rounds!"
        elif defender_dp > attacker_dp:
            outcome = "defender_wins"
            summary = f"{req.defender.name} defeats {req.attacker.name} after {len(rounds)} rounds!"
        else:
            outcome = "timeout"
            summary = f"Battle ends in a draw after {len(rounds)} rounds (max rounds reached)."
        
        logger.info(f"[{request_id}] Encounter complete: {outcome}")
        
        # Lore summary (COMMENTED OUT)
        # lore_summary = []
        # for r in range(1, len(rounds) + 1):
        #     lore_summary.extend(get_lore_by_round(r))
        lore_summary = []  # TODO: Migrate to new combat_log_store system
        
        return Encounter1v1Result(
            type="encounter_1v1",
            initiative_order=initiative_order,
            rounds=rounds,
            round_count=len(rounds),
            final_dp={
                req.attacker.name: attacker_dp,
                req.defender.name: defender_dp
            },
            outcome=outcome,
            summary=summary,
            lore=lore_summary  # Include empty lore summary
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Encounter error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Encounter simulation failed: {str(e)}")