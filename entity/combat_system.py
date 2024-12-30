import random
from typing import Dict, Tuple, Optional

class CombatSystem:
    """
    Handles combat resolution and related calculations.
    Determines combat outcomes based on unit types and manages combat execution.
    """
    
    def __init__(self, unit_stats: Dict):
        """
        Initialize combat system with unit stats.
        
        Args:
            unit_stats: Dictionary defining unit type relationships
        """
        self.unit_stats = unit_stats

    def is_enemy(self, unit_type1: str, unit_type2: str) -> bool:
        """
        Check if two units are enemies based on their faction.
        
        Args:
            unit_type1: First unit's type (e.g., 'R_ping')
            unit_type2: Second unit's type (e.g., 'W_shui')
            
        Returns:
            True if units are enemies, False otherwise
        """
        return ((unit_type1.startswith("R_") and unit_type2.startswith("W_")) or
                (unit_type1.startswith("W_") and unit_type2.startswith("R_")))

    def compute_combat_outcome(self, attacker_type: str, defender_type: str) -> str:
        """
        Determine the winner of a combat based on unit types.
        
        Args:
            attacker_type: Type of attacking unit
            defender_type: Type of defending unit
            
        Returns:
            Type of the winning unit
        """
        att_faction, att_type = attacker_type.split("_", 1)
        def_faction, def_type = defender_type.split("_", 1)

        att_data = self.unit_stats[att_type]
        def_data = self.unit_stats[def_type]

        if (att_data["strong_against"] == def_type and 
            def_data["strong_against"] == att_type):
            return random.choice([attacker_type, defender_type])
        elif att_data["strong_against"] == def_type:
            return attacker_type
        elif def_data["strong_against"] == att_type:
            return defender_type
        return random.choice([attacker_type, defender_type])

    def resolve_combat(self, 
                      attacker_id: int,
                      attacker_type: str,
                      defender_id: int,
                      defender_type: str,
                      defender_pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Resolve combat between two units and determine the outcome.
        
        Args:
            attacker_id: ID of attacking unit
            attacker_type: Type of attacking unit
            defender_id: ID of defending unit
            defender_type: Type of defending unit
            defender_pos: Position (y, x) of defending unit
            
        Returns:
            Tuple of (winner_id, loser_id)
        """
        winner_type = self.compute_combat_outcome(attacker_type, defender_type)
        
        if winner_type == attacker_type:
            return attacker_id, defender_id
        else:
            return defender_id, attacker_id 