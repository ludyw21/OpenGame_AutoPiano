#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guitar 控制器（占位）：负责协调吉他页面与后端服务。
后续实现：谱面解析、演奏调度、效果参数、与播放服务的交互等。
"""
from __future__ import annotations
from typing import Any, Optional


class GuitarController:
    def __init__(self, service: Optional[Any] = None):
        self.service = service

    def start(self):
        """开始演奏/任务（占位）。"""
        pass

    def stop(self):
        """停止演奏/任务（占位）。"""
        pass

    def apply_settings(self, settings: dict):
        """应用配置（占位）。"""
        pass
