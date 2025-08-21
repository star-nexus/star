"""
结算报告渲染系统
Settlement Report Render System
"""

import pygame
from typing import Dict, Any, Optional
from framework import System, RMS
from ..components.settlement_report import SettlementReport
from ..prefabs.config import GameConfig, Faction


class SettlementReportRenderSystem(System):
    """结算报告渲染系统"""
    
    def __init__(self):
        super().__init__(priority=10)  # 高优先级，在UI层渲染
        self.font_cache = {}
        self.scroll_offset = 0
        self.max_scroll = 0
        
    def initialize(self, world) -> None:
        self.world = world
        
    def subscribe_events(self):
        """订阅事件"""
        pass
        
    def update(self, delta_time: float) -> None:
        """更新系统"""
        pass
        
    def render(self, screen: pygame.Surface) -> None:
        """渲染结算报告"""
        settlement_report = self.world.get_singleton_component(SettlementReport)
        if not settlement_report:
            return
            
        # 渲染报告背景
        self._render_report_background(screen)
        
        # 渲染报告标题
        self._render_report_title(screen)
        
        # 渲染基本信息
        self._render_basic_info(screen, settlement_report)
        
        # 渲染游戏结果
        self._render_game_result(screen, settlement_report)
        
        # 渲染单位统计
        self._render_units_statistics(screen, settlement_report)
        
        # 渲染战斗统计
        self._render_battle_statistics(screen, settlement_report)
        
        # 渲染地图统计
        self._render_map_statistics(screen, settlement_report)
        
        # 渲染占位信息（待实现功能）
        self._render_placeholder_info(screen, settlement_report)
        
        # 渲染滚动条
        self._render_scrollbar(screen)
    
    def _render_report_background(self, screen: pygame.Surface) -> None:
        """渲染报告背景"""
        # 创建半透明背景
        background_surface = pygame.Surface((GameConfig.WINDOW_WIDTH - 40, GameConfig.WINDOW_HEIGHT - 200))
        background_surface.set_alpha(230)
        background_surface.fill((30, 30, 40))
        
        # 绘制边框
        pygame.draw.rect(background_surface, (80, 80, 100), background_surface.get_rect(), 3)
        
        # 绘制到屏幕
        screen.blit(background_surface, (20, 100))
    
    def _render_report_title(self, screen: pygame.Surface) -> None:
        """渲染报告标题"""
        title_font = self._get_font(28, bold=True)
        title_text = "🎯 游戏结算报告"
        title_surface = title_font.render(title_text, True, (255, 215, 0))  # 金色
        
        title_rect = title_surface.get_rect(center=(GameConfig.WINDOW_WIDTH // 2, 120))
        screen.blit(title_surface, title_rect)
    
    def _render_basic_info(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染基本信息"""
        font = self._get_font(16)
        y_offset = 160 + self.scroll_offset
        
        # 实验ID
        id_text = f"📅 实验ID: {report.experiment_id}"
        id_surface = font.render(id_text, True, (200, 200, 200))
        screen.blit(id_surface, (40, y_offset))
        y_offset += 25
        
        # 生成时间
        time_text = f"⏰ 生成时间: {report.timestamp}"
        time_surface = font.render(time_text, True, (200, 200, 200))
        screen.blit(time_surface, (40, y_offset))
        y_offset += 25
        
        # 游戏模式
        mode_text = f"🎮 游戏模式: {self._format_game_mode(report.game_mode)}"
        mode_surface = font.render(mode_text, True, (200, 200, 200))
        screen.blit(mode_surface, (40, y_offset))
        y_offset += 25
        
        # 地图类型
        map_text = f"🗺️ 地图类型: {report.map_type}"
        map_surface = font.render(map_text, True, (200, 200, 200))
        screen.blit(map_surface, (40, y_offset))
        y_offset += 25
        
        # 地图对称性
        symmetry_text = f"🔄 地图对称性: {report.map_statistics.get('symmetry_type', 'unknown')}"
        symmetry_surface = font.render(symmetry_text, True, (200, 200, 200))
        screen.blit(symmetry_surface, (40, y_offset))
        y_offset += 35
        
        return y_offset
    
    def _format_game_mode(self, game_mode: str) -> str:
        """格式化游戏模式显示"""
        mode_display = {
            "turn_based": "回合制",
            "real_time": "即时制",
            "real_time": "即时制",  # 兼容两种拼写
            "unknown": "未知模式"
        }
        return mode_display.get(game_mode, game_mode)
    
    def _render_game_result(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染游戏结果"""
        font = self._get_font(18, bold=True)
        y_offset = 300 + self.scroll_offset
        
        # 结果标题
        result_title = "🏆 游戏结果"
        result_surface = font.render(result_title, True, (255, 255, 255))
        screen.blit(result_surface, (40, y_offset))
        y_offset += 30
        
        # 结果内容
        content_font = self._get_font(16)
        
        if report.is_tie:
            result_text = "   结果: 平局"
            result_color = (255, 255, 0)  # 黄色
        else:
            winner = report.winner_faction
            victory_type = "半歼胜利" if report.is_half_win else "全歼胜利"
            result_text = f"   结果: {winner.value}阵营{victory_type}"
            result_color = (0, 255, 0) if winner == Faction.WEI else (255, 100, 100)  # 绿色或红色
        
        result_surface = content_font.render(result_text, True, result_color)
        screen.blit(result_surface, (40, y_offset))
        y_offset += 25
        
        # 游戏时长
        duration_text = f"⏱️ 游戏时长: {report.game_duration_formatted}"
        duration_surface = content_font.render(duration_text, True, (200, 200, 200))
        screen.blit(duration_surface, (40, y_offset))
        y_offset += 25
        
        # 根据游戏模式显示不同信息
        if report.game_mode == "turn_based":
            # 回合制模式：显示回合数
            turns_text = f"🔄 总回合数: {report.total_turns}"
            turns_surface = content_font.render(turns_text, True, (200, 200, 200))
            screen.blit(turns_surface, (40, y_offset))
            y_offset += 25
        else:
            # 即时制模式：显示游戏时长（已显示）和实时统计
            realtime_text = f"⚡ 实时模式: 无回合限制"
            realtime_surface = content_font.render(realtime_text, True, (150, 200, 150))
            screen.blit(realtime_surface, (40, y_offset))
            y_offset += 25
        
        y_offset += 10
        
        return y_offset
    
    def _render_units_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染单位统计"""
        font = self._get_font(18, bold=True)
        y_offset = 500 + self.scroll_offset
        
        # 单位统计标题
        units_title = "👥 单位统计"
        units_surface = font.render(units_title, True, (255, 255, 255))
        screen.blit(units_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # 渲染各阵营统计
        for faction_key in ["wei", "shu"]:
            if faction_key in report.units_info:
                faction_data = report.units_info[faction_key]
                faction_name = faction_key.upper()
                
                # 阵营标题
                faction_title = f"   {faction_name}阵营:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # 总单位数
                total_text = f"     总单位数: {faction_data['total_units']}"
                total_surface = content_font.render(total_text, True, (200, 200, 200))
                screen.blit(total_surface, (40, y_offset))
                y_offset += 20
                
                # 存活单位
                surviving_text = f"     存活单位: {faction_data['surviving_units']}"
                surviving_surface = content_font.render(surviving_text, True, (100, 255, 100))
                screen.blit(surviving_surface, (40, y_offset))
                y_offset += 20
                
                # 损失单位
                destroyed_text = f"     损失单位: {faction_data['destroyed_units']}"
                destroyed_surface = content_font.render(destroyed_text, True, (255, 100, 100))
                screen.blit(destroyed_surface, (40, y_offset))
                y_offset += 20
                
                # 总生命值
                health_text = f"     总生命值: {faction_data['total_health']}"
                health_surface = content_font.render(health_text, True, (200, 200, 200))
                screen.blit(health_surface, (40, y_offset))
                y_offset += 25
        
        return y_offset
    
    def _render_battle_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染战斗统计"""
        font = self._get_font(18, bold=True)
        y_offset = 800 + self.scroll_offset
        
        # 战斗统计标题
        battle_title = "⚔️ 战斗统计"
        battle_surface = font.render(battle_title, True, (255, 255, 255))
        screen.blit(battle_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # 总战斗次数
        total_battles_text = f"   总战斗次数: {report.battle_statistics['total_battles']}"
        total_battles_surface = content_font.render(total_battles_text, True, (200, 200, 200))
        screen.blit(total_battles_surface, (40, y_offset))
        y_offset += 25
        
        # 各阵营战斗统计
        for faction_key in ["wei", "shu"]:
            if faction_key in report.battle_statistics["faction_battle_stats"]:
                faction_stats = report.battle_statistics["faction_battle_stats"][faction_key]
                faction_name = faction_key.upper()
                
                faction_title = f"   {faction_name}阵营战斗统计:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # 单位损失
                units_lost = faction_stats.get("units_lost", 0)
                units_lost_text = f"     单位损失: {units_lost}"
                units_lost_surface = content_font.render(units_lost_text, True, (255, 100, 100))
                screen.blit(units_lost_surface, (40, y_offset))
                y_offset += 20
                
                # 造成伤害
                damage_dealt = faction_stats.get("damage_dealt", 0)
                damage_dealt_text = f"     造成伤害: {damage_dealt}"
                damage_dealt_surface = content_font.render(damage_dealt_text, True, (100, 255, 100))
                screen.blit(damage_dealt_surface, (40, y_offset))
                y_offset += 20
                
                # 承受伤害
                damage_taken = faction_stats.get("damage_taken", 0)
                damage_taken_text = f"     承受伤害: {damage_taken}"
                damage_taken_surface = content_font.render(damage_taken_text, True, (255, 150, 100))
                screen.blit(damage_taken_surface, (40, y_offset))
                y_offset += 25
        
        return y_offset
    
    def _render_map_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染地图统计"""
        font = self._get_font(18, bold=True)
        y_offset = 1100 + self.scroll_offset
        
        # 地图统计标题
        map_title = "🗺️ 地图统计"
        map_surface = font.render(map_title, True, (255, 255, 255))
        screen.blit(map_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        map_stats = report.map_statistics
        
        # 地图尺寸
        size_text = f"   地图尺寸: {map_stats['map_width']}x{map_stats['map_height']}"
        size_surface = content_font.render(size_text, True, (200, 200, 200))
        screen.blit(size_surface, (40, y_offset))
        y_offset += 20
        
        # 总地块数
        tiles_text = f"   总地块数: {map_stats['total_tiles']}"
        tiles_surface = content_font.render(tiles_text, True, (200, 200, 200))
        screen.blit(tiles_surface, (40, y_offset))
        y_offset += 25
        
        # 地形分布
        terrain_title = "   地形分布:"
        terrain_surface = content_font.render(terrain_title, True, (255, 200, 100))
        screen.blit(terrain_surface, (40, y_offset))
        y_offset += 20
        
        for terrain, count in map_stats["terrain_distribution"].items():
            percentage = count / map_stats["total_tiles"] * 100
            terrain_text = f"     {terrain}: {count}块 ({percentage:.1f}%)"
            terrain_surface = content_font.render(terrain_text, True, (200, 200, 200))
            screen.blit(terrain_surface, (40, y_offset))
            y_offset += 20
        
        y_offset += 10
        
        # 领土控制统计
        territory_title = "   领土控制:"
        territory_surface = content_font.render(territory_title, True, (255, 200, 100))
        screen.blit(territory_surface, (40, y_offset))
        y_offset += 20
        
        for faction_key in ["wei", "shu"]:
            if faction_key in map_stats["territory_control"]:
                territory_data = map_stats["territory_control"][faction_key]
                faction_name = faction_key.upper()
                
                territory_text = f"     {faction_name}: {territory_data['controlled_tiles']}块"
                territory_surface = content_font.render(territory_text, True, (200, 200, 200))
                screen.blit(territory_surface, (40, y_offset))
                y_offset += 20
                
                if territory_data.get("fortified_tiles", 0) > 0:
                    fortified_text = f"       工事: {territory_data['fortified_tiles']}块"
                    fortified_surface = content_font.render(fortified_text, True, (255, 150, 100))
                    screen.blit(fortified_surface, (40, y_offset))
                    y_offset += 20
        
        return y_offset
    
    def _render_placeholder_info(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """渲染Agent和模型信息"""
        font = self._get_font(18, bold=True)
        y_offset = 1500 + self.scroll_offset
        
        # Agent信息标题
        agent_title = "🤖 Agent & 模型信息"
        agent_surface = font.render(agent_title, True, (255, 255, 255))
        screen.blit(agent_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # 渲染各阵营的模型信息
        for faction_key in ["wei", "shu"]:
            if faction_key in report.model_info:
                model_name = report.model_info[faction_key]
                endpoint = report.agent_endpoints.get(faction_key, "unknown")
                
                faction_name = faction_key.upper()
                
                # 阵营标题
                faction_title = f"   {faction_name}阵营:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # 模型信息
                model_color = (100, 255, 100) if model_name != "placeholder_model" else (150, 150, 150)
                model_text = f"     模型: {model_name}"
                model_surface = content_font.render(model_text, True, model_color)
                screen.blit(model_surface, (40, y_offset))
                y_offset += 20
                
                # 服务端点
                endpoint_color = (200, 200, 200) if endpoint != "unknown" else (150, 150, 150)
                endpoint_text = f"     端点: {endpoint}"
                endpoint_surface = content_font.render(endpoint_text, True, endpoint_color)
                screen.blit(endpoint_surface, (40, y_offset))
                y_offset += 25
        
        # 策略评分
        strategy_text = f"   策略评分: {report.strategy_scores}"
        strategy_surface = content_font.render(strategy_text, True, (150, 150, 150))
        screen.blit(strategy_surface, (40, y_offset))
        y_offset += 20
        
        # 思考模式
        thinking_text = f"   思考模式: {report.enable_thinking}"
        thinking_surface = content_font.render(thinking_text, True, (150, 150, 150))
        screen.blit(thinking_surface, (40, y_offset))
        y_offset += 20
        
        # 响应次数
        response_text = f"   响应次数: {report.response_times}"
        response_surface = content_font.render(response_text, True, (150, 150, 150))
        screen.blit(response_surface, (40, y_offset))
        y_offset += 25
        
        # 更新最大滚动距离
        self.max_scroll = max(0, y_offset - GameConfig.WINDOW_HEIGHT + 300)
    
    def _render_scrollbar(self, screen: pygame.Surface) -> None:
        """渲染滚动条"""
        if self.max_scroll <= 0:
            return
            
        # 滚动条位置和大小
        scrollbar_x = GameConfig.WINDOW_WIDTH - 25
        scrollbar_y = 100
        scrollbar_height = GameConfig.WINDOW_HEIGHT - 200
        
        # 滚动条背景
        pygame.draw.rect(screen, (60, 60, 80), 
                        (scrollbar_x, scrollbar_y, 15, scrollbar_height))
        
        # 滚动条滑块
        if self.max_scroll > 0:
            slider_height = max(30, (scrollbar_height * scrollbar_height) / (scrollbar_height + self.max_scroll))
            slider_y = scrollbar_y + (self.scroll_offset / self.max_scroll) * (scrollbar_height - slider_height)
            
            pygame.draw.rect(screen, (120, 120, 140), 
                           (scrollbar_x, slider_y, 15, slider_height))
    
    def _get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """获取字体（带缓存）"""
        cache_key = f"{size}_{bold}"
        if cache_key not in self.font_cache:
            try:
                font = pygame.font.Font(None, size)
                if bold:
                    font.set_bold(True)
                self.font_cache[cache_key] = font
            except:
                # 如果无法创建字体，使用默认字体
                self.font_cache[cache_key] = pygame.font.Font(None, 24)
        
        return self.font_cache[cache_key]
    
    def handle_scroll(self, direction: int) -> None:
        """处理滚动"""
        if direction > 0:  # 向下滚动
            self.scroll_offset = max(0, self.scroll_offset - 50)
        else:  # 向上滚动
            self.scroll_offset = min(self.max_scroll, self.scroll_offset + 50)
