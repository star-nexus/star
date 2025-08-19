"""
结算报告相关组件
Settlement Report Components
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from framework import SingletonComponent
from ..prefabs.config import Faction


@dataclass
class SettlementReport(SingletonComponent):
    """结算报告主组件"""
    
    # 基本信息
    experiment_id: str = ""  # 实验ID（时间戳）
    timestamp: str = ""  # 生成时间
    map_type: str = ""  # 地图类型
    game_mode: str = ""  # 游戏模式 (turn_based/real_time)
    
    # 游戏结果
    is_tie: bool = False  # 是否平局
    winner_faction: Optional[Faction] = None  # 胜利阵营
    is_half_win: bool = False  # 是否为半歼胜利（超时后存活单位数量较多）
    game_duration_seconds: float = 0.0  # 游戏持续时间（秒）
    game_duration_formatted: str = ""  # 格式化的游戏时长
    
    # 游戏进度（回合制用）
    total_turns: int = 0  # 总回合数（回合制模式）
    
    # 单位信息
    units_info: Dict[str, Any] = field(default_factory=dict)  # 单位详细信息
    
    # 模型信息（已实现）
    model_info: Dict[str, str] = field(default_factory=dict)  # 各阵营使用的模型信息
    
    # Agent端点信息（已实现）
    agent_endpoints: Dict[str, str] = field(default_factory=dict)  # 各阵营Agent的服务端点
    
    # 策略评分（占位，待实现）
    strategy_scores: Dict[str, float] = field(default_factory=dict)  # 各阵营的策略推理分数
    
    # 思考模式（占位，待实现）
    enable_thinking: Optional[bool] = None  # 是否开启思考
    
    # 响应时间（占位，待实现）
    response_times: Dict[str, int] = field(default_factory=dict)  # 各阵营的响应次数
    
    # 战斗统计
    battle_statistics: Dict[str, Any] = field(default_factory=dict)  # 战斗相关统计
    
    # 地图统计
    map_statistics: Dict[str, Any] = field(default_factory=dict)  # 地图相关统计
    
    # 性能统计
    performance_statistics: Dict[str, Any] = field(default_factory=dict)  # 性能相关统计


@dataclass
class BattleStatistics(SingletonComponent):
    """战斗统计组件"""
    
    # 总战斗次数
    total_battles: int = 0
    
    # 各阵营战斗统计
    faction_battle_stats: Dict[Faction, Dict[str, Any]] = field(default_factory=dict)
    
    # 战斗历史记录
    battle_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 伤亡统计
    casualties: Dict[Faction, Dict[str, int]] = field(default_factory=dict)
    
    # 胜利类型统计
    victory_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class MapStatistics(SingletonComponent):
    """地图统计组件"""
    
    # 地图基本信息
    map_width: int = 0
    map_height: int = 0
    total_tiles: int = 0
    
    # 地形分布
    terrain_distribution: Dict[str, int] = field(default_factory=dict)
    
    # 领土控制统计
    territory_control: Dict[Faction, Dict[str, Any]] = field(default_factory=dict)
    
    # 地图对称性
    symmetry_type: str = ""
    
    # 特殊地形统计
    special_features: Dict[str, int] = field(default_factory=dict)


@dataclass
class PerformanceStatistics(SingletonComponent):
    """性能统计组件"""
    
    # 帧率统计
    fps_statistics: Dict[str, float] = field(default_factory=dict)
    
    # 内存使用
    memory_usage: Dict[str, Any] = field(default_factory=dict)
    
    # 渲染性能
    rendering_performance: Dict[str, Any] = field(default_factory=dict)
    
    # 系统性能
    system_performance: Dict[str, Any] = field(default_factory=dict)
