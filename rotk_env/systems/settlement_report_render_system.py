"""
Settlement Report Render System.
Renders a scrollable post-game summary: metadata, results, unit/battle/map stats,
and agent/model info, with a simple scrollbar.
"""

import pygame
from typing import Dict, Any, Optional
from framework import System, RMS
from ..components.settlement_report import SettlementReport
from ..prefabs.config import GameConfig, Faction


class SettlementReportRenderSystem(System):
    """Render the settlement (post-game) report overlay."""
    
    def __init__(self):
        super().__init__(priority=10)  # render late on UI layer
        self.font_cache = {}
        self.scroll_offset = 0
        self.max_scroll = 0
        
    def initialize(self, world) -> None:
        self.world = world
        
    def subscribe_events(self):
        """No event subscriptions; driven by scene and render() call."""
        pass
        
    def update(self, delta_time: float) -> None:
        """No per-frame logic; rendering is done via render(screen)."""
        pass
        
    def render(self, screen: pygame.Surface) -> None:
        """Render the settlement report to the given screen surface."""
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
        """Render semi-transparent background panel and border."""
        # Semi-transparent background
        background_surface = pygame.Surface((GameConfig.WINDOW_WIDTH - 40, GameConfig.WINDOW_HEIGHT - 200))
        background_surface.set_alpha(230)
        background_surface.fill((30, 30, 40))
        
        # Border
        pygame.draw.rect(background_surface, (80, 80, 100), background_surface.get_rect(), 3)
        
        # Blit on screen
        screen.blit(background_surface, (20, 100))
    
    def _render_report_title(self, screen: pygame.Surface) -> None:
        """Render report title."""
        title_font = self._get_font(28, bold=True)
        title_text = "🎯 Game Settlement Report"
        title_surface = title_font.render(title_text, True, (255, 215, 0))  # gold
        
        title_rect = title_surface.get_rect(center=(GameConfig.WINDOW_WIDTH // 2, 120))
        screen.blit(title_surface, title_rect)
    
    def _render_basic_info(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render basic metadata of the run."""
        font = self._get_font(16)
        y_offset = 160 + self.scroll_offset
        
        # Experiment ID
        id_text = f"📅 Experiment ID: {report.experiment_id}"
        id_surface = font.render(id_text, True, (200, 200, 200))
        screen.blit(id_surface, (40, y_offset))
        y_offset += 25
        
        # Timestamp
        time_text = f"⏰ Generated at: {report.timestamp}"
        time_surface = font.render(time_text, True, (200, 200, 200))
        screen.blit(time_surface, (40, y_offset))
        y_offset += 25
        
        # Game mode
        mode_text = f"🎮 Game mode: {self._format_game_mode(report.game_mode)}"
        mode_surface = font.render(mode_text, True, (200, 200, 200))
        screen.blit(mode_surface, (40, y_offset))
        y_offset += 25
        
        # Map type
        map_text = f"🗺️ Map type: {report.map_type}"
        map_surface = font.render(map_text, True, (200, 200, 200))
        screen.blit(map_surface, (40, y_offset))
        y_offset += 25
        
        # Map symmetry
        symmetry_text = f"🔄 Map symmetry: {report.map_statistics.get('symmetry_type', 'unknown')}"
        symmetry_surface = font.render(symmetry_text, True, (200, 200, 200))
        screen.blit(symmetry_surface, (40, y_offset))
        y_offset += 35
        
        return y_offset
    
    def _format_game_mode(self, game_mode: str) -> str:
        """Format game mode for display (English)."""
        mode_display = {
            "turn_based": "Turn-based",
            "real_time": "Real-time",
            "unknown": "Unknown",
        }
        return mode_display.get(game_mode, str(game_mode))
    
    def _render_game_result(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render game result summary."""
        font = self._get_font(18, bold=True)
        y_offset = 300 + self.scroll_offset
        
        # Result title
        result_title = "🏆 Game Result"
        result_surface = font.render(result_title, True, (255, 255, 255))
        screen.blit(result_surface, (40, y_offset))
        y_offset += 30
        
        # Result content
        content_font = self._get_font(16)
        
        if report.is_tie:
            result_text = "   Result: Draw"
            result_color = (255, 255, 0)  # yellow
        else:
            winner = report.winner_faction
            victory_type = "Decisive Victory" if not report.is_half_win else "Partial Victory"
            result_text = f"   Result: {winner.value} faction — {victory_type}"
            # Use a neutral highlight color
            result_color = (180, 220, 255)
        
        result_surface = content_font.render(result_text, True, result_color)
        screen.blit(result_surface, (40, y_offset))
        y_offset += 25
        
        # Duration
        duration_text = f"⏱️ Game duration: {report.game_duration_formatted}"
        duration_surface = content_font.render(duration_text, True, (200, 200, 200))
        screen.blit(duration_surface, (40, y_offset))
        y_offset += 25
        
        # Mode-specific info
        if report.game_mode == "turn_based":
            # Turn-based: show total turns
            turns_text = f"🔄 Total turns: {report.total_turns}"
            turns_surface = content_font.render(turns_text, True, (200, 200, 200))
            screen.blit(turns_surface, (40, y_offset))
            y_offset += 25
        else:
            # Real-time: already covered by duration
            realtime_text = f"⚡ Real-time mode: no turn limit"
            realtime_surface = content_font.render(realtime_text, True, (150, 200, 150))
            screen.blit(realtime_surface, (40, y_offset))
            y_offset += 25
        
        y_offset += 10
        
        return y_offset
    
    def _render_units_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render unit statistics per faction."""
        font = self._get_font(18, bold=True)
        y_offset = 500 + self.scroll_offset
        
        # Section title
        units_title = "👥 Unit Statistics"
        units_surface = font.render(units_title, True, (255, 255, 255))
        screen.blit(units_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # Per-faction
        for faction_key in ["wei", "shu"]:
            if faction_key in report.units_info:
                faction_data = report.units_info[faction_key]
                faction_name = faction_key.upper()
                
                # Faction header
                faction_title = f"   {faction_name} Faction:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # Totals
                total_text = f"     Total units: {faction_data['total_units']}"
                total_surface = content_font.render(total_text, True, (200, 200, 200))
                screen.blit(total_surface, (40, y_offset))
                y_offset += 20
                
                # Surviving units
                surviving_text = f"     Surviving units: {faction_data['surviving_units']}"
                surviving_surface = content_font.render(surviving_text, True, (100, 255, 100))
                screen.blit(surviving_surface, (40, y_offset))
                y_offset += 20
                
                # Destroyed units
                destroyed_text = f"     Destroyed units: {faction_data['destroyed_units']}"
                destroyed_surface = content_font.render(destroyed_text, True, (255, 100, 100))
                screen.blit(destroyed_surface, (40, y_offset))
                y_offset += 20
                
                # Total health
                health_text = f"     Total health: {faction_data['total_health']}"
                health_surface = content_font.render(health_text, True, (200, 200, 200))
                screen.blit(health_surface, (40, y_offset))
                y_offset += 25
        
        return y_offset
    
    def _render_battle_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render battle statistics totals and per faction."""
        font = self._get_font(18, bold=True)
        y_offset = 800 + self.scroll_offset
        
        # Section title
        battle_title = "⚔️ Battle Statistics"
        battle_surface = font.render(battle_title, True, (255, 255, 255))
        screen.blit(battle_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # Totals
        total_battles_text = f"   Total battles: {report.battle_statistics['total_battles']}"
        total_battles_surface = content_font.render(total_battles_text, True, (200, 200, 200))
        screen.blit(total_battles_surface, (40, y_offset))
        y_offset += 25
        
        # Per-faction stats
        for faction_key in ["wei", "shu"]:
            if faction_key in report.battle_statistics["faction_battle_stats"]:
                faction_stats = report.battle_statistics["faction_battle_stats"][faction_key]
                faction_name = faction_key.upper()
                
                faction_title = f"   {faction_name} Faction:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # Unit losses
                units_lost = faction_stats.get("units_lost", 0)
                units_lost_text = f"     Units lost: {units_lost}"
                units_lost_surface = content_font.render(units_lost_text, True, (255, 100, 100))
                screen.blit(units_lost_surface, (40, y_offset))
                y_offset += 20
                
                # Damage dealt
                damage_dealt = faction_stats.get("damage_dealt", 0)
                damage_dealt_text = f"     Damage dealt: {damage_dealt}"
                damage_dealt_surface = content_font.render(damage_dealt_text, True, (100, 255, 100))
                screen.blit(damage_dealt_surface, (40, y_offset))
                y_offset += 20
                
                # Damage taken
                damage_taken = faction_stats.get("damage_taken", 0)
                damage_taken_text = f"     Damage taken: {damage_taken}"
                damage_taken_surface = content_font.render(damage_taken_text, True, (255, 150, 100))
                screen.blit(damage_taken_surface, (40, y_offset))
                y_offset += 25
        
        return y_offset
    
    def _render_map_statistics(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render map statistics summary."""
        font = self._get_font(18, bold=True)
        y_offset = 1100 + self.scroll_offset
        
        # Section title
        map_title = "🗺️ Map Statistics"
        map_surface = font.render(map_title, True, (255, 255, 255))
        screen.blit(map_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        map_stats = report.map_statistics
        
        # Map size
        size_text = f"   Map size: {map_stats['map_width']}x{map_stats['map_height']}"
        size_surface = content_font.render(size_text, True, (200, 200, 200))
        screen.blit(size_surface, (40, y_offset))
        y_offset += 20
        
        # Total tiles
        tiles_text = f"   Total tiles: {map_stats['total_tiles']}"
        tiles_surface = content_font.render(tiles_text, True, (200, 200, 200))
        screen.blit(tiles_surface, (40, y_offset))
        y_offset += 25
        
        # Terrain distribution
        terrain_title = "   Terrain distribution:"
        terrain_surface = content_font.render(terrain_title, True, (255, 200, 100))
        screen.blit(terrain_surface, (40, y_offset))
        y_offset += 20
        
        for terrain, count in map_stats["terrain_distribution"].items():
            percentage = count / map_stats["total_tiles"] * 100
            terrain_text = f"     {terrain}: {count} tiles ({percentage:.1f}%)"
            terrain_surface = content_font.render(terrain_text, True, (200, 200, 200))
            screen.blit(terrain_surface, (40, y_offset))
            y_offset += 20
        
        y_offset += 10
        
        # Territory control
        territory_title = "   Territory control:"
        territory_surface = content_font.render(territory_title, True, (255, 200, 100))
        screen.blit(territory_surface, (40, y_offset))
        y_offset += 20
        
        for faction_key in ["wei", "shu"]:
            if faction_key in map_stats["territory_control"]:
                territory_data = map_stats["territory_control"][faction_key]
                faction_name = faction_key.upper()
                
                territory_text = f"     {faction_name}: {territory_data['controlled_tiles']} tiles"
                territory_surface = content_font.render(territory_text, True, (200, 200, 200))
                screen.blit(territory_surface, (40, y_offset))
                y_offset += 20
                
                if territory_data.get("fortified_tiles", 0) > 0:
                    fortified_text = f"       Fortified: {territory_data['fortified_tiles']} tiles"
                    fortified_surface = content_font.render(fortified_text, True, (255, 150, 100))
                    screen.blit(fortified_surface, (40, y_offset))
                    y_offset += 20
        
        return y_offset
    
    def _render_placeholder_info(self, screen: pygame.Surface, report: SettlementReport) -> None:
        """Render agent/model information and settings placeholders."""
        font = self._get_font(18, bold=True)
        y_offset = 1500 + self.scroll_offset
        
        # Section title
        agent_title = "🤖 Agent & Model Info"
        agent_surface = font.render(agent_title, True, (255, 255, 255))
        screen.blit(agent_surface, (40, y_offset))
        y_offset += 30
        
        content_font = self._get_font(16)
        
        # Per-faction model info
        for faction_key in ["wei", "shu"]:
            if faction_key in report.model_info:
                model_name = report.model_info[faction_key]
                endpoint = report.agent_endpoints.get(faction_key, "unknown")
                
                faction_name = faction_key.upper()
                
                # Faction header
                faction_title = f"   {faction_name} Faction:"
                faction_surface = content_font.render(faction_title, True, (255, 200, 100))
                screen.blit(faction_surface, (40, y_offset))
                y_offset += 20
                
                # Model
                model_color = (100, 255, 100) if model_name != "placeholder_model" else (150, 150, 150)
                model_text = f"     Model: {model_name}"
                model_surface = content_font.render(model_text, True, model_color)
                screen.blit(model_surface, (40, y_offset))
                y_offset += 20
                
                # Endpoint
                endpoint_color = (200, 200, 200) if endpoint != "unknown" else (150, 150, 150)
                endpoint_text = f"     Endpoint: {endpoint}"
                endpoint_surface = content_font.render(endpoint_text, True, endpoint_color)
                screen.blit(endpoint_surface, (40, y_offset))
                y_offset += 25
        
        # Strategy scores
        strategy_text = f"   Strategy scores: {report.strategy_scores}"
        strategy_surface = content_font.render(strategy_text, True, (150, 150, 150))
        screen.blit(strategy_surface, (40, y_offset))
        y_offset += 20
        
        # Thinking mode
        thinking_text = f"   Thinking mode: {report.enable_thinking}"
        thinking_surface = content_font.render(thinking_text, True, (150, 150, 150))
        screen.blit(thinking_surface, (40, y_offset))
        y_offset += 20
        
        # Action count
        action_text = f"   Action count: {report.action_counts}"
        action_surface = content_font.render(action_text, True, (150, 150, 150))
        screen.blit(action_surface, (40, y_offset))
        y_offset += 25

        # Interaction count (message level)
        interaction_text = f"   Interaction count: {report.interaction_counts}"
        interaction_surface = content_font.render(interaction_text, True, (150, 150, 150))
        screen.blit(interaction_surface, (40, y_offset))
        y_offset += 25
        
        # Update max scroll distance
        self.max_scroll = max(0, y_offset - GameConfig.WINDOW_HEIGHT + 300)
    
    def _render_scrollbar(self, screen: pygame.Surface) -> None:
        """Render a simple scrollbar indicating scroll position."""
        if self.max_scroll <= 0:
            return
            
        # Scrollbar geometry
        scrollbar_x = GameConfig.WINDOW_WIDTH - 25
        scrollbar_y = 100
        scrollbar_height = GameConfig.WINDOW_HEIGHT - 200
        
        # Track
        pygame.draw.rect(screen, (60, 60, 80), 
                        (scrollbar_x, scrollbar_y, 15, scrollbar_height))
        
        # Thumb
        if self.max_scroll > 0:
            slider_height = max(30, (scrollbar_height * scrollbar_height) / (scrollbar_height + self.max_scroll))
            slider_y = scrollbar_y + (self.scroll_offset / self.max_scroll) * (scrollbar_height - slider_height)
            
            pygame.draw.rect(screen, (120, 120, 140), 
                           (scrollbar_x, slider_y, 15, slider_height))
    
    def _get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """Get a cached font at given size and weight."""
        cache_key = f"{size}_{bold}"
        if cache_key not in self.font_cache:
            try:
                font = pygame.font.Font(None, size)
                if bold:
                    font.set_bold(True)
                self.font_cache[cache_key] = font
            except:
                # Fallback to default font
                self.font_cache[cache_key] = pygame.font.Font(None, 24)
        
        return self.font_cache[cache_key]
    
    def handle_scroll(self, wheel_y: int) -> None:
        """Handle mouse wheel scroll (wheel_y > 0 = scroll up in pygame)."""
        # In pygame, MouseWheelEvent.y > 0 when scrolling up
        if wheel_y > 0:  # scroll up
            self.scroll_offset = max(0, self.scroll_offset - 50)
        else:  # scroll down
            self.scroll_offset = min(self.max_scroll, self.scroll_offset + 50)
