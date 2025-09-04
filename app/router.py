#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单路由器：在 UIManager 的左右框架中装载/卸载页面
页面约定：提供 mount(parent_left, parent_right) 和 unmount() 方法
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Callable, Optional, Any


class BasePage:
    def mount(self, left: ttk.Frame, right: ttk.Frame):
        raise NotImplementedError

    def unmount(self):
        pass


class Router:
    def __init__(self, left: ttk.Frame, right: ttk.Frame, set_title: Callable[[str], None] | None = None):
        self.left = left
        self.right = right
        self._set_title = set_title or (lambda s: None)
        self._pages: Dict[str, BasePage] = {}
        self._current_key: Optional[str] = None

    def register(self, key: str, page: BasePage):
        self._pages[key] = page

    def show(self, key: str, *, title: Optional[str] = None):
        if key == self._current_key:
            return
        # 卸载当前
        if self._current_key and self._current_key in self._pages:
            try:
                self._pages[self._current_key].unmount()
            except Exception:
                pass
            # 清空容器
        try:
            for w in list(self.left.winfo_children()):
                w.destroy()
            for w in list(self.right.winfo_children()):
                w.destroy()
        except Exception:
            pass
        # 装载新页面
        self._current_key = key
        page = self._pages.get(key)
        if page:
            page.mount(self.left, self.right)
        if title is not None:
            self._set_title(title)

    def current(self) -> Optional[str]:
        return self._current_key
