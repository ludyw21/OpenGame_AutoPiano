#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
乐器页面包：提供四大板块（电子琴、吉他、贝斯、架子鼓）的页面基类与占位实现。
仅电子琴页面连接现有完整功能，其余页面为占位，后续逐步实现。
"""
from __future__ import annotations
from typing import Protocol

try:
    # 复用 Router 的 BasePage 约定（若可用）
    from .. import BasePage  # type: ignore
except Exception:
    # 兜底协议，避免循环依赖或导入失败影响其他模块
    class BasePage(Protocol):  # type: ignore
        def mount(self, left, right): ...
        def unmount(self): ...
