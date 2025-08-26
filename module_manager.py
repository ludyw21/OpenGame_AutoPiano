#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块管理器
负责动态加载、初始化和依赖注入管理
"""

import importlib
import sys
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    module: Any
    instance: Any
    dependencies: List[str]
    status: str  # 'loaded', 'error', 'unloaded'


class ModuleManager:
    """模块管理器"""
    
    def __init__(self, logger=None, event_bus=None):
        self.logger = logger
        self.event_bus = event_bus
        self.modules: Dict[str, ModuleInfo] = {}
        self.module_config = {
            'core': {
                'path': 'meowauto.core',
                'classes': ['ConfigManager', 'Logger'],
                'dependencies': [],
                'singleton': True
            },
            'playback': {
                'path': 'meowauto.playback',
                'classes': ['AutoPlayer', 'MidiPlayer'],
                'dependencies': ['core'],
                'singleton': False
            },
            # UI模块需要特定参数，不在这里自动加载
            # 'ui': {
            #     'path': 'meowauto.ui',
            #     'classes': ['AppearanceManager', 'Sidebar', 'PlaylistView', 'LogView'],
            #     'dependencies': ['core'],
            #     'singleton': False
            # },
            'utils': {
                'path': 'meowauto.utils',
                'classes': ['CountdownTimer', 'ScoreUtils', 'MidiUtils'],
                'dependencies': ['core'],
                'singleton': False
            }
        }
    
    def load_module(self, module_name: str) -> bool:
        """加载指定模块"""
        try:
            if module_name not in self.module_config:
                self._log_error(f"未知模块: {module_name}")
                return False
            
            # 检查依赖
            if not self._check_dependencies(module_name):
                return False
            
            config = self.module_config[module_name]
            module_path = config['path']
            
            # 导入模块
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                self._log_error(f"导入模块失败 {module_path}: {e}")
                return False
            
            # 创建模块实例
            instances = {}
            for class_name in config['classes']:
                try:
                    if hasattr(module, class_name):
                        class_obj = getattr(module, class_name)
                        
                        # 获取类的构造函数参数
                        import inspect
                        try:
                            sig = inspect.signature(class_obj.__init__)
                            required_params = [name for name, param in sig.parameters.items() 
                                             if param.default == inspect.Parameter.empty and name != 'self']
                            
                            # 跳过需要特殊参数的类
                            if class_name == 'CountdownTimer' and len(required_params) >= 2:
                                self.logger.log(f"跳过 {class_name}: 需要 {len(required_params)} 个必需参数", "INFO")
                                continue
                            
                            # 尝试创建实例
                            if required_params:
                                # 有必需参数，尝试提供默认值
                                if class_name == 'AutoPlayer' and 'logger' in required_params:
                                    # AutoPlayer 需要 Logger 参数
                                    logger_instance = self.get_module_instance('core', 'Logger')
                                    if logger_instance:
                                        instance = class_obj(logger_instance)
                                    else:
                                        self.logger.log(f"无法创建 {class_name}: Logger 不可用", "WARNING")
                                        continue
                                elif class_name == 'MidiPlayer' and 'logger' in required_params:
                                    # MidiPlayer 需要 Logger 参数
                                    logger_instance = self.get_module_instance('core', 'Logger')
                                    if logger_instance:
                                        instance = class_obj(logger_instance)
                                    else:
                                        self.logger.log(f"无法创建 {class_name}: Logger 不可用", "WARNING")
                                        continue
                                else:
                                    # 其他需要参数的类，跳过
                                    self.logger.log(f"跳过 {class_name}: 需要参数 {required_params}", "INFO")
                                    continue
                            else:
                                # 无必需参数，直接创建
                                instance = class_obj()
                            
                            instances[class_name] = instance
                            self.logger.log(f"成功创建 {class_name} 实例", "SUCCESS")
                        except Exception as e:
                            self.logger.log(f"创建 {class_name} 实例失败: {e}", "WARNING")
                            continue
                    else:
                        self._log_error(f"模块 {module_path} 中未找到类 {class_name}")
                        continue
                except Exception as e:
                    self._log_error(f"创建实例失败 {class_name}: {e}")
                    continue
            
            if not instances:
                self._log_error(f"模块 {module_name} 没有成功创建任何实例")
                return False
            
            # 注册模块
            module_info = ModuleInfo(
                name=module_name,
                module=module,
                instance=instances,
                dependencies=config['dependencies'],
                status='loaded'
            )
            
            self.modules[module_name] = module_info
            
            # 发布事件
            if self.event_bus:
                self.event_bus.publish(
                    'module.loaded',
                    {'module_name': module_name, 'instances': list(instances.keys())},
                    'ModuleManager'
                )
            
            self._log_info(f"模块 {module_name} 加载完成: {list(instances.keys())}")
            return True
            
        except Exception as e:
            self._log_error(f"加载模块 {module_name} 失败: {e}")
            return False
    
    def load_all_modules(self) -> Dict[str, bool]:
        """加载所有模块"""
        results = {}
        
        # 按依赖顺序加载
        load_order = self._get_load_order()
        
        for module_name in load_order:
            success = self.load_module(module_name)
            results[module_name] = success
            
            if not success:
                self._log_error(f"模块 {module_name} 加载失败，停止加载后续模块")
                break
        
        return results
    
    def get_module(self, module_name: str) -> Optional[Any]:
        """获取模块实例"""
        if module_name in self.modules:
            return self.modules[module_name].instance
        return None
    
    def get_class_instance(self, module_name: str, class_name: str) -> Optional[Any]:
        """获取指定模块中指定类的实例"""
        module_info = self.modules.get(module_name)
        if module_info and isinstance(module_info.instance, dict):
            return module_info.instance.get(class_name)
        return None
    
    def unload_module(self, module_name: str) -> bool:
        """卸载模块"""
        try:
            if module_name in self.modules:
                module_info = self.modules[module_name]
                
                # 检查是否有其他模块依赖此模块
                for name, info in self.modules.items():
                    if module_name in info.dependencies:
                        self._log_error(f"无法卸载模块 {module_name}，模块 {name} 依赖它")
                        return False
                
                # 卸载模块
                del self.modules[module_name]
                
                # 发布事件
                if self.event_bus:
                    self.event_bus.publish(
                        'module.unloaded',
                        {'module_name': module_name},
                        'ModuleManager'
                    )
                
                self._log_info(f"模块 {module_name} 已卸载")
                return True
            
            return False
            
        except Exception as e:
            self._log_error(f"卸载模块 {module_name} 失败: {e}")
            return False
    
    def reload_module(self, module_name: str) -> bool:
        """重新加载模块"""
        try:
            if self.unload_module(module_name):
                return self.load_module(module_name)
            return False
        except Exception as e:
            self._log_error(f"重新加载模块 {module_name} 失败: {e}")
            return False
    
    def get_module_status(self) -> Dict[str, str]:
        """获取所有模块状态"""
        return {name: info.status for name, info in self.modules.items()}
    
    def get_module_instance(self, module_name: str, class_name: str = None) -> Any:
        """获取模块实例"""
        try:
            if module_name not in self.modules:
                self._log_error(f"模块 {module_name} 未加载")
                return None
            
            module_info = self.modules[module_name]
            if module_info.status != 'loaded':
                self._log_error(f"模块 {module_name} 状态异常: {module_info.status}")
                return None
            
            if class_name:
                # 获取指定类的实例
                if class_name in module_info.instance:
                    return module_info.instance[class_name]
                else:
                    self._log_error(f"模块 {module_name} 中未找到类 {class_name}")
                    return None
            else:
                # 返回整个模块的实例字典
                return module_info.instance
                
        except Exception as e:
            self._log_error(f"获取模块实例失败 {module_name}: {e}")
            return None
    
    def get_loaded_modules(self) -> List[str]:
        """获取已加载的模块列表"""
        return [name for name, info in self.modules.items() if info.status == 'loaded']
    
    def get_module_status(self, module_name: str) -> Optional[str]:
        """获取模块状态"""
        if module_name in self.modules:
            return self.modules[module_name].status
        return None
    
    def _check_dependencies(self, module_name: str) -> bool:
        """检查模块依赖"""
        config = self.module_config[module_name]
        dependencies = config.get('dependencies', [])
        
        for dep in dependencies:
            if dep not in self.modules:
                self._log_error(f"模块 {module_name} 依赖模块 {dep} 未加载")
                return False
        
        return True
    
    def _get_load_order(self) -> List[str]:
        """获取模块加载顺序（拓扑排序）"""
        # 简单的依赖排序
        order = []
        visited = set()
        
        def visit(module_name):
            if module_name in visited:
                return
            if module_name in order:
                return
            
            config = self.module_config[module_name]
            for dep in config.get('dependencies', []):
                visit(dep)
            
            order.append(module_name)
            visited.add(module_name)
        
        for module_name in self.module_config:
            visit(module_name)
        
        return order
    
    def _log_info(self, message: str):
        """记录信息日志"""
        if self.logger:
            try:
                self.logger.log(message, "INFO")
            except:
                pass
        else:
            print(f"[INFO] {message}")
    
    def _log_warning(self, message: str):
        """记录警告日志"""
        if self.logger:
            try:
                self.logger.log(message, "WARNING")
            except:
                pass
        else:
            print(f"[WARNING] {message}")
    
    def _log_error(self, message: str):
        """记录错误日志"""
        if self.logger:
            try:
                self.logger.log(message, "ERROR")
            except:
                pass
        else:
            print(f"[ERROR] {message}")
    
    def _log_success(self, message: str):
        """记录成功日志"""
        if self.logger:
            try:
                self.logger.log(message, "SUCCESS")
            except:
                pass
        else:
            print(f"[SUCCESS] {message}")
    
    def inject_dependencies(self, target_instance: Any, module_name: str):
        """向目标实例注入依赖"""
        try:
            module_info = self.modules.get(module_name)
            if not module_info:
                return False
            
            # 注入模块实例
            if hasattr(target_instance, 'inject_module'):
                target_instance.inject_module(module_name, module_info.instance)
            
            # 注入事件总线
            if hasattr(target_instance, 'set_event_bus') and self.event_bus:
                target_instance.set_event_bus(self.event_bus)
            
            return True
            
        except Exception as e:
            self._log_error(f"注入依赖失败: {e}")
            return False 

    def _get_logger_instance(self):
        """获取Logger实例"""
        try:
            # 首先尝试从已加载的core模块获取
            core_module = self.modules.get('core')
            if core_module and isinstance(core_module.instance, dict):
                logger = core_module.instance.get('Logger')
                if logger:
                    return logger
            
            # 如果core模块未加载，尝试直接导入
            try:
                from meowauto.core import Logger
                return Logger()
            except ImportError:
                return None
        except Exception:
            return None
    
    def _get_config_instance(self):
        """获取ConfigManager实例"""
        try:
            # 首先尝试从已加载的core模块获取
            core_module = self.modules.get('core')
            if core_module and isinstance(core_module.instance, dict):
                config = core_module.instance.get('ConfigManager')
                if config:
                    return config
            
            # 如果core模块未加载，尝试直接导入
            try:
                from meowauto.core import ConfigManager
                return ConfigManager()
            except ImportError:
                return None
        except Exception:
            return None 

    def _create_instance(self, module_name: str, class_name: str, module_dict: dict) -> Any:
        """创建模块实例"""
        try:
            if class_name in module_dict:
                class_obj = module_dict[class_name]
                
                # 跳过需要特殊参数的类
                if class_name == 'CountdownTimer':
                    self._log_info(f"跳过 {class_name}: 需要 root 和 seconds 参数")
                    return None
                
                # 尝试创建实例
                try:
                    if class_name == 'Logger':
                        instance = class_obj()
                    elif class_name == 'ConfigManager':
                        instance = class_obj()
                    elif class_name == 'KeySender':
                        instance = class_obj()
                    elif class_name == 'AutoPlayer':
                        # AutoPlayer 需要 Logger 参数
                        logger_instance = self.get_module_instance('core', 'Logger')
                        if logger_instance:
                            instance = class_obj(logger_instance)
                        else:
                            self._log_warning(f"无法创建 {class_name}: Logger 不可用")
                            return None
                    elif class_name == 'MidiPlayer':
                        # MidiPlayer 需要 Logger 参数
                        logger_instance = self.get_module_instance('core', 'Logger')
                        if logger_instance:
                            instance = class_obj(logger_instance)
                        else:
                            self._log_warning(f"无法创建 {class_name}: Logger 不可用")
                            return None
                    else:
                        # 尝试无参数实例化
                        instance = class_obj()
                    
                    self._log_success(f"成功创建 {class_name} 实例")
                    return instance
                    
                except Exception as e:
                    self._log_warning(f"创建 {class_name} 实例失败: {e}")
                    return None
            else:
                self._log_warning(f"类 {class_name} 在模块 {module_name} 中不存在")
                return None
                
        except Exception as e:
            self._log_error(f"创建实例失败 {class_name}: {e}")
            return None 