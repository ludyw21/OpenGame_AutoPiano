#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bass 服务（占位）：面向控制器提供底层能力封装。
"""
from __future__ import annotations
from typing import Any, Optional


class BassService:
    def __init__(self, *, playback_service: Optional[Any] = None):
        self.playback_service = playback_service

    def prepare(self) -> bool:
        return True

    def teardown(self):
        pass

    def play(self, data: Any) -> bool:
        return True

    def stop(self):
        pass
