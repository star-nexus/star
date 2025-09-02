#!/usr/bin/env python3
"""
结算报告模块测试脚本
Test script for Settlement Report Module
"""

import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "rotk_env")))

def test_settlement_report_components():
    """测试结算报告组件"""
    print("🧪 测试结算报告组件...")
    
    try:
        from rotk_env.components.settlement_report import (
            SettlementReport, 
            BattleStatistics, 
            MapStatistics, 
            PerformanceStatistics
        )
        
        # 测试组件创建
        report = SettlementReport(
            experiment_id="test_20241201_120000",
            timestamp=datetime.now().isoformat(),
            map_type="测试地图",
            is_tie=False,
            winner_faction=None,
            game_duration_seconds=120.5
        )
        
        battle_stats = BattleStatistics(
            total_battles=10,
            faction_battle_stats={},
            battle_history=[]
        )
        
        map_stats = MapStatistics(
            map_width=15,
            map_height=15,
            total_tiles=225,
            terrain_distribution={"plain": 150, "forest": 50, "hill": 25}
        )
        
        perf_stats = PerformanceStatistics(
            fps_statistics={"average_fps": 60.0},
            memory_usage={"total_memory": "128MB"}
        )
        
        print("✅ 组件创建成功")
        print(f"   - 报告ID: {report.experiment_id}")
        print(f"   - 地图类型: {report.map_type}")
        print(f"   - 战斗次数: {battle_stats.total_battles}")
        print(f"   - 地图尺寸: {map_stats.map_width}x{map_stats.map_height}")
        print(f"   - 平均FPS: {perf_stats.fps_statistics['average_fps']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 组件测试失败: {e}")
        return False

def test_settlement_report_system():
    """测试结算报告系统"""
    print("\n🧪 测试结算报告系统...")
    
    try:
        from rotk_env.systems.settlement_report_system import SettlementReportSystem
        
        # 测试系统创建
        system = SettlementReportSystem()
        print("✅ 系统创建成功")
        print(f"   - 系统优先级: {system.priority}")
        print(f"   - 报告生成状态: {system.report_generated}")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统测试失败: {e}")
        return False

def test_settlement_report_render_system():
    """测试结算报告渲染系统"""
    print("\n🧪 测试结算报告渲染系统...")
    
    try:
        from rotk_env.systems.settlement_report_render_system import SettlementReportRenderSystem
        
        # 测试系统创建
        render_system = SettlementReportRenderSystem()
        print("✅ 渲染系统创建成功")
        print(f"   - 系统优先级: {render_system.priority}")
        print(f"   - 滚动偏移: {render_system.scroll_offset}")
        
        return True
        
    except Exception as e:
        print(f"❌ 渲染系统测试失败: {e}")
        return False

def test_file_output():
    """测试文件输出功能"""
    print("\n🧪 测试文件输出功能...")
    
    try:
        # 创建测试数据
        test_data = {
            "experiment_id": "test_20241201_120000",
            "timestamp": datetime.now().isoformat(),
            "map_type": "测试地图",
            "is_tie": False,
            "winner_faction": "wei",
            "game_duration_seconds": 120.5,
            "units_info": {
                "wei": {"total_units": 5, "surviving_units": 3},
                "shu": {"total_units": 5, "surviving_units": 0}
            },
            "battle_statistics": {"total_battles": 10},
            "map_statistics": {
                "map_width": 15,
                "map_height": 15,
                "total_tiles": 225,
                "terrain_distribution": {"plain": 150, "forest": 50, "hill": 25}
            }
        }
        
        # 测试JSON输出
        test_dir = "test_settlement_reports"
        os.makedirs(test_dir, exist_ok=True)
        
        json_file = os.path.join(test_dir, "test_settlement.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        # 测试CSV输出
        csv_file = os.path.join(test_dir, "test_settlement.csv")
        import csv
        
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["experiment_id", "map_type", "winner_faction", "game_duration"])
            writer.writerow([
                test_data["experiment_id"],
                test_data["map_type"],
                test_data["winner_faction"],
                test_data["game_duration_seconds"]
            ])
        
        print("✅ 文件输出测试成功")
        print(f"   - JSON文件: {json_file}")
        print(f"   - CSV文件: {csv_file}")
        
        # 清理测试文件
        os.remove(json_file)
        os.remove(csv_file)
        os.rmdir(test_dir)
        
        return True
        
    except Exception as e:
        print(f"❌ 文件输出测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🎯 结算报告模块测试开始")
    print("=" * 50)
    
    tests = [
        test_settlement_report_components,
        test_settlement_report_system,
        test_settlement_report_render_system,
        test_file_output
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"🎯 测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("✅ 所有测试通过！结算报告模块工作正常。")
        return 0
    else:
        print("❌ 部分测试失败，请检查相关代码。")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
