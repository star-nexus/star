from collections import namedtuple
import enum
from turtle import mode
from typing import Optional
import datetime

from framework.ecs import System
from framework.engine.events import EventMessage, EventType
from framework.ecs.entity import Entity
from framework.utils.logging import get_logger, configure
from game.components import UnitComponent, UnitState
from game.components import MapComponent
from game.components import BattleStatsComponent
from pathlib import Path
import random
import requests
import yaml
import json


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
            log_file=f"{Path(__file__).parent}/logs/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
        )
        self.logger = get_logger(__name__)
        self.ai_decision_cooldowns = {}  # 存储AI决策冷却时间

        self.ai_targets = {}  # 存储AI单位的目标 {ai_entity: target_entity}
        self.decision_interval = 5.0  # AI决策间隔（秒）
        self.agent_type = 1  # 1: 单体决策, 2: 群体决策, 3: 混合决策

        self.futures = {}
        self.step_status = {}

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
                    self.futures[fa]["orient"] = None
                    self.step_status[fa]["step"] = STEP.DECIDE
                    self.step_status[fa]["think"] = f.result()
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
                )
            except Exception as e:
                self.logger.error(f"error: {e}")
        elif self.step_status[faction]["action"] is not None:
            # act()
            # self.logger.msg(f"action: {self.step_status[faction]['action']}")
            action = self.step_status[faction]["action"]
            # 对action 进行str 2 dict 解析
            if action.startswith("```json"):
                action = action[7:-3]
                action = json.loads(action)
            elif action.startswith("{"):
                action = json.loads(action)
            else:
                self.logger.error(f"error fmt action: {action}")
            self.logger.msg(f"action: {action}")
            for k, v in action.items():
                if v["action"] == "move":
                    self.context.event_manager.publish(
                        EventMessage(
                            EventType.UNIT_MOVED,
                            {
                                "entity": int(k),
                                "target_x": float(v["args"][0]),
                                "target_y": float(v["args"][1]),
                            },
                        )
                    )
                if v["action"] == "attack":
                    self.context.event_manager.publish(
                        EventMessage(
                            EventType.ATTACK,
                            {
                                "entity": int(k),
                                "target": int(v["args"]),
                            },
                        )
                    )

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
                # 对于响应，记录文本内容
                if (
                    "message" in content
                    and "content" in content["message"]
                    and "text_content" in content["message"]["content"]
                ):
                    response_text = content["message"]["content"]["text_content"]
                    log_content = f"{prefix} \n***阵营{log_tag}***\n 收到响应:\n------\n{response_text}\n------"
                else:
                    log_content = (
                        f"{prefix} 收到响应: {json.dumps(content, ensure_ascii=True)}"
                    )

            # 使用主日志记录器记录
            self.logger.msg(log_content)

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

    def chat(
        self,
        messages,
        # model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        model_id="us.amazon.nova-pro-v1:0",
        stream=False,
        log_tag=None,
    ):
        SERVER_URL = "http://ec2-100-20-214-248.us-west-2.compute.amazonaws.com:8000"
        TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeCJ9.Gb_y2viQzURkq9cTmP9bdE6I_c1RZZcKLrnZgluLZP0"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        }
        if log_tag is not None and "1" in log_tag:
            model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

        if log_tag is not None and "2" in log_tag:
            model_id = "us.amazon.nova-pro-v1:0"
        # self.logger.msg(messages)
        data = {
            "messages": messages,
            "model_id": model_id,
            "temperature": 0,
            "max_token": 8192,
            "stream": stream,
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
            response = requests.post(
                f"{SERVER_URL}/api/rotk/chat", json=data, headers=headers
            )
            # self.logger.msg(f"res : {response.json()}")
            response_text = response.json()["message"]["content"]["text_content"]

            # 记录响应内容到日志
            self._log_chat_to_file("response", response.json(), log_tag)

            return response_text


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
