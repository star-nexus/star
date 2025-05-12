"""
系统调度器模块

管理系统执行顺序、分组和依赖关系
"""

from typing import Dict, List, Set, Type, Callable, Optional, Any
import logging
import time
from .system import System


class SystemGroup:
    """系统分组，用于组织系统执行顺序"""
    
    def __init__(self, name: str, priority: int = 0):
        """
        初始化系统分组
        
        Args:
            name: 分组名称
            priority: 优先级，值越高越先执行
        """
        self.name = name
        self.priority = priority
        self.systems: List[System] = []
        
    def add_system(self, system: System) -> None:
        """
        添加系统到分组
        
        Args:
            system: 系统实例
        """
        if system not in self.systems:
            self.systems.append(system)
            # 按优先级排序
            self.systems.sort(key=lambda s: s.priority, reverse=True)
            
    def remove_system(self, system: System) -> bool:
        """
        从分组中移除系统
        
        Args:
            system: 系统实例
            
        Returns:
            bool: 是否成功移除
        """
        if system in self.systems:
            self.systems.remove(system)
            return True
        return False
        
    def update(self, world, delta_time: float) -> None:
        """
        更新分组中的所有系统
        
        Args:
            world: 游戏世界实例
            delta_time: 帧时间间隔
        """
        for system in self.systems:
            system.update(world, delta_time)
            
    def get_system_count(self) -> int:
        """
        获取分组中的系统数量
        
        Returns:
            int: 系统数量
        """
        return len(self.systems)


class SystemScheduler:
    """系统调度器，管理系统执行顺序和分组"""
    
    # 预定义系统分组
    GROUP_EARLY_UPDATE = "EARLY_UPDATE"     # 早期更新，如输入处理
    GROUP_SIMULATION = "SIMULATION"         # 游戏模拟，如物理、AI
    GROUP_PRESENTATION = "PRESENTATION"     # 表现层，如渲染、音效
    GROUP_LATE_UPDATE = "LATE_UPDATE"       # 晚期更新，如日志、统计
    
    def __init__(self):
        """初始化系统调度器"""
        self._groups: Dict[str, SystemGroup] = {}
        self._systems: Dict[Type, System] = {}
        self._update_order: List[str] = []
        self._logger = logging.getLogger("SystemScheduler")
        
        # 创建默认分组
        self.create_group(self.GROUP_EARLY_UPDATE, 3000)
        self.create_group(self.GROUP_SIMULATION, 2000)
        self.create_group(self.GROUP_PRESENTATION, 1000)
        self.create_group(self.GROUP_LATE_UPDATE, 0)
        
        # 设置默认更新顺序
        self._update_order = [
            self.GROUP_EARLY_UPDATE,
            self.GROUP_SIMULATION,
            self.GROUP_PRESENTATION,
            self.GROUP_LATE_UPDATE
        ]
        
        # 性能监控
        self._enable_profiling = False
        self._system_times: Dict[str, float] = {}
        
    def create_group(self, name: str, priority: int = 0) -> SystemGroup:
        """
        创建系统分组
        
        Args:
            name: 分组名称
            priority: 优先级，值越高越先执行
            
        Returns:
            SystemGroup: 创建的分组
        """
        if name in self._groups:
            self._logger.warning(f"Group {name} already exists, updating priority")
            self._groups[name].priority = priority
            return self._groups[name]
            
        group = SystemGroup(name, priority)
        self._groups[name] = group
        
        # 按优先级重新排序更新顺序
        self._update_order = sorted(
            self._groups.keys(),
            key=lambda name: self._groups[name].priority,
            reverse=True
        )
        
        return group
        
    def add_system(self, system: System, group_name: str = None) -> None:
        """
        添加系统到调度器
        
        Args:
            system: 系统实例
            group_name: 分组名称，为None则添加到SIMULATION分组
        """
        # 如果已经添加过，先移除
        self.remove_system(system)
        
        # 确定分组
        if group_name is None:
            group_name = self.GROUP_SIMULATION
            
        # 确保分组存在
        if group_name not in self._groups:
            self._logger.warning(f"Group {group_name} not found, creating it")
            self.create_group(group_name)
            
        # 添加到分组
        self._groups[group_name].add_system(system)
        # 记录系统类型映射
        self._systems[type(system)] = system
        
    def remove_system(self, system: System) -> bool:
        """
        从调度器中移除系统
        
        Args:
            system: 系统实例
            
        Returns:
            bool: 是否成功移除
        """
        removed = False
        # 从所有分组中移除
        for group in self._groups.values():
            if group.remove_system(system):
                removed = True
                
        # 从类型映射中移除
        if type(system) in self._systems:
            del self._systems[type(system)]
            
        return removed
        
    def get_system(self, system_type: Type) -> Optional[System]:
        """
        获取指定类型的系统
        
        Args:
            system_type: 系统类型
            
        Returns:
            Optional[System]: 系统实例，如果不存在则返回None
        """
        return self._systems.get(system_type)
        
    def update(self, world, delta_time: float) -> None:
        """
        更新所有系统
        
        Args:
            world: 游戏世界实例
            delta_time: 帧时间间隔
        """
        for group_name in self._update_order:
            group = self._groups.get(group_name)
            if not group:
                continue
                
            if self._enable_profiling:
                self._update_group_with_profiling(group, world, delta_time)
            else:
                group.update(world, delta_time)
                
    def _update_group_with_profiling(self, group: SystemGroup, world, delta_time: float) -> None:
        """
        带性能分析的更新分组
        
        Args:
            group: 系统分组
            world: 游戏世界实例
            delta_time: 帧时间间隔
        """
        for system in group.systems:
            start_time = time.time()
            system.update(world, delta_time)
            end_time = time.time()
            
            elapsed = (end_time - start_time) * 1000  # 转换为毫秒
            self._system_times[system.name] = elapsed
            
    def set_update_order(self, group_names: List[str]) -> None:
        """
        设置分组更新顺序
        
        Args:
            group_names: 分组名称列表，按更新顺序排列
        """
        # 验证所有分组都存在
        for name in group_names:
            if name not in self._groups:
                self._logger.warning(f"Group {name} not found in scheduler")
                return
                
        self._update_order = group_names.copy()
        
    def enable_profiling(self, enable: bool = True) -> None:
        """
        启用或禁用性能分析
        
        Args:
            enable: 是否启用
        """
        self._enable_profiling = enable
        if not enable:
            self._system_times.clear()
            
    def get_profiling_data(self) -> Dict[str, float]:
        """
        获取性能分析数据
        
        Returns:
            Dict[str, float]: 系统名称 -> 执行时间(毫秒)
        """
        return self._system_times.copy()
        
    def initialize_all(self, world, event_manager) -> None:
        """
        初始化所有系统
        
        Args:
            world: 游戏世界实例
            event_manager: 事件管理器
        """
        for system in self._systems.values():
            system.initialize(world, event_manager)
            
    def shutdown_all(self) -> None:
        """关闭所有系统"""
        for system in self._systems.values():
            system.shutdown() 