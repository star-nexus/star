from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from framework.ecs.component import Component
from framework.ecs.entity import Entity


@dataclass
class UnitEffectComponent(Component):
    """单位效果组件，存储单位受到的各种效果

    用于跟踪单位当前受到的各种效果，包括地形效果、技能效果等
    """

    # 当前激活的效果ID列表
    active_effects: List[str] = field(default_factory=list)

    # 效果数据，用于存储各种效果的具体数值
    effect_data: Dict[str, Any] = field(default_factory=dict)

    # 效果来源，记录效果的来源实体（如地形实体、技能施放者等）
    effect_sources: Dict[str, Entity] = field(default_factory=dict)

    # 效果持续时间（回合数，-1表示永久）
    effect_durations: Dict[str, int] = field(default_factory=dict)

    # 效果描述，用于UI显示
    effect_descriptions: Dict[str, str] = field(default_factory=dict)

    def add_effect(
        self,
        effect_id: str,
        source: Entity,
        data: Any,
        duration: int = -1,
        description: str = "",
    ):
        """添加一个效果

        Args:
            effect_id: 效果ID
            source: 效果来源实体
            data: 效果数据
            duration: 效果持续时间（回合数，-1表示永久）
            description: 效果描述
        """
        if effect_id not in self.active_effects:
            self.active_effects.append(effect_id)

        self.effect_data[effect_id] = data
        self.effect_sources[effect_id] = source
        self.effect_durations[effect_id] = duration
        self.effect_descriptions[effect_id] = description

    def remove_effect(self, effect_id: str):
        """移除一个效果

        Args:
            effect_id: 效果ID
        """
        if effect_id in self.active_effects:
            self.active_effects.remove(effect_id)
            self.effect_data.pop(effect_id, None)
            self.effect_sources.pop(effect_id, None)
            self.effect_durations.pop(effect_id, None)
            self.effect_descriptions.pop(effect_id, None)

    def has_effect(self, effect_id: str) -> bool:
        """检查是否有指定效果

        Args:
            effect_id: 效果ID

        Returns:
            是否有指定效果
        """
        return effect_id in self.active_effects

    def get_effect_data(self, effect_id: str) -> Any:
        """获取效果数据

        Args:
            effect_id: 效果ID

        Returns:
            效果数据
        """
        return self.effect_data.get(effect_id)

    def update_durations(self):
        """更新效果持续时间，通常在回合结束时调用"""
        effects_to_remove = []

        for effect_id in self.active_effects:
            duration = self.effect_durations.get(effect_id, -1)
            if duration > 0:
                self.effect_durations[effect_id] = duration - 1
                if self.effect_durations[effect_id] <= 0:
                    effects_to_remove.append(effect_id)

        for effect_id in effects_to_remove:
            self.remove_effect(effect_id)
