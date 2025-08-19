"""
结算报告生成器系统
Settlement Report Generator System
"""

import os
import json
import csv
import datetime
from typing import Dict, Any, Optional, List
from framework import System, World
from ..components.settlement_report import (
    SettlementReport, 
    BattleStatistics, 
    MapStatistics, 
    PerformanceStatistics
)
from ..components import (
    GameState, 
    GameStats, 
    GameTime, 
    MapData, 
    Unit, 
    UnitCount, 
    Terrain,
    TerritoryControl
)
from ..prefabs.config import Faction, TerrainType, GameConfig
from ..components.agent_info import AgentInfo, AgentInfoRegistry


class SettlementReportSystem(System):
    """结算报告生成器系统"""
    
    def __init__(self):
        super().__init__(priority=200)  # 高优先级，在游戏结束后执行
        self.report_generated = False
        
    def initialize(self, world: World) -> None:
        self.world = world
        
    def subscribe_events(self):
        """订阅事件"""
        pass
        
    def update(self, delta_time: float) -> None:
        """更新系统"""
        # 检查游戏是否结束，如果结束且未生成报告，则生成报告
        if not self.report_generated:
            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.game_over:
                self._generate_settlement_report()
                self.report_generated = True
    
    def _generate_settlement_report(self) -> None:
        """生成结算报告"""
        print("[SettlementReport] 🎯 开始生成结算报告...")
        
        try:
            # 收集所有统计数据
            report_data = self._collect_comprehensive_statistics()
            
            # 创建结算报告组件
            settlement_report = SettlementReport(**report_data)
            self.world.add_singleton_component(settlement_report)
            
            # 保存报告到文件
            self._save_report_to_files(report_data)
            
            # 输出到控制台
            self._print_report_summary(report_data)
            
            print("[SettlementReport] ✅ 结算报告生成完成!")
            
        except Exception as e:
            print(f"[SettlementReport] ❌ 生成结算报告时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _collect_comprehensive_statistics(self) -> Dict[str, Any]:
        """收集综合统计数据"""
        # 获取当前时间作为实验ID
        timestamp = datetime.datetime.now()
        experiment_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # 收集基础游戏数据
        game_data = self._collect_game_data()
        
        # 收集单位信息
        units_info = self._collect_units_info()
        
        # 收集战斗统计
        battle_stats = self._collect_battle_statistics()
        
        # 收集地图统计
        map_stats = self._collect_map_statistics()
        
        # 收集性能统计
        performance_stats = self._collect_performance_statistics()
        
        # 收集占位数据（待实现功能）
        placeholder_data = self._collect_placeholder_data()
        
        return {
            "experiment_id": experiment_id,
            "timestamp": timestamp.isoformat(),
            "map_type": self._get_map_type(),
            **game_data,
            "units_info": units_info,
            "battle_statistics": battle_stats,
            "map_statistics": map_stats,
            "performance_statistics": performance_stats,
            **placeholder_data
        }
    
    def _collect_game_data(self) -> Dict[str, Any]:
        """收集游戏基础数据"""
        game_state = self.world.get_singleton_component(GameState)
        game_time = self.world.get_singleton_component(GameTime)
        
        # 计算游戏时长
        game_duration = 0.0
        if game_time:
            game_duration = game_time.get_game_elapsed_seconds()
        
        # 判断胜利类型
        is_tie = False
        winner_faction = None
        is_half_win = False
        
        if game_state:
            winner_faction = game_state.winner
            if winner_faction:
                # 检查是否为半歼胜利（存活单位数量较多）
                is_half_win = self._check_half_win_condition(winner_faction)
            else:
                is_tie = True
        
        # 检测游戏模式
        game_mode = self._detect_game_mode()
        
        # 收集游戏进度数据
        game_progress = self._collect_game_progress(game_state, game_mode)
        
        return {
            "is_tie": is_tie,
            "winner_faction": winner_faction,
            "is_half_win": is_half_win,
            "game_duration_seconds": game_duration,
            "game_duration_formatted": f"{game_duration:.2f}秒",
            "game_mode": game_mode,
            **game_progress
        }
    
    def _detect_game_mode(self) -> str:
        """检测游戏模式"""
        # 检查是否有回合系统
        turn_system_exists = False
        realtime_system_exists = False
        
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                turn_system_exists = True
            elif system.__class__.__name__ == "RealtimeSystem":
                realtime_system_exists = True
        
        if turn_system_exists and not realtime_system_exists:
            return "turn_based"
        elif realtime_system_exists:
            return "real_time"
        else:
            # 默认检测：检查GameState组件
            game_state = self.world.get_singleton_component(GameState)
            if game_state and hasattr(game_state, 'game_mode'):
                return game_state.game_mode.value
            else:
                return "unknown"
    
    def _collect_game_progress(self, game_state, game_mode: str) -> Dict[str, Any]:
        """收集游戏进度数据"""
        if game_mode == "turn_based":
            # 回合制模式：收集回合数
            total_turns = game_state.turn_number if game_state else 0
            return {
                "total_turns": total_turns
            }
        else:
            # 即时制模式：没有回合概念，返回0
            return {
                "total_turns": 0
            }
    
    def _collect_units_info(self) -> Dict[str, Any]:
        """收集单位信息"""
        units_info = {}
        
        # 🆕 获取初始单位数记录
        game_stats = self.world.get_singleton_component(GameStats)
        initial_counts = game_stats.initial_unit_counts if game_stats else {}
        
        # 🔍 添加调试信息
        print(f"[SettlementReport] 📊 调试信息:")
        print(f"  GameStats组件存在: {game_stats is not None}")
        if game_stats:
            print(f"  初始单位数记录: {initial_counts}")
        else:
            print("  ❌ GameStats组件不存在!")
        
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_units = []
            surviving_units = 0
            total_health = 0
            
            # 🆕 使用记录的初始单位数，而不是当前存活的单位数
            total_units = initial_counts.get(faction, 0)
            
            # 只统计当前存活的单位
            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)
                
                if unit.faction == faction:
                    current_count = unit_count.current_count if unit_count else 0
                    
                    if current_count > 0:
                        surviving_units += 1
                        total_health += current_count
                    
                    # 记录单位详细信息（包括死亡单位，如果仍在世界中）
                    unit_info = {
                        "unit_id": entity,
                        "unit_type": unit.unit_type.value,
                        "position": self._get_unit_position(entity),
                        "current_count": current_count,
                        "max_count": unit_count.max_count if unit_count else 100,
                        "health_percentage": current_count / (unit_count.max_count if unit_count else 100) if unit_count else 0
                    }
                    faction_units.append(unit_info)
            
            # 🔍 添加更多调试信息
            print(f"  {faction.value}阵营:")
            print(f"    初始单位数: {total_units}")
            print(f"    存活单位数: {surviving_units}")
            print(f"    单位详情数量: {len(faction_units)}")
            
            if total_units > 0:  # 🆕 只要有初始单位就记录统计信息
                destroyed_units = total_units - surviving_units  # 🆕 正确计算损失单位数
                units_info[faction.value] = {
                    "total_units": total_units,  # 🆕 使用初始单位数
                    "current_units": surviving_units,  # 🆕 明确标识当前存活单位数
                    "surviving_units": surviving_units,
                    "destroyed_units": destroyed_units,  # 🆕 正确的损失单位数
                    "total_health": total_health,
                    "units": faction_units
                }
                print(f"    ✅ 添加到结算报告")
            else:
                print(f"    ❌ 初始单位数为0，跳过")
        
        return units_info
    
    def _collect_battle_statistics(self) -> Dict[str, Any]:
        """收集战斗统计"""
        game_stats = self.world.get_singleton_component(GameStats)
        
        battle_stats = {
            "total_battles": 0,
            "faction_battle_stats": {},
            "battle_history": [],
            "casualties": {},
            "victory_types": {}
        }
        
        if game_stats:
            # 从GameStats获取战斗历史
            battle_stats["battle_history"] = game_stats.battle_history
            battle_stats["total_battles"] = len(game_stats.battle_history)
            
            # 统计各阵营伤亡
            for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
                faction_stats = game_stats.faction_stats.get(faction, {})
                battle_stats["faction_battle_stats"][faction.value] = faction_stats
                
                # 计算伤亡统计
                casualties = {
                    "units_lost": faction_stats.get("units_lost", 0),
                    "damage_dealt": faction_stats.get("damage_dealt", 0),
                    "damage_taken": faction_stats.get("damage_taken", 0)
                }
                battle_stats["casualties"][faction.value] = casualties
        
        return battle_stats
    
    def _collect_map_statistics(self) -> Dict[str, Any]:
        """收集地图统计"""
        map_data = self.world.get_singleton_component(MapData)
        
        map_stats = {
            "map_width": 0,
            "map_height": 0,
            "total_tiles": 0,
            "terrain_distribution": {},
            "territory_control": {},
            "symmetry_type": "unknown",
            "special_features": {}
        }
        
        if map_data:
            map_stats["map_width"] = map_data.width
            map_stats["map_height"] = map_data.height
            map_stats["total_tiles"] = len(map_data.tiles)
            
            # 统计地形分布
            terrain_counts = {}
            for tile_entity in map_data.tiles.values():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain:
                    terrain_type = terrain.terrain_type.value
                    terrain_counts[terrain_type] = terrain_counts.get(terrain_type, 0) + 1
            
            map_stats["terrain_distribution"] = terrain_counts
            
            # 统计领土控制
            for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
                controlled_tiles = 0
                fortified_tiles = 0
                
                for tile_entity in map_data.tiles.values():
                    territory = self.world.get_component(tile_entity, TerritoryControl)
                    if territory and territory.controlling_faction == faction:
                        controlled_tiles += 1
                        if territory.fortified:
                            fortified_tiles += 1
                
                if controlled_tiles > 0:
                    map_stats["territory_control"][faction.value] = {
                        "controlled_tiles": controlled_tiles,
                        "fortified_tiles": fortified_tiles
                    }
            
            # 获取地图对称类型（从MapSystem）
            map_system = None
            for system in self.world.systems:
                if system.__class__.__name__ == "MapSystem":
                    map_system = system
                    break
            
            if map_system:
                map_stats["symmetry_type"] = getattr(map_system, 'symmetry_type', 'unknown')
        
        return map_stats
    
    def _collect_performance_statistics(self) -> Dict[str, Any]:
        """收集性能统计"""
        # 这里可以收集帧率、内存使用等性能数据
        # 目前先返回占位数据
        return {
            "fps_statistics": {
                "average_fps": 60.0,  # 占位数据
                "min_fps": 45.0,
                "max_fps": 75.0
            },
            "memory_usage": {
                "total_memory": "128MB",  # 占位数据
                "peak_memory": "150MB"
            },
            "rendering_performance": {
                "render_calls_per_frame": 100,  # 占位数据
                "texture_memory": "64MB"
            },
            "system_performance": {
                "cpu_usage": "15%",  # 占位数据
                "gpu_usage": "25%"
            }
        }
    
    def _collect_placeholder_data(self) -> Dict[str, Any]:
        """收集Agent和模型信息（原占位数据方法）"""
        # 获取Agent信息注册表
        registry = self.world.get_singleton_component(AgentInfoRegistry)
        
        model_info = {}
        agent_endpoints = {}
        
        if registry:
            print(f"[SettlementReport] 📋 发现Agent注册表，已注册阵营: {list(registry.agents.keys())}")
            
            for faction in ["wei", "shu", "wu"]:
                agent_info = registry.get_agent_info(faction)
                if agent_info:
                    model_info[faction] = agent_info.model_id
                    agent_endpoints[faction] = agent_info.base_url
                    print(f"[SettlementReport] ✅ {faction}阵营: {agent_info.provider}:{agent_info.model_id}")
                else:
                    model_info[faction] = "placeholder_model"
                    agent_endpoints[faction] = "unknown"
                    print(f"[SettlementReport] ⚠️ {faction}阵营: 未注册Agent信息，使用占位符")
        else:
            print(f"[SettlementReport] ⚠️ 未发现Agent注册表，使用占位符")
            # 使用占位符
            for faction in ["wei", "shu", "wu"]:
                model_info[faction] = "placeholder_model"
                agent_endpoints[faction] = "unknown"
        
        return {
            "model_info": model_info,
            "agent_endpoints": agent_endpoints,  # 新增字段
            "strategy_scores": {
                "wei": 0.0,  # 占位，待实现
                "shu": 0.0
            },
            "enable_thinking": None,  # 占位，待实现
            "response_times": {
                "wei": 0,  # 占位，待实现
                "shu": 0
            }
        }
    
    def _get_map_type(self) -> str:
        """获取地图类型"""
        # 检查MapSystem的地图类型
        for system in self.world.systems:
            if system.__class__.__name__ == "MapSystem":
                symmetry_type = getattr(system, 'symmetry_type', 'unknown')
                if symmetry_type == "moba":
                    return "MOBA风格地图"
                elif symmetry_type == "river_split":
                    return "河流分割对角线竞技地图"
                elif symmetry_type == "diagonal":
                    return "对角线对称竞技地图"
                elif symmetry_type == "square":
                    return "正方形竞技地图"
                elif symmetry_type == "horizontal":
                    return "水平轴对称竞技地图"
                else:
                    return f"自定义地图({symmetry_type})"
        
        return "标准随机地图"
    
    def _check_half_win_condition(self, winner_faction: Faction) -> bool:
        """检查是否为半歼胜利"""
        # 统计双方存活单位数量
        winner_surviving = 0
        loser_surviving = 0
        
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)
            
            if unit_count and unit_count.current_count > 0:
                if unit.faction == winner_faction:
                    winner_surviving += 1
                else:
                    loser_surviving += 1
        
        # 如果失败方仍有较多存活单位，则为半歼胜利
        return loser_surviving > winner_surviving * 0.3  # 失败方存活超过30%算半歼
    
    def _get_unit_position(self, entity: int) -> Optional[Dict[str, int]]:
        """获取单位位置"""
        from ..components import HexPosition
        position = self.world.get_component(entity, HexPosition)
        if position:
            return {"col": position.col, "row": position.row}
        return None
    
    def _save_report_to_files(self, report_data: Dict[str, Any]) -> None:
        """保存报告到文件"""
        try:
            # 创建报告目录
            report_dir = "settlement_reports"
            os.makedirs(report_dir, exist_ok=True)
            
            # 预处理数据，确保JSON可序列化
            json_safe_data = self._prepare_json_safe_data(report_data)
            
            # 验证预处理后的数据
            if not self._validate_json_data(json_safe_data):
                print("[SettlementReport] ⚠️ JSON数据验证失败，尝试修复...")
                # 如果验证失败，尝试更激进的清理
                json_safe_data = self._force_clean_data(report_data)
            
            # 保存为JSON文件
            json_file = os.path.join(report_dir, f"settlement_{report_data['experiment_id']}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(json_safe_data, f, ensure_ascii=False, indent=2)
            
            # 保存到CSV文件便于统计分析
            csv_file = os.path.join(report_dir, "settlement_results.csv")
            csv_exists = os.path.exists(csv_file)
            
            with open(csv_file, "a", encoding="utf-8", newline="") as f:
                if not csv_exists:
                    # 🆕 更新CSV头部，添加 current_units 字段
                    headers = [
                        "experiment_id", "timestamp", "map_type", "game_mode", "is_tie", "winner_faction",
                        "is_half_win", "game_duration_seconds", "total_turns",
                        "wei_total_units", "wei_current_units", "wei_surviving_units", "wei_destroyed_units",
                        "shu_total_units", "shu_current_units", "shu_surviving_units", "shu_destroyed_units",
                        "total_battles", "symmetry_type"
                    ]
                    f.write(",".join(headers) + "\n")
                
                # 🆕 更新数据行，添加 current_units 数据
                row_data = [
                    report_data["experiment_id"],
                    report_data["timestamp"],
                    report_data["map_type"],
                    report_data.get("game_mode", "unknown"),
                    str(report_data["is_tie"]),
                    report_data["winner_faction"].value if report_data["winner_faction"] else "tie",
                    str(report_data["is_half_win"]),
                    f"{report_data['game_duration_seconds']:.2f}",
                    str(report_data.get("total_turns", 0)),
                    str(report_data["units_info"].get("wei", {}).get("total_units", 0)),
                    str(report_data["units_info"].get("wei", {}).get("current_units", 0)),  # 🆕
                    str(report_data["units_info"].get("wei", {}).get("surviving_units", 0)),
                    str(report_data["units_info"].get("wei", {}).get("destroyed_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("total_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("current_units", 0)),  # 🆕
                    str(report_data["units_info"].get("shu", {}).get("surviving_units", 0)),
                    str(report_data["units_info"].get("shu", {}).get("destroyed_units", 0)),
                    str(report_data["battle_statistics"]["total_battles"]),
                    report_data["map_statistics"]["symmetry_type"]
                ]
                f.write(",".join(row_data) + "\n")
            
            print(f"[SettlementReport] 📁 报告已保存到: {json_file}")
            print(f"[SettlementReport] 📊 CSV数据已追加到: {csv_file}")
            
        except Exception as e:
            print(f"[SettlementReport] ❌ 保存报告文件时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _prepare_json_safe_data(self, data: Any) -> Any:
        """准备JSON安全的数据，处理不可序列化的对象"""
        try:
            if isinstance(data, dict):
                return {key: self._prepare_json_safe_data(value) for key, value in data.items()}
            elif isinstance(data, list):
                return [self._prepare_json_safe_data(item) for item in data]
            elif hasattr(data, 'value'):  # 处理枚举对象（如Faction）
                return data.value
            elif hasattr(data, '__dict__'):  # 处理其他对象
                return str(data)
            elif isinstance(data, (int, float, str, bool, type(None))):
                # 基本类型直接返回
                return data
            else:
                # 其他类型转换为字符串
                return str(data)
        except Exception as e:
            print(f"[SettlementReport] ⚠️ 数据预处理警告: {type(data)} -> {e}")
            return f"<无法序列化: {type(data).__name__}>"
    
    def _validate_json_data(self, data: Any) -> bool:
        """验证数据是否可以安全地序列化为JSON"""
        try:
            # 尝试序列化一小部分数据来验证
            json.dumps(data, ensure_ascii=False)
            return True
        except (TypeError, ValueError) as e:
            print(f"[SettlementReport] ❌ JSON验证失败: {e}")
            return False
    
    def _force_clean_data(self, data: Any) -> Any:
        """强制清理数据，移除所有可能导致JSON序列化失败的内容"""
        try:
            if isinstance(data, dict):
                cleaned_dict = {}
                for key, value in data.items():
                    # 确保键是字符串
                    safe_key = str(key) if not isinstance(key, str) else key
                    try:
                        cleaned_dict[safe_key] = self._force_clean_data(value)
                    except Exception:
                        # 如果某个值无法处理，跳过它
                        continue
                return cleaned_dict
            elif isinstance(data, list):
                cleaned_list = []
                for item in data:
                    try:
                        cleaned_list.append(self._force_clean_data(item))
                    except Exception:
                        # 如果某个项目无法处理，跳过它
                        continue
                return cleaned_list
            elif isinstance(data, (int, float, str, bool, type(None))):
                return data
            elif hasattr(data, 'value'):
                # 枚举对象
                return data.value
            else:
                # 其他所有类型都转换为字符串
                return str(data)
        except Exception as e:
            print(f"[SettlementReport] ⚠️ 强制清理警告: {type(data)} -> {e}")
            return f"<清理失败: {type(data).__name__}>"
    
    def _print_report_summary(self, report_data: Dict[str, Any]) -> None:
        """打印报告摘要到控制台"""
        print("\n" + "=" * 80)
        print("🎯 游戏结算报告")
        print("=" * 80)
        print(f"📅 实验ID: {report_data['experiment_id']}")
        print(f"⏰ 生成时间: {report_data['timestamp']}")
        print(f"🗺️ 地图类型: {report_data['map_type']}")
        print(f"🎮 游戏模式: {report_data.get('game_mode', 'unknown')}")
        print(f"🔄 地图对称性: {report_data['map_statistics']['symmetry_type']}")
        
        print(f"\n🏆 游戏结果:")
        if report_data["is_tie"]:
            print("   结果: 平局")
        else:
            winner = report_data["winner_faction"]
            victory_type = "半歼胜利" if report_data["is_half_win"] else "全歼胜利"
            print(f"   结果: {winner.value}阵营{victory_type}")
        
        print(f"⏱️ 游戏时长: {report_data['game_duration_formatted']}")
        
        # 根据游戏模式显示不同信息
        if report_data.get("game_mode") == "turn_based":
            print(f"🔄 总回合数: {report_data.get('total_turns', 0)}")
        else:
            print(f"⚡ 实时模式: 无回合限制")
        
        print(f"\n⚔️ 战斗统计:")
        print(f"   总战斗次数: {report_data['battle_statistics']['total_battles']}")
        
        print(f"\n👥 单位统计:")
        for faction_key in ["wei", "shu"]:
            if faction_key in report_data["units_info"]:
                faction_data = report_data["units_info"][faction_key]
                print(f"   {faction_key.upper()}阵营:")
                print(f"     总单位数: {faction_data['total_units']}")
                print(f"     存活单位: {faction_data['surviving_units']}")
                print(f"     损失单位: {faction_data['destroyed_units']}")
        
        print(f"\n🗺️ 地图统计:")
        map_stats = report_data["map_statistics"]
        print(f"   地图尺寸: {map_stats['map_width']}x{map_stats['map_height']}")
        print(f"   总地块数: {map_stats['total_tiles']}")
        
        print(f"   地形分布:")
        for terrain, count in map_stats["terrain_distribution"].items():
            percentage = count / map_stats["total_tiles"] * 100
            print(f"     {terrain}: {count}块 ({percentage:.1f}%)")
        
        print("=" * 80)
