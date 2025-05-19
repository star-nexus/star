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
        self.ai_decision_cooldowns = {}  # 存储AI决策冷却时间

        self.ai_targets = {}  # 存储AI单位的目标 {ai_entity: target_entity}
        self.decision_interval = 5.0  # AI决策间隔（秒）
        self.agent_type = 1  # 1: 单体决策, 2: 群体决策, 3: 混合决策

        self.futures = {}
        self.step_status = {}

        # 存储每个阵营使用的模型ID
        self.faction_models = {
            # 1: "Qwen/Qwen3-14B",
            # 2: "Qwen/Qwen3-8B",
            # 2: "Qwen/Qwen2.5-14B-Instruct",
            # 1: "us.meta.llama4-scout-17b-instruct-v1:0",
            # # 2: "Qwen/Qwen3-235B-A22B"# "Pro/deepseek-ai/DeepSeek-V3",#
            # 2: "Pro/deepseek-ai/DeepSeek-V3" # 
            2: "Qwen/Qwen3-32B",
            # #     "deepseek-reasoner",
            # 2: "us.amazon.nova-pro-v1:0",
            # 1: "us.meta.llama4-scout-17b-instruct-v1:0",
            1: "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
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

        # 存储每个阵营的策略推理分数
        self.strategy_scores = {1: 0, 2: 0}  # 阵营1的策略分数  # 阵营2的策略分数

        # 策略关键词列表
        self.strategy_keywords = [
            "协同作战", "协同攻击", "协同进攻",
            "速战速决", 
            "集火射击", "集火攻击", "集中火力",
            "隐蔽"]
        # self.strategy_keywords = [
        #     "Coordinated", "coordinated",
        #     "Concentrated", "concentrated",
        #     "Stealth", "stealth"
        # ]
        self.enable_thinking = False

    def initialize(self, context):
        self.context = context
        self.logger.info("LLM控制系统初始化")

    def subscribe_events(self):
        pass

    def handle_event(self, event: EventMessage):
        pass

    def update(self, delta_time: float):
        """更新AI控制系统"""
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
        # 更新AI决策冷却时间
        self._update_decision_cooldowns(delta_time)

        match self.agent_type:
            case 1:
                # 单体决策
                for i in range(1, 3):
                    if i not in self.ai_decision_cooldowns:
                        self._make_type1_step(i)
                        self.ai_decision_cooldowns[i] = self.decision_interval
            case 2:
                # 群体决策
                self._update_type2_agents()
                self._update_ai_decisions_type2(delta_time)
            case 3:
                # 混合决策
                self._update_type3_agents()
                self._update_ai_decisions_type3(delta_time)
            case _:
                # 其他类型的agent
                pass

    def _update_decision_cooldowns(self, delta_time: float):
        """更新AI决策冷却时间"""
        match self.agent_type:
            case 1:
                # 单体决策
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)
            case 2:
                # 群体决策
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)
            case 3:
                # 混合决策
                need_to_remove = []
            case _:
                # 其他类型的agent
                need_to_remove = []
                for entity, cooldown in self.ai_decision_cooldowns.items():
                    self.ai_decision_cooldowns[entity] = cooldown - delta_time
                    if self.ai_decision_cooldowns[entity] <= 0:
                        need_to_remove.append(entity)

        # 移除已完成冷却的单位
        for entity in need_to_remove:
            del self.ai_decision_cooldowns[entity]

    def _make_type1_step(self, faction: int):
        """为type1 agent做出决策"""
        # 获取type1 agent的单位列表
        # 遍历每个agent单位

        ## OODA
        ## 1. 观察
        ## 2. 思考
        ## 3. 决策
        ## 4. 行动

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
            # observe() 收集信息
            with open(
                f"{Path(__file__).parent}/prompts/situation_awareness.yaml",
                "r",
                encoding="utf-8",
            ) as f:
                sa_template = yaml.safe_load(f)
            # 遍历所有单位
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

            # self.logger.msg(f"sa: {sa_prompt}")

            # sa_template = sa_template.replace("${faction}", str(faction))

            # orient() 反思定向
            try:
                with open(
                    f"{Path(__file__).parent}/prompts/orient_thinking.yaml",
                    "r",
                    encoding="utf-8",
                ) as f:
                    ot_template = yaml.safe_load(f)

                ot_prompt = ot_template["prompt"].format(
                    faction=faction, situation_info=sa_prompt
                )
                # self.logger.msg(f"ot: {ot_prompt}")

                self.futures[faction]["orient"] = self.context.executor.submit(
                    self.chat,
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
                self.logger.error(f"error: {e}")
        elif (
            self.futures[faction]["decide"] is None
            and self.step_status[faction]["step"] is STEP.DECIDE
            and self.step_status[faction]["think"] is not None
        ):
            with open(
                f"{Path(__file__).parent}/prompts/decision.yaml",
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
                    self.chat,
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
                self.logger.error(f"error: {e}")
        elif self.step_status[faction]["action"] is not None:
            # act()
            action = self.step_status[faction]["action"]
            
            # 处理None或空字符串
            if action is None or action.strip() == "":
                self.logger.warning(f"Empty action received for faction {faction}, skipping")
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return
            
            # 确保是字符串类型再进行处理
            if not isinstance(action, str):
                self.logger.error(f"Action is not a string: {type(action)}")
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return
            
            # 标准化格式处理
            action = action.strip()
            json_dict = {}
            
            try:
                if action.startswith("```json"):
                    # 尝试提取JSON内容
                    content = action[7:]
                    end_pos = content.find("```")
                    if end_pos != -1:
                        content = content[:end_pos].strip()
                    json_dict = json.loads(content)
                elif action.startswith("{") and action.endswith("}"):
                    # 直接解析JSON
                    json_dict = json.loads(action)
                else:
                    # 尝试寻找JSON部分
                    start_pos = action.find("{")
                    end_pos = action.rfind("}")
                    if start_pos != -1 and end_pos != -1:
                        json_dict = json.loads(action[start_pos:end_pos+1])
                    else:
                        self.logger.error(f"Cannot find valid JSON in action: {action}")
                        self.step_status[faction]["action"] = None
                        self.step_status[faction]["step"] = STEP.ORIENT
                        return
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析错误: {e}, action: {action}")
                self.step_status[faction]["action"] = None
                self.step_status[faction]["step"] = STEP.ORIENT
                return
            
            # 另外，修改decision.yaml中的提示，使其更清晰地指示需要JSON格式
            # system: |
            #   ...
            #   输出必须是一个有效的JSON对象，不要包含其他任何内容。
            #   每个键是单位ID（整数），每个值是{ "action": <move|attack>, "args": <数组|整数> }。
            #   使用标准JSON格式：双引号字符串，没有注释，没有尾随逗号。
            
            for k, v in json_dict.items():
                entity_id = int(k)

                # 验证单位是否存在且存活
                if not self.context.has_component(entity_id, UnitComponent):
                    self.logger.warning(f"单位 ID:{entity_id} 不存在，跳过操作")
                    continue

                unit = self.context.get_component(entity_id, UnitComponent)
                if not unit.is_alive:
                    self.logger.warning(f"单位 ID:{entity_id} 已死亡，跳过操作")
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
                    # 验证单位是否存在且存活
                    try:
                        entity_id = int(k)
                        target_id = int(v["args"])
                    except ValueError:
                        self.logger.error(
                            f"Invalid attack parameters: entity={k}, target={v['args']}. Expected numeric values."
                        )
                        continue

                    # 验证攻击者和目标是否都存在且存活
                    if not self.context.has_component(
                        entity_id, UnitComponent
                    ) or not self.context.has_component(target_id, UnitComponent):
                        self.logger.warning(f"攻击者或目标不存在，跳过攻击")
                        continue

                    attacker = self.context.get_component(entity_id, UnitComponent)
                    target = self.context.get_component(target_id, UnitComponent)

                    if not attacker.is_alive:
                        self.logger.warning(f"攻击者 ID:{entity_id} 已死亡，跳过攻击")
                        continue

                    if not target.is_alive:
                        self.logger.warning(f"目标 ID:{target_id} 已死亡，跳过攻击")
                        continue

                    # 获取地图组件，用于计算地图边界
                    map_entity = self.context.with_all(MapComponent).first()
                    map_component = self.context.get_component(map_entity, MapComponent)

                    # 确定攻击者的攻击范围
                    attack_range = 10  # 默认为步兵和骑兵的攻击范围
                    if attacker.unit_type == UnitType.ARCHER:
                        attack_range = 20  # 弓箭手的攻击范围

                    # 计算从攻击者到目标的方向向量
                    dx = target.position_x - attacker.position_x
                    dy = target.position_y - attacker.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    # 如果已经在攻击范围内，不需要移动
                    if distance <= attack_range:
                        self.logger.info(
                            f"单位 ID:{entity_id} 已在攻击范围内，无需移动"
                        )
                        continue

                    # 计算移动目标位置（目标位置减去攻击范围的距离）
                    # 通过归一化方向向量并乘以(距离-攻击范围)来计算
                    if distance > 0:  # 避免除以零
                        # 计算单位方向向量
                        dx_norm = dx / distance
                        dy_norm = dy / distance

                        # 计算需要移动的距离（确保停在攻击范围边缘）
                        move_distance = distance - attack_range + 5  # 确保进入攻击范围

                        # 计算最终目标位置
                        target_x = (
                            attacker.position_x + int(dx_norm * move_distance) + 1
                        )
                        target_y = (
                            attacker.position_y + int(dy_norm * move_distance) + 1
                        )

                        # 确保目标位置在地图范围内
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

                        # 发送移动事件
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
                            f"单位 ID:{entity_id} 移动到目标 ID:{target_id} 的攻击位置 ({target_x:.1f}, {target_y:.1f})"
                        )
                    else:
                        # 目标和攻击者在同一位置，这是一种边缘情况
                        self.logger.warning(
                            f"单位 ID:{entity_id} 与目标 ID:{target_id} 位置相同，无法确定攻击方向"
                        )

            # 重置状态，准备下一轮OODA循环
            self.step_status[faction]["action"] = None
            self.step_status[faction]["step"] = STEP.ORIENT
        else:
            # 处理等待状态或其他未处理的状态
            current_step = self.step_status[faction]["step"]
            orient_future = self.futures[faction]["orient"]
            decide_future = self.futures[faction]["decide"]

            # 记录当前状态
            if current_step == STEP.ORIENT and orient_future is not None:
                # 正在等待定向思考完成
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"阵营{faction}正在思考中...(ORIENT阶段)")
                    self._last_status_log = time.time()
            elif current_step == STEP.DECIDE and decide_future is not None:
                # 正在等待决策完成
                if (
                    not hasattr(self, "_last_status_log")
                    or time.time() - self._last_status_log > 5
                ):
                    self.logger.debug(f"阵营{faction}正在决策中...(DECIDE阶段)")
                    self._last_status_log = time.time()
            else:
                # 未知或异常状态
                self.logger.warning(
                    f"阵营{faction}处于未处理状态: step={current_step}, "
                    f"orient_future={orient_future is not None}, "
                    f"decide_future={decide_future is not None}, "
                    f"think={self.step_status[faction]['think'] is not None}, "
                    f"action={self.step_status[faction]['action'] is not None}"
                )

                # 如果处于异常状态，尝试恢复到初始状态 ## To be decided
                if (
                    current_step == STEP.DECIDE
                    and self.step_status[faction]["think"] is None
                ) or (current_step != STEP.ORIENT and current_step != STEP.DECIDE):
                    self.logger.warning(f"阵营{faction}状态异常，重置为ORIENT阶段")
                    self.step_status[faction]["step"] = STEP.ORIENT
                    self.step_status[faction]["think"] = None
                    self.step_status[faction]["action"] = None
                    self.futures[faction]["orient"] = None
                    self.futures[faction]["decide"] = None

    def _make_ai_decision(self, entity: Entity, unit: UnitComponent):
        """为AI单位做出决策"""
        # 如果单位正在移动或攻击，或者单位已死亡，不做新的决策
        if unit.state in [UnitState.MOVING, UnitState.ATTACKING] or not unit.is_alive:
            return

        # 1. 寻找目标
        target_entity = self._find_target(entity, unit)

        # 如果找到目标，更新目标记录
        if target_entity:
            self.ai_targets[entity] = target_entity
            target_unit = self.context.get_component(target_entity, UnitComponent)

            # 2. 检查是否在攻击范围内
            distance = self._calculate_distance(unit, target_unit)

            if distance <= unit.range:
                # 在攻击范围内，发起攻击
                self._attack_target(entity, target_entity)
                self.logger.debug(f"AI单位 {unit.name} 攻击目标 {target_unit.name}")
            else:
                # 不在攻击范围内，移动接近目标
                self._move_towards_target(entity, unit, target_unit)
                self.logger.debug(f"AI单位 {unit.name} 向目标 {target_unit.name} 移动")
        else:
            # 没有找到目标，随机移动
            self._random_movement(entity, unit)
            self.logger.debug(f"AI单位 {unit.name} 随机移动")

    def _find_target(self, entity: Entity, unit: UnitComponent) -> Optional[Entity]:
        """寻找攻击目标"""
        # 如果已有目标且目标仍然有效，继续使用当前目标
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
            # 如果当前目标无效，则清除
            del self.ai_targets[entity]

        # 寻找新目标
        potential_targets = []

        # 遍历所有单位，寻找敌方单位
        for target_entity, (target_unit,) in self.context.with_all(
            UnitComponent
        ).iter_components(UnitComponent):
            # 检查是否是敌方单位且存活
            if target_unit.owner_id != unit.owner_id and target_unit.is_alive:
                # 计算距离
                distance = self._calculate_distance(unit, target_unit)
                # 将目标和距离添加到潜在目标列表
                potential_targets.append((target_entity, distance))

        # 如果有潜在目标，选择最近的目标
        if potential_targets:
            # 按距离排序
            potential_targets.sort(key=lambda x: x[1])
            # 返回最近的目标
            return potential_targets[0][0]

        return None

    def _is_valid_target(self, target_entity: Entity, unit: UnitComponent) -> bool:
        """检查目标是否有效"""
        # 检查目标是否存在且有UnitComponent
        if not self.context.component_manager.has_component(
            target_entity, UnitComponent
        ):
            return False

        target_unit = self.context.get_component(target_entity, UnitComponent)

        # 检查目标是否是敌方单位且存活
        return target_unit.owner_id != unit.owner_id and target_unit.is_alive

    def _calculate_distance(self, unit1: UnitComponent, unit2: UnitComponent) -> float:
        """计算两个单位之间的曼哈顿距离"""
        return abs(unit1.position_x - unit2.position_x) + abs(
            unit1.position_y - unit2.position_y
        )

    def _attack_target(self, attacker_entity: Entity, target_entity: Entity):
        """发起攻击"""
        # 发布攻击事件
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
        """向目标移动"""
        # 计算移动方向
        dx = target_unit.position_x - unit.position_x
        dy = target_unit.position_y - unit.position_y

        # 确定移动距离（不超过单位的移动范围）
        move_distance = min(unit.base_speed, max(abs(dx), abs(dy)))

        # 计算移动目标位置
        if abs(dx) > abs(dy):
            # 水平方向移动
            target_x = unit.position_x + (move_distance if dx > 0 else -move_distance)
            target_y = unit.position_y
        else:
            # 垂直方向移动
            target_x = unit.position_x
            target_y = unit.position_y + (move_distance if dy > 0 else -move_distance)

        # 发布移动事件
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
        """随机移动"""
        # 随机选择一个方向
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        dx, dy = random.choice(directions)

        # 计算移动目标位置
        target_x = unit.position_x + dx * unit.base_speed
        target_y = unit.position_y + dy * unit.base_speed

        # 确保目标位置在地图范围内
        map_component = self._get_map_component()
        if map_component:
            target_x = max(0, min(target_x, map_component.width - 1))
            target_y = max(0, min(target_y, map_component.height - 1))

        # 发布移动事件
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
        """获取地图组件"""
        for entity, (map_component,) in self.context.with_all(
            MapComponent
        ).iter_components(MapComponent):
            return map_component
        return None

    def _log_chat_to_file(self, log_type, content, log_tag):
        """记录聊天内容

        Args:
            log_type: 日志类型，'request'或'response'
            content: 要记录的内容
            log_tag: 日志标签, 按阵营区分
        """
        try:
            # 提取faction_id（如果存在）
            # 构建日志消息前缀
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if log_tag:
                prefix = f"[Chat 阵营{log_tag} {log_type.upper()}]"
                prefix += f" Time: {timestamp}"
            else:
                prefix = f"[Chat {log_type.upper()}]"
                prefix += f" Time: {timestamp}"

            # 创建日志内容
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
                log_content = f"{prefix} \n***阵营{log_tag}***\n 发送请求: \n------\n{content_text}\n------"
            else:  # response
                # 检查是否是增强的响应对象
                if (
                    "response_type" in content
                    and content["response_type"] == "LLM_API_RESPONSE"
                ):
                    # 添加醒目的分隔线和标记
                    separator = "=" * 50
                    log_content = (
                        f"{prefix}\n{separator}\n"
                        f"【阵营{log_tag} LLM响应 - {content['timestamp']}】\n{separator}\n"
                        f"{content['content']}\n"
                        f"{separator}\n响应结束\n{separator}"
                    )

                    # 保留原始响应的日志记录
                    original_response = content["original_response"]
                    original_json = json.dumps(
                        original_response, ensure_ascii=False, indent=2
                    )
                    log_content += f"\n\n原始响应JSON:\n{original_json}\n"
                else:
                    # 原有的响应处理逻辑
                    if (
                        "message" in content
                        and "content" in content["message"]
                        and "text_content" in content["message"]["content"]
                    ):
                        response_text = content["message"]["content"]["text_content"]
                        log_content = f"{prefix} \n***阵营{log_tag}***\n 收到响应:\n------\n{response_text}\n------"
                    else:
                        log_content = f"{prefix} 收到响应: {json.dumps(content, ensure_ascii=False)}"

            # 使用主日志记录器记录
            # self.logger.msg(log_content)

            # 根据log_tag将日志写入不同的文件
            if log_tag:
                # 确保日志目录存在
                log_dir = Path(__file__).parent / "logs"
                log_dir.mkdir(exist_ok=True)

                # 根据log_tag创建对应的日志文件
                # 处理log_tag中可能包含的特殊字符，确保文件名有效
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

                # 追加写入日志文件
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{log_content}\n\n")

        except Exception as e:
            self.logger.error(f"记录聊天内容时出错: {str(e)}")

    def get_faction_models(self):
        """返回每个阵营使用的模型信息"""
        return self.faction_models

    def get_strategy_scores(self):
        """返回每个阵营的策略推理分数"""
        return self.strategy_scores

    def get_enable_thinking(self):
        """返回是否开启思考"""
        return self.enable_thinking

    def update_strategy_score(self, faction, response_text):
        """根据响应文本中是否包含策略关键词更新策略分数

        Args:
            faction: 阵营ID
            response_text: 模型响应文本
        """
        for strategy in self.strategy_keywords:
            if strategy in response_text:
                self.strategy_scores[faction] += 0.5
                self.logger.info(
                    f"阵营{faction}使用了策略'{strategy}'，策略推理分+0.5，当前得分:{self.strategy_scores[faction]}"
                )

    def chat(
        self,
        messages,
        model_id="us.amazon.nova-pro-v1:0",
        stream=False,
        log_tag=None,
        enable_thinking=True,
    ):
        # SERVER_URL = "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
        # TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"
        # SERVER_URL = "https://api.deepseek.com/v1/chat/completions"
        # TOKEN = "sk-419ab6c0fc9c4d849e5efbde67149dc5"

        if log_tag is not None and "1" in log_tag:
            # model_id = "Qwen/Qwen3-8B"
            # SERVER_URL = (
            #     "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
            # )
            # TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"

            SERVER_URL = "https://api.siliconflow.cn/v1/chat/completions"
            TOKEN = "sk-iciaxzpoxqwfmubueuobhlocgezdojutrreqhrhuthclkebt"

            model_id = self.faction_models[1]

        if log_tag is not None and "2" in log_tag:
            # model_id = "Pro/Qwen/Qwen2-1.5B-Instruct"
            # model_id = "Qwen/Qwen3-14B"

            SERVER_URL = "https://api.siliconflow.cn/v1/chat/completions"
            TOKEN = "sk-iciaxzpoxqwfmubueuobhlocgezdojutrreqhrhuthclkebt"

            # SERVER_URL = (
            #     "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
            # )
            # TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"

            model_id = self.faction_models[2]

        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }

        # self.logger.msg(messages)
        self.logger.msg(f"** enable_thinking: {enable_thinking} **")
        data = {
            "messages": messages,
            "model": model_id,
            "temperature": 0,
            "max_token": 8192,
            "stream": stream,
            # "enable_thinking": enable_thinking,
            "response_format": {"type": "json_object"},
        }

        # 记录请求内容到日志
        self._log_chat_to_file("request", data, log_tag)

        if stream:
            # 暂时先不支持
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
                response = requests.post(
                    SERVER_URL, json=data, headers=headers
                )
                llm_response = response.json()
                response_text = llm_response["choices"][0]["message"]["content"]
                #  ==================================

                # 添加此段代码以更新策略分数
                if "orient_thinking" in log_tag:
                    self.update_strategy_score(1, response_text)

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

                # 添加此段代码以更新策略分数
                if "orient_thinking" in log_tag:
                    self.update_strategy_score(2, response_text)

            # Add validation for empty responses
            if not response_text or response_text.strip() == "":
                self.logger.warning(f"Received empty response from LLM API for {log_tag}")
                return None  # Return None instead of empty string

            # 记录响应内容到日志
            self._log_chat_to_file("response", llm_response, log_tag)

            self.logger.msg(f"** {log_tag} ** Response :\n {response_text}")
            return response_text

    def cleanup(self):
        """清理所有正在进行的API请求"""
        self.logger.info("清理LLM控制系统的所有未完成任务")
        for faction, futures in self.futures.items():
            for key, future in futures.items():
                if future is not None and not future.done():
                    future.cancel()
                    self.logger.info(f"取消阵营{faction}的{key}任务")

        # 清空futures和状态
        self.futures = {}
        self.step_status = {}


# tpye 1
## 单体决策 agent控制多个单位, 独立作战

# type 2
## 群体决策 agent控制一个单位, 合作作战

# type 3
## 混合决策 一个agent作为主控，多个agent作为执行单位, 混合作战

## action type
### move
### attack
### wait


# SA Example
"""
  # 敌方情况
    观测范围内敌方兵力部署与调动
    兵力状态:{{entity_id: 1, health: 100/100, position: (1, 1)}, {id: 2, status: 1, position: (1, 2)}}
    调动情况:{{entity_id: 1, status: moving, : 1}, {entity_id: 2, status: Moving, status: 1}}
  # 我方情况
    我方兵力状态: {{entity_id: 1, health: 100/100, position: (1, 1)}, {id: 2, status: 1, position: (1, 2)}}
    我方作战任务执行进度: {{entity_id: 1, status: moving, : 1}, {entity_id: 2, status: Moving, status: 1}}
  # 战场环境
    地理环境: {{entity_id: 1, status: moving, : 1}, {entity_id: 2, status: Moving, status: 1}}
  # 作战进程
    交战双方的接触与交火情况: {"步兵(ID:107) 移动到 (184.0, 101.0)"}
    交战双方的伤亡情况: {}
"""
