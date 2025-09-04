# -*- coding: utf-8 -*-
"""
统一日志占位模块：后续可在此定义标准 Logger 接口并桥接到现有 meowauto.core.Logger。
当前作为占位，便于后续替换与注入。
"""
from typing import Any
try:
    from meowauto.core import Logger as CoreLogger  # 兼容现有
except Exception:  # 运行期容错
    CoreLogger = None  # type: ignore

class LoggerProxy:
    def __init__(self, impl: Any | None = None):
        self._impl = impl or (CoreLogger() if CoreLogger else None)
    def log(self, msg: str, level: str = "INFO") -> None:
        if self._impl and hasattr(self._impl, 'log'):
            self._impl.log(msg, level)
        else:
            print(f"[{level}] {msg}")
