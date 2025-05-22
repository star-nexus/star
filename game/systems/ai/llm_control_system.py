import enum
from typing import Optional
import datetime
import time

from framework.ecs import System
from framework.engine.events import EventMessage, EventType
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger, configure
from game.components import UnitComponent, UnitState
from game.components import MapComponent
from game.components import BattleStatsComponent
from game.utils.game_types import UnitType
from pathlib import Path
import random
import requests
import yaml
import json
import math
import re

# from game.components.map import map_component


class STEP(enum.Enum):
    ORIENT = 1
    DECIDE = 2


class LLMControlSystem(System):
    def __init__(self, priority: int = 10):
        super().__init__(required_components=[UnitComponent], priority=priority)

        configure(
            level="MSG",
            enable_output=True,
            log_to_file=True,
            log_file=f"{Path(__file__).parent}/logs/{datetime.datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}.log",
        )
        self.logger = get_logger(__name__)
        self.ai_decision_cooldowns = {}  # Store AI decision cooldowns

        self.ai_targets = {}  # {ai_entity: target_entity} Store AI unit targets
        self.decision_interval = 5.0  # AI决策间隔（秒） AI decision interval (seconds)
        self.agent_type = 1  # Agent type: 1: single decision, 2: group decision, 3: mixed decision

        self.futures = {}
        self.step_status = {}
        self.chat_function = self.chat_ollama

        # Store model IDs for each faction
        self.faction_models = {
            # 1: "Qwen/Qwen3-14B",
            # 2: "Qwen/Qwen3-8B",
            # 2: "Qwen/Qwen2.5-14B-Instruct",
            # 1: "us.meta.llama4-scout-17b-instruct-v1:0",
            # # 2: "Qwen/Qwen3-235B-A22B"# "Pro/deepseek-ai/DeepSeek-V3",#
            # 2: "Pro/deepseek-ai/DeepSeek-V3" #
            2: "qwen3:8b",
            # #     "deepseek-reasoner",
            # 2: "us.amazon.nova-pro-v1:0",
            # 1: "us.meta.llama4-scout-17b-instruct-v1:0",
            1: "qwen3:32b",
            # # 2: "Qwen/Qwen3-235B-A22B"# "Pro/deepseek-ai/DeepSeek-V3",#
            # # 2: "Pro/deepseek-ai/DeepSeek-V3" # "Pro/deepseek-ai/DeepSeek-R1"
            # #     "deepseek-reasoner",
            # 2: "Pro/deepseek-ai/DeepSeek-V3",
        }
        # "deepseek-chat",
        # "gpt-4o",
        # "claude-3-5-sonnet-20241022",
        # "us.amazon.nova-pro-v1:0",
        # "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        # "us.anthropic.claude-3-7-sonnet-20250219-v1:0",

        # Store strategy reasoning scores for each faction
        self.strategy_scores = {1: 0, 2: 0} 
        # Add new counter to track response times
        self.response_times = {1: 0, 2: 0}  # Track responses per faction

        # Strategy keyword list
        self.strategy_keywords = [
            "协同作战",
            "协同攻击",
            "协同进攻",
            "速战速决",
            "集火射击",
            "集火攻击",
            "集中火力",
            "隐蔽",
        ]
        self.strategy_keywords_en = [
            "Coordinated", "coordinated",
            "Concentrated", "concentrated",
            "Stealth", "stealth"
        ]
        self.enable_thinking = False


    def initialize(self, context):
        self.context = context
        self.logger.info("LLM Control System initialized") 

    def subscribe_events(self):
        pass

    def handle_event(self, event: EventMessage):
        pass

    def update(self, delta_time: float):
        """Update AI control system"""
        if not self.is_enabled():
            return
        for fa, fu in self.futures.items():
            if fu["orient"] is not None:
                f = self.futures[fa]["orient"]
                if f.done():
                    try:
                        think_str = f.result()
                    except Exception as e:
                        self.logger.error(f"error: {e}")
                        self.logger.error(f"future: {f.result()}")
                    self.futures[fa]["orient"] = None
                    self.step_status[fa]["step"] = STEP.DECIDE
                    self.step_status[fa]["think"] = think_str
                    self.step_status[fa]["action"] = None
                    # self.logger.msg(f"future: {f.result()}")

            if fu["decide"] is not None:
                f = self.futures[fa]["decide"]
                if f.done():
                    self.futures[fa]["decide"] = None
                    self.step_status[fa]["step"] = STEP.ORIENT
                    self.step_status[fa]["think"] = None
                    self.step_status[fa]["action"] = f.result()
                    # self.logger.msg(f"future: {f.result()}")
        # Update AI decision cooldowns
        self._update_decision_cooldowns(delta_time)

        # tpye 1
        ## Single decision: Agent control muliple units
        # type 2
        ## Group decision: Each agent control a single unit.
        # type 3
        ## Mixed decision: An agent being as the main controler. Other agents excute actions. 
        match self.agent_type:
            case 1:
                # Single decision
                for i in range(1, 3):
                    if i not in self.ai_decision_cooldowns:
                        if i == 2:
                            self._make_type1_step_no_think(i)
                        else:
                            self._make_type1_step_no_think(i)
                            # self._make_type1_step(i)
                        self.ai_decision_cooldowns[i] = self.decision_interval
            case 2:
                # Group decision
                self._update_type2_agents()
                self._update_ai_decisions_type2(delta_time)
            case 3:
                # Mixed decision   
                self._update_type3_agents()
                self._update_ai_decisions_type3(delta_time)
            case _:
                # agent Other types of agents
                pass

    def _update_decision_cooldowns(self, delta_time: float):
        """Update AI decision cooldowns"""
        match self.agent_type:
            case 1:
                # Single decision
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)
            case 2:
                # Group decision
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)
            case 3:
                # Mixed decision
                need_to_remove = []
            case _:
                # agent Other types of agents     
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)

        # Remove units that have completed cooling
        for entity in need_to_remove:
            del self.ai_decision_cooldowns[entity]

    def _make_type1_step_no_think(self, faction: int):
        if faction not in self.futures:
            self.futures[faction] = {
                "orient": None,
                "decide": None,
            }
        if faction not in self.step_status:
            self.step_status[faction] = {
                "step": STEP.ORIENT,
                "think": None,
                "action": None,
            }
        if (
            self.futures[faction]["orient"] is None
            and self.step_status[faction]["step"] is STEP.ORIENT
        ):

            with open(
                f"{Path(__file__).parent}/prompts/situation_awareness_en.yaml",
                "r",
                encoding="utf-8",
            ) as f:
                sa_template = yaml.safe_load(f)
            # Iterate through all units
            for entity, (stats_comp,) in self.context.with_all(
                BattleStatsComponent
            ).iter_components(BattleStatsComponent):
                if stats_comp.faction == faction:
                    sa_prompt = sa_template["prompt"].format(
                        enemy_status=stats_comp.enemy_status_info,
                        transfer_situation=stats_comp.enemy_transfer_situation,
                        my_status=stats_comp.my_status_info,
                        my_transfer_situation=stats_comp.my_transfer_situation,
                        terrain_environment=stats_comp.terrain_environment,
                        contact_and_fire=stats_comp.contact_and_fire,
                        death_status=stats_comp.death_status,
                    )

            try:
                with open(
                    f"{Path(__file__).parent}/prompts/decision_no_cot_en.yaml",
                    "r",
                    encoding="utf-8",
                ) as f:
                    ot_template = yaml.safe_load(f)

                ot_prompt = (
                    ot_template["prompt"]
                    .replace("{{faction}}", str(faction))
                    .replace("{{situation_info}}", sa_prompt)
                )

                self.futures[faction]["orient"] = self.context.executor.submit(
                    self.chat_function,
                    [
                        {
                            "role": "system",
                            "content": ot_template["system"],
                        },
                        {
                            "role": "user",
                            "content": ot_prompt,
                        },
                    ],
                    log_tag=f"orient_thinking_{faction}",
                    enable_thinking=self.enable_thinking,
                )
            except Exception as e:
                self.logger.error(f"[Faction {faction}]: error: {e}")
        elif self.step_status[faction]["think"] is not None:
            action = self.step_status[faction]["think"]

            # Handle None or empty strings
            if action is None or action.strip() == "":
                self.logger.warning(
                    f"[Faction {faction}]: Empty action received, skipping"
                )
                self.step_status[faction]["think"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return

            # Ensure it's a string before processing
            if not isinstance(action, str):
                self.logger.error(
                    f"[Faction {faction}]: Action is not a string: {type(action)}"
                )
                self.step_status[faction]["think"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return

            # Normalize the format
            action = action.strip()
            json_dict = {}

            try:
                if action.startswith("```json"):
                    # Try to extract JSON content
                    content = action[7:]
                    end_pos = content.find("```")
                    if end_pos != -1:
                        content = content[:end_pos].strip()
                    json_dict = json.loads(content)
                elif action.startswith("{") and action.endswith("}"):
                    # Parse JSON directly
                    json_dict = json.loads(action)
                else:
                    # try to find JSON part
                    start_pos = action.find("{")
                    end_pos = action.rfind("}")
                    if start_pos != -1 and end_pos != -1:
                        json_dict = json.loads(action[start_pos : end_pos + 1])
                    else:
                        self.logger.error(
                            f"[Faction {faction}]: Cannot find valid JSON in action: {action}"
                        )
                        self.step_status[faction]["think"] = None
                        self.step_status[faction]["step"] = STEP.ORIENT
                        return
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"[Faction {faction}]: JSON解析错误: {e}, action: {action}"
                )
                self.step_status[faction]["think"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return
            for k, v in json_dict.items():
                entity_id = int(k)

                # Verify if the unit exists and is alive
                if not self.context.has_component(entity_id, UnitComponent):
                    self.logger.warning(
                        f"[Faction {faction}]: Unit ID:{entity_id} not exist. skip."
                    )
                    continue

                unit = self.context.get_component(entity_id, UnitComponent)
                if not unit.is_alive:
                    self.logger.warning(
                        f"[Faction {faction}]: Unit ID:{entity_id} already dead. skip."
                    )
                    continue

                if v["action"] == "move":
                    unit.decision_state = "move"
                    self.context.event_manager.publish(
                        EventMessage(
                            EventType.UNIT_MOVED,
                            {
                                "entity": entity_id,
                                "target_x": float(v["args"][0]),
                                "target_y": float(v["args"][1]),
                            },
                        )
                    )
                if v["action"] == "attack":
                    # Verify if the unit exists and is alive
                    try:
                        entity_id = int(k)
                        target_id = int(v["args"])
                    except ValueError:
                        self.logger.error(
                            f"[Faction {faction}]: Invalid attack parameters: entity={k}, target={v['args']}. Expected numeric values."
                        )
                        continue

                    # Verify if both the attacker and target exist and are alive
                    if not self.context.has_component(
                        entity_id, UnitComponent
                    ) or not self.context.has_component(target_id, UnitComponent):
                        self.logger.warning(
                            f"[Faction {faction}]: Attacker or target not exist. Skipping attack."
                        )
                        continue

                    attacker = self.context.get_component(entity_id, UnitComponent)
                    attacker.decision_state = "attack"
                    target = self.context.get_component(target_id, UnitComponent)

                    if not attacker.is_alive:
                        self.logger.warning(
                            f"[Faction {faction}]: Attacker ID:{entity_id} is dead, skipping attack"
                        )
                        continue

                    if not target.is_alive:
                        self.logger.warning(
                            f"[Faction {faction}]: Target ID:{target_id} is dead, skipping attack"
                        )
                        continue

                    # Get the map component, for calculating the map boundary
                    map_entity = self.context.with_all(MapComponent).first()
                    map_component = self.context.get_component(map_entity, MapComponent)

                    # Determine the attack range of the attacker
                    attack_range = 10  # Default to the attack range of infantry and cavalry
                    if attacker.unit_type == UnitType.ARCHER:
                        attack_range = 20  # The attack range of archers

                    # Calculate the direction vector from the attacker to the target
                    dx = target.position_x - attacker.position_x
                    dy = target.position_y - attacker.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    # If already in the attack range, no need to move
                    if distance <= attack_range:
                        self.logger.info(
                            f"[Faction {faction}]: Unit ID:{entity_id} is already in the attack range, no need to move"
                        )
                        continue

                    # Calculate the target position to move (subtract the attack range from the target position)
                    # Calculate by normalizing the direction vector and multiplying by (distance - attack range)
                    if distance > 0:  # 避免除以零 Avoid division by zero
                        # Calculate the unit direction vector
                        dx_norm = dx / distance
                        dy_norm = dy / distance

                        # Calculate the distance to move (ensure stopping at the attack range edge)
                        move_distance = distance - attack_range + 5  # 确保进入攻击范围 Ensure entering the attack range

                        # Calculate the final target position
                        target_x = (
                            attacker.position_x + int(dx_norm * move_distance) + 1
                        )
                        target_y = (
                            attacker.position_y + int(dy_norm * move_distance) + 1
                        )

                        # Ensure the target position is within the map range
                        target_x = max(
                            0,
                            min(
                                target_x, map_component.width * map_component.tile_size
                            ),
                        )
                        target_y = max(
                            0,
                            min(
                                target_y, map_component.height * map_component.tile_size
                            ),
                        )

                        # Send a move event
                        self.context.event_manager.publish(
                            EventMessage(
                                EventType.UNIT_MOVED,
                                {
                                    "entity": entity_id,
                                    "target_x": float(target_x),
                                    "target_y": float(target_y),
                                },
                            )
                        )
                        self.logger.info(
                            f"[Faction {faction}]: 单位 ID:{entity_id} 移动到目标 ID:{target_id} 的攻击位置 ({target_x:.1f}, {target_y:.1f})"
                        )
                    else:
                        # An edge case where the target and attacker are in the same position
                        self.logger.warning(
                            f"[Faction {faction}]: Unit ID:{entity_id} is in the same position as target ID:{target_id}, cannot determine attack direction"
                        )

            # Reset the state, prepare for the next OODA loop
            self.step_status[faction]["think"] = None
            self.step_status[faction]["step"] = STEP.ORIENT
        else:
            # Handle waiting state or other unprocessed states
            current_step = self.step_status[faction]["step"]
            orient_future = self.futures[faction]["orient"]
            decide_future = self.futures[faction]["decide"]

            # Record the current state
            if current_step == STEP.ORIENT and orient_future is not None:
                # Waiting for the orientation thinking to complete
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"[Faction {faction}]: Thinking...(ORIENT stage)")
                    self._last_status_log = time.time()
            elif current_step == STEP.DECIDE and decide_future is not None:
                # Waiting for the decision to complete
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"[Faction {faction}]: Deciding...(DECIDE stage)")
                    self._last_status_log = time.time()
            else:
                # Unknown or abnormal state
                self.logger.warning(
                    f"[Faction {faction}]:In Unprocessed state: step={current_step}, "
                    f"orient_future={orient_future is not None}, "
                    f"decide_future={decide_future is not None}, "
                    f"think={self.step_status[faction]['think'] is not None}, "
                    f"action={self.step_status[faction]['action'] is not None}"
                )

                # reset if in abnormal state ## To be decided
                if (
                    current_step == STEP.DECIDE
                    and self.step_status[faction]["think"] is None
                ) or (current_step != STEP.ORIENT and current_step != STEP.DECIDE):
                    self.logger.warning(
                        f"[Faction {faction}]: Abnormal state, reset to ORIENT stage"
                    )
                    self.step_status[faction]["step"] = STEP.ORIENT
                    self.step_status[faction]["think"] = None
                    self.step_status[faction]["action"] = None
                    self.futures[faction]["orient"] = None
                    self.futures[faction]["decide"] = None

    def _make_type1_step(self, faction: int):
        """Make decisions for type1 agents"""
        # Get the list of units for type1 agents
        # Iterate through each agent unit

        ## OODA
        ## 1. Observe
        ## 2. Think
        ## 3. Decide
        ## 4. Act

        if faction not in self.futures:
            self.futures[faction] = {
                "orient": None,
                "decide": None,
            }
        if faction not in self.step_status:
            self.step_status[faction] = {
                "step": STEP.ORIENT,
                "think": None,
                "action": None,
            }

        if (
            self.futures[faction]["orient"] is None
            and self.step_status[faction]["step"] is STEP.ORIENT
        ):
            # observe() 
            with open(
                f"{Path(__file__).parent}/prompts/situation_awareness_en.yaml",
                "r",
                encoding="utf-8",
            ) as f:
                sa_template = yaml.safe_load(f)
            # Iterate through all units
            for entity, (stats_comp,) in self.context.with_all(
                BattleStatsComponent
            ).iter_components(BattleStatsComponent):
                if stats_comp.faction == faction:
                    sa_prompt = sa_template["prompt"].format(
                        enemy_status=stats_comp.enemy_status_info,
                        transfer_situation=stats_comp.enemy_transfer_situation,
                        my_status=stats_comp.my_status_info,
                        my_transfer_situation=stats_comp.my_transfer_situation,
                        terrain_environment=stats_comp.terrain_environment,
                        contact_and_fire=stats_comp.contact_and_fire,
                        death_status=stats_comp.death_status,
                    )

            # orient() Reflect on orientation
            try:
                with open(
                    f"{Path(__file__).parent}/prompts/orient_thinking_en.yaml",
                    "r",
                    encoding="utf-8",
                ) as f:
                    ot_template = yaml.safe_load(f)

                ot_prompt = ot_template["prompt"].format(
                    faction=faction, situation_info=sa_prompt
                )

                self.futures[faction]["orient"] = self.context.executor.submit(
                    self.chat_function,
                    [
                        {
                            "role": "system",
                            "content": ot_template["system"],
                        },
                        {
                            "role": "user",
                            "content": ot_prompt,
                        },
                    ],
                    log_tag=f"orient_thinking_{faction}",
                    enable_thinking=self.enable_thinking,
                )
            except Exception as e:
                self.logger.error(f"[Faction {faction}]: error: {e}")
        elif (
            self.futures[faction]["decide"] is None
            and self.step_status[faction]["step"] is STEP.DECIDE
            and self.step_status[faction]["think"] is not None
        ):
            with open(
                f"{Path(__file__).parent}/prompts/decision_en.yaml",
                "r",
                encoding="utf-8",
            ) as f:
                de_template = yaml.safe_load(f)
            de_prompt = de_template["prompt"].replace(
                # "{faction}", str(faction)
                # ).replace(
                #     "{situation_info}", sa_prompt
                # ).replace(
                "{{thinking_result}}",
                self.step_status[faction]["think"],
            )
            try:
                self.futures[faction]["decide"] = self.context.executor.submit(
                    self.chat_function,
                    [
                        {
                            "role": "system",
                            "content": de_template["system"],
                        },
                        {
                            "role": "user",
                            "content": de_prompt,
                        },
                    ],
                    log_tag=f"decision_{faction}",
                    enable_thinking=self.enable_thinking,
                )
            except Exception as e:
                self.logger.error(f"[Faction {faction}]: error: {e}")
        elif self.step_status[faction]["action"] is not None:
            # act()
            action = self.step_status[faction]["action"]

            # Handle None or empty string
            if action is None or action.strip() == "":
                self.logger.warning(
                    f"[Faction {faction}]: Empty action received, skipping"
                )
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return

            # Ensure it's a string type before processing
            if not isinstance(action, str):
                self.logger.error(
                    f"[Faction {faction}]: Action is not a string: {type(action)}"
                )
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return

            # Standardize format processing
            action = action.strip()
            json_dict = {}

            try:
                if action.startswith("```json"):
                    # Try to extract JSON content
                    content = action[7:]
                    end_pos = content.find("```")
                    if end_pos != -1:
                        content = content[:end_pos].strip()
                    json_dict = json.loads(content)
                elif action.startswith("{") and action.endswith("}"):
                    # Parse JSON directly
                    json_dict = json.loads(action)
                else:
                    # Try to find JSON part
                    start_pos = action.find("{")
                    end_pos = action.rfind("}")
                    if start_pos != -1 and end_pos != -1:
                        json_dict = json.loads(action[start_pos : end_pos + 1])
                    else:
                        self.logger.error(
                            f"[Faction {faction}]: Cannot find valid JSON in action: {action}"
                        )
                        self.step_status[faction]["action"] = None
                        self.step_status[faction]["step"] = STEP.ORIENT
                        return
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"[Faction {faction}]: JSON解析错误: {e}, action: {action}"
                )
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return

            # Also, modify the prompt in decision.yaml to make it clearer that JSON format is required
            # system: |
                #   ...
                #   Output must be a valid JSON object, do not include any other content.
                #   Each key is the unit ID (integer), each value is { "action": <move|attack>, "args": <array|integer> }.
                #   Use standard JSON format: double-quoted strings, no comments, no trailing commas.

            for k, v in json_dict.items():
                try:
                    # Try to convert directly to an integer
                    entity_id = int(k)
                except ValueError:
                    # If failed, try to extract ID from string
                    id_match = re.search(r"ID:(\d+)", k)
                    if id_match:
                        entity_id = int(id_match.group(1))
                        self.logger.info(
                            f"[Faction {faction}]: Extracted ID: {entity_id} from key: {k}"
                        )
                    else:
                        self.logger.error(
                            f"[Faction {faction}]: Cannot extract a valid ID from key: '{k}', skipping this operation"
                        )
                        continue

                # Validate if the unit exists and is alive
                if not self.context.has_component(entity_id, UnitComponent):
                    self.logger.warning(
                        f"[Faction {faction}]: Unit ID:{entity_id} does not exist, skipping operation"
                    )
                    continue

                unit = self.context.get_component(entity_id, UnitComponent)
                if not unit.is_alive:
                    self.logger.warning(
                        f"[Faction {faction}]: Unit ID:{entity_id} is dead, skipping operation"
                    )
                    continue

                if v["action"] == "move":
                    self.context.event_manager.publish(
                        EventMessage(
                            EventType.UNIT_MOVED,
                            {
                                "entity": entity_id,
                                "target_x": float(v["args"][0]),
                                "target_y": float(v["args"][1]),
                            },
                        )
                    )
                if v["action"] == "attack":
                    # Validate if the unit exists and is alive
                    try:
                        target_id = int(v["args"])
                    except ValueError:
                        # If failed, try to extract ID from string
                        id_match = re.search(r"(\d+)", v["args"])
                        if id_match:
                            target_id = int(id_match.group(1))
                            self.logger.info(
                                f"[Faction {faction}]: Extracted ID: {target_id} from key: {v['args']}"
                            )
                        else:
                            self.logger.error(
                                f"[Faction {faction}]: Invalid attack target: {v['args']}. Expected numeric value."
                            )
                            continue

                    # Validate if both the attacker and target exist and are alive
                    if not self.context.has_component(
                        entity_id, UnitComponent
                    ) or not self.context.has_component(target_id, UnitComponent):
                        self.logger.warning(
                            f"[Faction {faction}]: Attacker or target does not exist, skipping attack"
                        )
                        continue

                    attacker = self.context.get_component(entity_id, UnitComponent)
                    target = self.context.get_component(target_id, UnitComponent)

                    if not attacker.is_alive:
                        self.logger.warning(
                            f"[Faction {faction}]: Attacker ID:{entity_id} is dead, skipping attack"
                        )
                        continue

                    if not target.is_alive:
                        self.logger.warning(
                            f"[Faction {faction}]: Target ID:{target_id} is dead, skipping attack"
                        )
                        continue

                    # Get the map component, for calculating the map boundary
                    map_entity = self.context.with_all(MapComponent).first()
                    map_component = self.context.get_component(map_entity, MapComponent)

                    # Determine the attack range of the attacker
                    attack_range = 10  # Default to the attack range of infantry and cavalry
                    if attacker.unit_type == UnitType.ARCHER:
                        attack_range = 20  # The attack range of archers

                    # Calculate the direction vector from the attacker to the target
                    dx = target.position_x - attacker.position_x
                    dy = target.position_y - attacker.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    # If already in the attack range, no need to move
                    if distance <= attack_range:
                        self.logger.info(
                            f"[Faction {faction}]: Unit ID:{entity_id} is already in the attack range, no need to move"
                        )
                        continue

                    # Calculate the target position to move (subtract the attack range from the target position)
                    # Calculate by normalizing the direction vector and multiplying by (distance - attack range)
                    if distance > 0:  # Avoid division by zero
                        # Calculate the unit direction vector
                        dx_norm = dx / distance
                        dy_norm = dy / distance

                        # Calculate the distance to move (ensure stopping at the attack range edge)
                        move_distance = distance - attack_range + 5  # Ensure entering the attack range

                        # Calculate the final target position
                        target_x = (
                            attacker.position_x + int(dx_norm * move_distance) + 1
                        )
                        target_y = (
                            attacker.position_y + int(dy_norm * move_distance) + 1
                        )

                        # Ensure the target position is within the map range
                        target_x = max(
                            0,
                            min(
                                target_x, map_component.width * map_component.tile_size
                            ),
                        )
                        target_y = max(
                            0,
                            min(
                                target_y, map_component.height * map_component.tile_size
                            ),
                        )

                        # Send the move event
                        self.context.event_manager.publish(
                            EventMessage(
                                EventType.UNIT_MOVED,
                                {
                                    "entity": entity_id,
                                    "target_x": float(target_x),
                                    "target_y": float(target_y),
                                },
                            )
                        )
                        self.logger.info(
                            f"[Faction {faction}]: Unit ID:{entity_id} moved to the attack position of target ID:{target_id} ({target_x:.1f}, {target_y:.1f})"
                        )
                    else:
                        self.logger.warning(
                            f"[Faction {faction}]: Unit ID:{entity_id} is at the same position as target ID:{target_id}, cannot determine the attack direction"
                        )

            # Reset the status, prepare for the next OODA loop
            self.step_status[faction]["action"] = None
            self.step_status[faction]["step"] = STEP.ORIENT
        else:
            # Handle the waiting state or other unhandled states
            current_step = self.step_status[faction]["step"]
            orient_future = self.futures[faction]["orient"]
            decide_future = self.futures[faction]["decide"]

            # Record the current state
            if current_step == STEP.ORIENT and orient_future is not None:
                # Waiting for the orientation thinking to complete
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"[Faction {faction}]: Thinking...(ORIENT stage)")
                    self._last_status_log = time.time()
            elif current_step == STEP.DECIDE and decide_future is not None:
                # Waiting for the decision to complete
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"[Faction {faction}]: Deciding...(DECIDE stage)")
                    self._last_status_log = time.time()
            else:
                # Unknown or abnormal state
                self.logger.warning(
                    f"[Faction {faction}]: In unhandled state: step={current_step}, "
                    f"orient_future={orient_future is not None}, "
                    f"decide_future={decide_future is not None}, "
                    f"think={self.step_status[faction]['think'] is not None}, "
                    f"action={self.step_status[faction]['action'] is not None}"
                )

                # If in an abnormal state, try to recover to the initial state ## To be decided
                if (
                    current_step == STEP.DECIDE
                    and self.step_status[faction]["think"] is None
                ) or (current_step != STEP.ORIENT and current_step != STEP.DECIDE):
                    self.logger.warning(
                        f"[Faction {faction}]: Abnormal state, reset to ORIENT stage"
                    )
                    self.step_status[faction]["step"] = STEP.ORIENT
                    self.step_status[faction]["think"] = None
                    self.step_status[faction]["action"] = None
                    self.futures[faction]["orient"] = None
                    self.futures[faction]["decide"] = None

    def _make_ai_decision(self, entity: Entity, unit: UnitComponent):
        """Make a decision for the AI unit"""
        # If the unit is moving or attacking, or the unit is dead, do not make a new decision
        if unit.state in [UnitState.MOVING, UnitState.ATTACKING] or not unit.is_alive:
            return

        # 1. Find the target
        target_entity = self._find_target(entity, unit)

        # If a target is found, update the target record
        if target_entity:
            self.ai_targets[entity] = target_entity
            target_unit = self.context.get_component(target_entity, UnitComponent)

            # 2. Check if the unit is in the attack range
            distance = self._calculate_distance(unit, target_unit)

            if distance <= unit.range:
                # In the attack range, launch an attack
                self._attack_target(entity, target_entity)
                self.logger.debug(
                    f"[Faction {unit.owner_id}]: AI unit {unit.name} attacks target {target_unit.name}"
                )
            else:
                # Not in the attack range, move towards the target
                self._move_towards_target(entity, unit, target_unit)
                self.logger.debug(
                    f"[Faction {unit.owner_id}]: AI unit {unit.name} moves towards target {target_unit.name}"
                )
        else:
            # No target found, random movement
            self._random_movement(entity, unit)
            self.logger.debug(f"[Faction {unit.owner_id}]: AI unit {unit.name} random movement")

    def _find_target(self, entity: Entity, unit: UnitComponent) -> Optional[Entity]:
        """Find the target to attack"""
        # If there is already a target and the target is still valid, continue using the current target
        if entity in self.ai_targets:
            current_target = self.ai_targets[entity]
            if self.context.component_manager.has_component(
                current_target, UnitComponent
            ):
                target_unit_comp = self.context.get_component(
                    current_target, UnitComponent
                )
                if (
                    target_unit_comp
                    and target_unit_comp.is_alive
                    and target_unit_comp.owner_id != unit.owner_id
                ):
                    return current_target
            # If the current target is invalid, clear it
            del self.ai_targets[entity]

        # Find a new target
        potential_targets = []

        # Iterate through all units, find enemy units
        for target_entity, (target_unit,) in self.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            # Check if the target is an enemy unit and is alive
            if target_unit.owner_id != unit.owner_id and target_unit.is_alive:
                # Calculate the distance
                distance = self._calculate_distance(unit, target_unit)
                # Add the target and distance to the potential target list
                potential_targets.append((target_entity, distance))

        # If there are potential targets, select the nearest target
        if potential_targets:
            # Sort by distance
            potential_targets.sort(key=lambda x: x[1])
            # Return the nearest target
            return potential_targets[0][0]

        return None

    def _is_valid_target(self, target_entity: Entity, unit: UnitComponent) -> bool:
        """Check if the target is valid"""
        # Check if the target exists and has a UnitComponent
        if not self.context.component_manager.has_component(
            target_entity, UnitComponent
        ):
            return False

        target_unit = self.context.get_component(target_entity, UnitComponent)

        # Check if the target is an enemy unit and is alive
        return target_unit.owner_id != unit.owner_id and target_unit.is_alive

    def _calculate_distance(self, unit1: UnitComponent, unit2: UnitComponent) -> float:
        """Calculate the distance between two units"""
        # Use Manhattan distance
        # return abs(unit1.position_x - unit2.position_x) + abs(
        #     unit1.position_y - unit2.position_y
        # )
        # Use Euclidean distance
        return math.hypot(unit1.position_x - unit2.position_x, unit1.position_y - unit2.position_y)

    def _attack_target(self, attacker_entity: Entity, target_entity: Entity):
        """Launch an attack"""
        # Publish the attack event
        self.context.event_manager.publish(
            EventMessage(
                EventType.ATTACK,
                {
                    "entity": attacker_entity,
                    "target": target_entity,
                },
            )
        )

    def _move_towards_target(
        self, entity: Entity, unit: UnitComponent, target_unit: UnitComponent
    ):
        """Move towards the target"""
        # Calculate the movement direction
        dx = target_unit.position_x - unit.position_x
        dy = target_unit.position_y - unit.position_y

        # Determine the movement distance (not exceeding the unit's movement range)
        move_distance = min(unit.base_speed, max(abs(dx), abs(dy)))

        # Calculate the target position
        if abs(dx) > abs(dy):
            # Horizontal movement
            target_x = unit.position_x + (move_distance if dx > 0 else -move_distance)
            target_y = unit.position_y
        else:
            # Vertical movement
            target_x = unit.position_x
            target_y = unit.position_y + (move_distance if dy > 0 else -move_distance)

        # Publish the movement event
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_MOVED,
                {
                    "entity": entity,
                    "target_x": target_x,
                    "target_y": target_y,
                },
            )
        )

    def _random_movement(self, entity: Entity, unit: UnitComponent):
        """Random movement"""
        # Randomly select a direction
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        dx, dy = random.choice(directions)

        # Calculate the target position
        target_x = unit.position_x + dx * unit.base_speed
        target_y = unit.position_y + dy * unit.base_speed

        # Ensure the target position is within the map range
        map_component = self._get_map_component()
        if map_component:
            target_x = max(0, min(target_x, map_component.width - 1))
            target_y = max(0, min(target_y, map_component.height - 1))

        # Publish the movement event
        self.context.event_manager.publish(
            EventMessage(
                EventType.UNIT_MOVED,
                {
                    "entity": entity,
                    "target_x": target_x,
                    "target_y": target_y,
                },
            )
        )

    def _get_map_component(self) -> Optional[MapComponent]:
        """Get the map component"""
        for entity, (map_component,) in self.context.with_all(
            MapComponent
        ).iter_components(MapComponent):
            return map_component
        return None

    def _log_chat_to_file(self, log_type, content, log_tag):
        """Log the chat content

        Args:
            log_type: The log type, 'request' or 'response'
            content: The content to log
            log_tag: The log tag, separated by faction
        """
        try:
            # Extract faction_id (if it exists)
            # Build the log message prefix
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if log_tag:
                prefix = f"[Chat Fraction{log_tag} {log_type.upper()}]"
                prefix += f" Time: {timestamp}"
            else:
                prefix = f"[Chat {log_type.upper()}]"
                prefix += f" Time: {timestamp}"

            # Create the log content
            if log_type == "request":
                content_text = ""
                for item in content["messages"]:
                    if item["role"] == "system":
                        content_text += "System: \n"
                        content_text += item["content"]
                        content_text += "\n"
                    if item["role"] == "user":
                        content_text += "User: \n"
                        content_text += item["content"]
                        content_text += "\n"
                    if item["role"] == "assistant":
                        content_text += "Assistant: \n"
                        content_text += item["content"]
                        content_text += "\n"
                log_content = f"{prefix} \n***Fraction{log_tag}***\n Sending Request: \n------\n{content_text}\n------"
            else:  # response
                # Check if it is an enhanced response object
                if (
                    "response_type" in content
                    and content["response_type"] == "LLM_API_RESPONSE"
                ):
                    # Add a prominent separator and marker
                    separator = "=" * 50
                    log_content = (
                        f"{prefix}\n{separator}\n"
                        f"【Fraction{log_tag} LLM Response - {content['timestamp']}】\n{separator}\n"
                        f"{content['content']}\n"
                        f"{separator}\n Response end\n{separator}"
                    )

                    # Keep the original response log
                    original_response = content["original_response"]
                    original_json = json.dumps(
                        original_response, ensure_ascii=False, indent=2
                    )
                    log_content += f"\n\n The Original JSON:\n{original_json}\n"
                else:
                    # The original response processing logic
                    if (
                        "message" in content
                        and "content" in content["message"]
                        and "text_content" in content["message"]["content"]
                    ):
                        response_text = content["message"]["content"]["text_content"]
                        log_content = f"{prefix} \n***Fraction {log_tag}***\n Received Response:\n------\n{response_text}\n------"
                    else:
                        log_content = f"{prefix} Received Response: {json.dumps(content, ensure_ascii=False)}"

            # self.logger.msg(log_content)

            # Write to log file according to log_tag 
            if log_tag:
                log_dir = Path(__file__).parent / "logs"
                log_dir.mkdir(exist_ok=True)

                safe_log_tag = (
                    str(log_tag).replace("/", "_").replace("\\", "_").replace(":", "_")
                )
                if "1" in safe_log_tag:
                    safe_log_tag = "1"
                if "2" in safe_log_tag:
                    safe_log_tag = "2"
                if "0" in safe_log_tag:
                    safe_log_tag = "0"
                log_file_path = (
                    log_dir
                    / f"{safe_log_tag}_{datetime.datetime.now().strftime('%Y-%m-%d')}.log"
                )

                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{log_content}\n\n")

        except Exception as e:
            self.logger.error(f"ERROR When logging LLM Response: {str(e)}")

    def get_faction_models(self):
        """Return models used by each fraction"""
        return self.faction_models

    def get_strategy_scores(self):
        """Return the strategy scores of each fraction"""
        return self.strategy_scores

    def get_enable_thinking(self):
        """return thinking flag for experiment report."""
        return self.enable_thinking

    def update_strategy_score(self, faction, response_text):
        """Update strategy score using rule-based match.

        Args:
            faction: fraction ID
            response_text: response from LLM
        """
        for strategy in self.strategy_keywords:
            if strategy in response_text:
                self.strategy_scores[faction] += 0.5
                self.logger.info(
                    f"[Faction {faction}]: used strategy '{strategy}'，score+0.5. Current score:{self.strategy_scores[faction]}"
                )

    def chat(
        self,
        messages,
        model_id="Qwen/Qwen3-14B",
        stream=False,
        log_tag=None,
        enable_thinking=True,
    ):

        # SERVER_URL = "https://api.deepseek.com/v1/chat/completions"
        # TOKEN = "sk-419ab6c0fc9c4d849e5efbde67149dc5"

        if log_tag is not None and "1" in log_tag:
            # model_id = "Qwen/Qwen3-8B"
            # SERVER_URL = (
            #     "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
            # )
            # TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"

            SERVER_URL = "http://172.16.75.204:11434/api/generate"
            # TOKEN = "sk-iciaxzpoxqwfmubueuobhlocgezdojutrreqhrhuthclkebt"

            model_id = self.faction_models[1]

        if log_tag is not None and "2" in log_tag:

            SERVER_URL = "http://172.16.75.204:11434/api/generate"
            # TOKEN = "sk-iciaxzpoxqwfmubueuobhlocgezdojutrreqhrhuthclkebt"

            # SERVER_URL = (
            #     "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
            # )
            # TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"

            model_id = self.faction_models[2]

        headers = {
            # "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }

        data = {
            "messages": messages,
            "model": model_id,
            "temperature": 0,
            "max_token": 8192,
            "stream": stream,
            # "enable_thinking": enable_thinking,
            "response_format": {"type": "json_object"},
        }

        self._log_chat_to_file("request", data, log_tag)

        if stream:
            # response = requests.post(
            #     f"{SERVER_URL}/api/rotk/chat", json=data, headers=headers, stream=True
            # )
            pass
        else:
            # 发送请求
            if log_tag is not None and "1" in log_tag:
                #  ==========   AWS  ==========
                # response = requests.post(
                #     f"{SERVER_URL}/api/rotk/chat", json=data, headers=headers
                # )
                # llm_response = response.json()
                # response_text = llm_response["message"]["content"]["text_content"]
                #  ==========   SiliconFlow  ==========
                response = requests.post(SERVER_URL, json=data, headers=headers)
                llm_response = response.json()
                response_text = llm_response["choices"][0]["message"]["content"]
                #  ==================================

                if "orient_thinking" in log_tag:
                    self.update_strategy_score(1, response_text)

                # Increment response counter for faction 1
                self.response_times[1] += 1

            if log_tag is not None and "2" in log_tag:  # openai
                #  ==========   SiliconFlow  ==========
                response = requests.post(SERVER_URL, json=data, headers=headers)
                llm_response = response.json()
                response_text = llm_response["choices"][0]["message"]["content"]
                #  ==================================
                # response = requests.post(
                #     f"{SERVER_URL}/api/rotk/chat", json=data, headers=headers
                # )
                # llm_response = response.json()
                # response_text = llm_response["message"]["content"]["text_content"]

                if "orient_thinking" in log_tag:
                    self.update_strategy_score(2, response_text)

                # Increment response counter for faction 2
                self.response_times[2] += 1

            # Add validation for empty responses
            if not response_text or response_text.strip() == "":
                self.logger.warning(
                    f"[Faction {log_tag}]: Received empty response from LLM API"
                )
                return None  # Return None instead of empty string

            self._log_chat_to_file("response", llm_response, log_tag)

            self.logger.msg(f"** [Faction {log_tag}] ** Response :\n {response_text}")
            return response_text


    def chat_ollama(self, messages, model_id="qwen3:8b", stream=False, log_tag=None, enable_thinking=True):

        SERVER_URL = "http://172.16.75.204:11434/api/chat"
        headers = {
            "Content-Type": "application/json",
        }
        if log_tag is not None and "1" in log_tag:
            model_id = "qwen3:32b"  

        if log_tag is not None and "2" in log_tag:
            model_id = "qwen3:8b"

        data = {
            "model": model_id,
            "messages": messages,
            "stream": stream,
        }
        self._log_chat_to_file("request", data, log_tag)
        if stream:
            # Ollama stream return JSON string line by line
            response = requests.post(SERVER_URL, json=data, headers=headers, stream=True)
            response_text = ""
            for line in response.iter_lines():
                if line:
                    line_data = json.loads(line.decode("utf-8"))
                    response_text += line_data.get("message", {}).get("content", "")
        else:
            response = requests.post(SERVER_URL, json=data, headers=headers)
            llm_response = response.json()
            response_text = llm_response["message"]["content"]

            if log_tag is not None and "1" in log_tag:
                self.update_strategy_score(1, response_text)
                self.response_times[1] += 1

            if log_tag is not None and "2" in log_tag:
                self.update_strategy_score(2, response_text)
                self.response_times[2] += 1

        # Add validation for empty responses
        if not response_text or response_text.strip() == "":
            self.logger.warning(
                f"[Ollama {model_id}]: Received empty response from local LLM"
            )
            return None
        self._log_chat_to_file("response", llm_response, log_tag)
        self.logger.msg(f"** [Ollama:{model_id}] ** Response :\n {response_text}")
        return response_text



    def cleanup(self):
        """Clean all the LLM API request. """
        self.logger.info("Clean all the unfinished tasked of LLM")
        for faction, futures in self.futures.items():
            for key, future in futures.items():
                if future is not None and not future.done():
                    future.cancel()
                    self.logger.info(f"Cancel Fraction {faction} {key} Task")

        # 清空futures和状态
        self.futures = {}
        self.step_status = {}

    def get_response_times(self):
        """Return the number of responses received from the LLM API for each faction"""
        return self.response_times

