#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件总线模块
提供模块间通信的事件发布/订阅机制
"""

import threading
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """事件对象"""
    name: str
    data: Any
    timestamp: datetime
    source: str


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._lock = threading.RLock()
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> bool:
        """订阅事件"""
        try:
            with self._lock:
                if event_name not in self._subscribers:
                    self._subscribers[event_name] = []
                self._subscribers[event_name].append(callback)
                return True
        except Exception:
            return False
    
    def unsubscribe(self, event_name: str, callback: Callable[[Event], None]) -> bool:
        """取消订阅"""
        try:
            with self._lock:
                if event_name in self._subscribers:
                    if callback in self._subscribers[event_name]:
                        self._subscribers[event_name].remove(callback)
                        return True
                return False
        except Exception:
            return False
    
    def publish(self, event_name: str, data: Any = None, source: str = "system") -> bool:
        """发布事件"""
        try:
            event = Event(
                name=event_name,
                data=data,
                timestamp=datetime.now(),
                source=source
            )
            
            # 记录事件历史
            with self._lock:
                self._event_history.append(event)
                if len(self._event_history) > self._max_history:
                    self._event_history.pop(0)
            
            # 异步通知订阅者
            if event_name in self._subscribers:
                callbacks = self._subscribers[event_name].copy()
                for callback in callbacks:
                    try:
                        # 在新线程中执行回调，避免阻塞
                        threading.Thread(
                            target=self._safe_callback,
                            args=(callback, event),
                            daemon=True
                        ).start()
                    except Exception:
                        continue
            
            return True
        except Exception:
            return False
    
    def _safe_callback(self, callback: Callable, event: Event):
        """安全执行回调函数"""
        try:
            callback(event)
        except Exception:
            pass
    
    def get_event_history(self, event_name: Optional[str] = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        with self._lock:
            if event_name is None:
                return self._event_history[-limit:]
            else:
                filtered = [e for e in self._event_history if e.name == event_name]
                return filtered[-limit:]
    
    def clear_history(self):
        """清空事件历史"""
        with self._lock:
            self._event_history.clear()
    
    def get_subscriber_count(self, event_name: str) -> int:
        """获取指定事件的订阅者数量"""
        with self._lock:
            return len(self._subscribers.get(event_name, []))
    
    def list_events(self) -> List[str]:
        """列出所有已注册的事件"""
        with self._lock:
            return list(self._subscribers.keys())


# 全局事件总线实例
event_bus = EventBus()

# 常用事件名称常量
class Events:
    """事件名称常量"""
    # 播放相关
    PLAYBACK_START = "playback.start"
    PLAYBACK_STOP = "playback.stop"
    PLAYBACK_PAUSE = "playback.pause"
    PLAYBACK_RESUME = "playback.resume"
    PLAYBACK_PROGRESS = "playback.progress"
    
    # 文件相关
    FILE_LOADED = "file.loaded"
    FILE_CONVERTED = "file.converted"
    FILE_ERROR = "file.error"
    
    # UI相关
    UI_THEME_CHANGED = "ui.theme_changed"
    UI_LAYOUT_CHANGED = "ui.layout_changed"
    UI_PAGE_CHANGED = "ui.page_changed"
    
    # 系统相关
    SYSTEM_READY = "system.ready"
    SYSTEM_ERROR = "system.error"
    SYSTEM_SHUTDOWN = "system.shutdown"
    
    # 配置相关
    CONFIG_LOADED = "config.loaded"
    CONFIG_SAVED = "config.saved"
    CONFIG_CHANGED = "config.changed" 