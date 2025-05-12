"""
配置管理器模块

提供游戏配置的加载、保存和访问功能
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, List, Set, Union, Callable
from pathlib import Path


class ConfigManager:
    """配置管理器，处理游戏配置的加载、保存和访问"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self._config_dir = config_dir
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._default_configs: Dict[str, Dict[str, Any]] = {}
        self._modified_configs: Set[str] = set()
        self._logger = logging.getLogger("ConfigManager")
        
        # 确保配置目录存在
        os.makedirs(config_dir, exist_ok=True)
        
    def load_config(self, name: str, file_path: Optional[str] = None) -> bool:
        """
        加载配置文件
        
        Args:
            name: 配置名称
            file_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            bool: 是否成功加载
        """
        if file_path is None:
            file_path = os.path.join(self._config_dir, f"{name}.yaml")
            
        if not os.path.exists(file_path):
            self._logger.warning(f"Config file {file_path} not found")
            # 如果有默认配置，使用默认配置
            if name in self._default_configs:
                self._configs[name] = self._default_configs[name].copy()
                return True
            return False
            
        try:
            # 根据文件扩展名选择解析器
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.yaml', '.yml']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._configs[name] = yaml.safe_load(f) or {}
            elif ext == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._configs[name] = json.load(f)
            else:
                self._logger.error(f"Unsupported config file format: {ext}")
                return False
                
            self._logger.info(f"Loaded config {name} from {file_path}")
            return True
        except Exception as e:
            self._logger.error(f"Error loading config {name} from {file_path}: {e}")
            # 如果有默认配置，使用默认配置
            if name in self._default_configs:
                self._configs[name] = self._default_configs[name].copy()
                return True
            return False
            
    def save_config(self, name: str, file_path: Optional[str] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            name: 配置名称
            file_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            bool: 是否成功保存
        """
        if name not in self._configs:
            self._logger.warning(f"Config {name} not found")
            return False
            
        if file_path is None:
            file_path = os.path.join(self._config_dir, f"{name}.yaml")
            
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 根据文件扩展名选择序列化方式
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.yaml', '.yml']:
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self._configs[name], f, default_flow_style=False, sort_keys=False)
            elif ext == '.json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._configs[name], f, indent=2, ensure_ascii=False)
            else:
                self._logger.error(f"Unsupported config file format: {ext}")
                return False
                
            self._logger.info(f"Saved config {name} to {file_path}")
            self._modified_configs.discard(name)
            return True
        except Exception as e:
            self._logger.error(f"Error saving config {name} to {file_path}: {e}")
            return False
            
    def set_default_config(self, name: str, config: Dict[str, Any]) -> None:
        """
        设置默认配置
        
        Args:
            name: 配置名称
            config: 配置数据
        """
        self._default_configs[name] = config.copy()
        
        # 如果配置不存在，使用默认配置
        if name not in self._configs:
            self._configs[name] = config.copy()
            
    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取配置
        
        Args:
            name: 配置名称
            
        Returns:
            Optional[Dict[str, Any]]: 配置数据，如果不存在则返回None
        """
        return self._configs.get(name)
        
    def get_value(self, name: str, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            name: 配置名称
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值，如果配置不存在则返回此值
            
        Returns:
            Any: 配置值
        """
        if name not in self._configs:
            return default
            
        # 处理嵌套键
        keys = key.split('.')
        value = self._configs[name]
        
        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return default
            value = value[k]
            
        return value
        
    def set_value(self, name: str, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            name: 配置名称
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
            
        Returns:
            bool: 是否成功设置
        """
        if name not in self._configs:
            self._configs[name] = {}
            
        # 处理嵌套键
        keys = key.split('.')
        config = self._configs[name]
        
        # 遍历到倒数第二级
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                # 如果中间键不是字典，则替换为字典
                config[k] = {}
                
            config = config[k]
            
        # 设置最后一级的值
        config[keys[-1]] = value
        self._modified_configs.add(name)
        
        return True
        
    def has_config(self, name: str) -> bool:
        """
        检查配置是否存在
        
        Args:
            name: 配置名称
            
        Returns:
            bool: 配置是否存在
        """
        return name in self._configs
        
    def has_value(self, name: str, key: str) -> bool:
        """
        检查配置值是否存在
        
        Args:
            name: 配置名称
            key: 配置键，支持点号分隔的嵌套键
            
        Returns:
            bool: 配置值是否存在
        """
        if name not in self._configs:
            return False
            
        # 处理嵌套键
        keys = key.split('.')
        value = self._configs[name]
        
        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return False
            value = value[k]
            
        return True
        
    def remove_value(self, name: str, key: str) -> bool:
        """
        移除配置值
        
        Args:
            name: 配置名称
            key: 配置键，支持点号分隔的嵌套键
            
        Returns:
            bool: 是否成功移除
        """
        if name not in self._configs:
            return False
            
        # 处理嵌套键
        keys = key.split('.')
        config = self._configs[name]
        
        # 遍历到倒数第二级
        for i, k in enumerate(keys[:-1]):
            if not isinstance(config, dict) or k not in config:
                return False
            config = config[k]
            
        # 移除最后一级的值
        if not isinstance(config, dict) or keys[-1] not in config:
            return False
            
        del config[keys[-1]]
        self._modified_configs.add(name)
        
        return True
        
    def clear_config(self, name: str) -> bool:
        """
        清空配置
        
        Args:
            name: 配置名称
            
        Returns:
            bool: 是否成功清空
        """
        if name not in self._configs:
            return False
            
        self._configs[name] = {}
        self._modified_configs.add(name)
        
        return True
        
    def save_all_modified(self) -> Dict[str, bool]:
        """
        保存所有已修改的配置
        
        Returns:
            Dict[str, bool]: 配置名称 -> 是否成功保存
        """
        results = {}
        for name in self._modified_configs.copy():
            results[name] = self.save_config(name)
            
        return results
        
    def load_all_from_directory(self, directory: Optional[str] = None) -> Dict[str, bool]:
        """
        从目录加载所有配置文件
        
        Args:
            directory: 配置文件目录，如果为None则使用默认目录
            
        Returns:
            Dict[str, bool]: 配置名称 -> 是否成功加载
        """
        if directory is None:
            directory = self._config_dir
            
        if not os.path.exists(directory) or not os.path.isdir(directory):
            self._logger.warning(f"Config directory {directory} not found")
            return {}
            
        results = {}
        for file_name in os.listdir(directory):
            file_path = os.path.join(directory, file_name)
            if os.path.isfile(file_path) and file_name.endswith(('.yaml', '.yml', '.json')):
                name = os.path.splitext(file_name)[0]
                results[name] = self.load_config(name, file_path)
                
        return results
        
    def get_modified_configs(self) -> List[str]:
        """
        获取已修改的配置列表
        
        Returns:
            List[str]: 已修改的配置名称列表
        """
        return list(self._modified_configs)
        
    def is_modified(self, name: str) -> bool:
        """
        检查配置是否已修改
        
        Args:
            name: 配置名称
            
        Returns:
            bool: 配置是否已修改
        """
        return name in self._modified_configs
        
    def reset_to_default(self, name: str) -> bool:
        """
        重置配置为默认值
        
        Args:
            name: 配置名称
            
        Returns:
            bool: 是否成功重置
        """
        if name not in self._default_configs:
            self._logger.warning(f"No default config for {name}")
            return False
            
        self._configs[name] = self._default_configs[name].copy()
        self._modified_configs.add(name)
        
        return True 