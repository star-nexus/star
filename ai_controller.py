import os
from typing import Optional, List, Tuple

class AIController:
    def __init__(self):
        self.action_file = "run_log/unit_action.txt"
        
    def load_actions(self) -> List[Tuple[int, str, tuple]]:
        """
        Load and parse actions from the action file.
        Returns list of (unit_id, action_type, params) tuples.
        """
        if not os.path.exists(self.action_file):
            return []
            
        actions = []
        with open(self.action_file, "r") as f:
            for line in f.readlines():
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                    
                unit_id = int(parts[0])
                action = parts[1]
                
                if action == "move" and len(parts) == 4:
                    params = (int(parts[2]), int(parts[3]))
                    actions.append((unit_id, action, params))
                elif action == "attack" and len(parts) == 3:
                    params = int(parts[2])
                    actions.append((unit_id, action, params))
                    
        return actions

    def execute_actions(self, game_controller):
        """
        Execute all pending AI actions
        """
        actions = self.load_actions()
        for unit_id, action, params in actions:
            game_controller.unit_controller.execute_action(unit_id, action, params) 

        for uid, (uy, ux, ut) in game_controller.unit_controller.unit_id_map.copy().items():
            # 为了处理多个单位，可暂时选中相应unit_id，再step
            game_controller.unit_controller.selected_unit_index = uid
            game_controller.unit_controller.step_along_path()  # 每秒走一步
            # 攻击逻辑如有需要在step_along_path或execute_action里触发