#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guitar 服务（占位）：面向控制器提供底层能力封装。
后续可扩展：
- 音色/效果链加载与参数管理
- 节拍/节奏引擎对接
- 与播放系统（PlaybackService）/时钟的协同
"""
from __future__ import annotations
from typing import Any, Optional


class GuitarService:
    def __init__(self, *, playback_service: Optional[Any] = None):
        self.playback_service = playback_service

    def prepare(self) -> bool:
        """资源预备（占位）。返回是否成功。"""
        return True

    def teardown(self):
        """资源释放（占位）。"""
        pass

    def play(self, data: Any) -> bool:
        """播放/执行一次任务（占位）。返回是否成功。"""
        return True

    def stop(self):
        """停止（占位）。"""
        pass
