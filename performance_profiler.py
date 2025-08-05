"""
性能分析工具 - 找出真正的性能瓶颈
Performance profiler to identify real bottlenecks
"""

import time
import pygame
from typing import Dict, List
from collections import defaultdict

class PerformanceProfiler:
    def __init__(self):
        self.frame_times: List[float] = []
        self.system_times: Dict[str, List[float]] = defaultdict(list)
        self.last_frame_time = time.time()
        self.fps_samples = []
        
    def start_frame(self):
        """开始新帧的计时"""
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        self.frame_times.append(frame_time)
        self.last_frame_time = current_time
        
        # 计算FPS
        if frame_time > 0:
            fps = 1.0 / frame_time
            self.fps_samples.append(fps)
        
        # 保持最近100帧的数据
        if len(self.frame_times) > 100:
            self.frame_times.pop(0)
        if len(self.fps_samples) > 100:
            self.fps_samples.pop(0)
    
    def time_system(self, system_name: str):
        """返回一个上下文管理器来计时特定系统"""
        return SystemTimer(self, system_name)
    
    def add_system_time(self, system_name: str, elapsed_time: float):
        """添加系统执行时间"""
        self.system_times[system_name].append(elapsed_time)
        if len(self.system_times[system_name]) > 100:
            self.system_times[system_name].pop(0)
    
    def get_stats(self) -> Dict:
        """获取性能统计"""
        if not self.frame_times:
            return {}
        
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        avg_fps = sum(self.fps_samples) / len(self.fps_samples) if self.fps_samples else 0
        
        stats = {
            'avg_fps': avg_fps,
            'avg_frame_time_ms': avg_frame_time * 1000,
            'min_fps': min(self.fps_samples) if self.fps_samples else 0,
            'max_fps': max(self.fps_samples) if self.fps_samples else 0,
            'systems': {}
        }
        
        for system_name, times in self.system_times.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                stats['systems'][system_name] = {
                    'avg_time_ms': avg_time * 1000,
                    'max_time_ms': max_time * 1000,
                    'percentage': (avg_time / avg_frame_time * 100) if avg_frame_time > 0 else 0
                }
        
        return stats
    
    def print_stats(self):
        """打印性能统计"""
        stats = self.get_stats()
        if not stats:
            return
            
        print("\n" + "="*60)
        print("性能统计 Performance Stats")
        print("="*60)
        print(f"平均FPS: {stats['avg_fps']:.1f}")
        print(f"最低FPS: {stats['min_fps']:.1f}")
        print(f"最高FPS: {stats['max_fps']:.1f}")
        print(f"平均帧时间: {stats['avg_frame_time_ms']:.2f}ms")
        print("\n系统耗时占比:")
        
        # 按耗时排序
        system_stats = sorted(
            stats['systems'].items(), 
            key=lambda x: x[1]['avg_time_ms'], 
            reverse=True
        )
        
        for system_name, system_data in system_stats:
            print(f"  {system_name:25} {system_data['avg_time_ms']:6.2f}ms ({system_data['percentage']:5.1f}%)")

class SystemTimer:
    def __init__(self, profiler: PerformanceProfiler, system_name: str):
        self.profiler = profiler
        self.system_name = system_name
        self.start_time = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        self.profiler.add_system_time(self.system_name, elapsed)

# 全局分析器
profiler = PerformanceProfiler() 