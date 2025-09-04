#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drums 控制器（占位）：负责协调架子鼓页面与后端服务。
"""
from __future__ import annotations
from typing import Any, Optional, Dict

try:
    from meowauto.app.services.playback_service import PlaybackService
except Exception:
    PlaybackService = None  # 运行期兜底
try:
    from meowauto.playback.keymaps_ext.drums import DRUMS_KEYMAP
except Exception:
    DRUMS_KEYMAP = {}


class DrumsController:
    """架子鼓控制器：负责页面到播放服务的桥接。"""

    def __init__(self, service: Optional[Any] = None):
        self.service: Any = service or (PlaybackService() if PlaybackService else None)
        self.settings: Dict[str, Any] = {
            'tempo': 1.0,
            'key_mapping': dict(DRUMS_KEYMAP),  # 可被 UI 覆盖
            # 预留：量化/最短持续/连击合并等
        }

    # 兼容旧接口
    def start(self):
        return False

    def start_from_file(self, midi_path: str, *, tempo: Optional[float] = None, key_mapping: Optional[Dict[str, str]] = None) -> bool:
        if not midi_path:
            return False
        if not self.service:
            return False
        try:
            # 确保播放器初始化
            if hasattr(self.service, 'init_players'):
                self.service.init_players()
            ap = getattr(self.service, 'auto_player', None)
            if not ap or not hasattr(ap, 'start_auto_play_midi_drums'):
                return False
            t = float(tempo) if tempo is not None else float(self.settings.get('tempo', 1.0))
            km = key_mapping or self.settings.get('key_mapping') or DRUMS_KEYMAP
            return bool(ap.start_auto_play_midi_drums(midi_path, tempo=t, key_mapping=km))
        except Exception:
            return False

    def stop(self) -> None:
        if not self.service:
            return
        try:
            if hasattr(self.service, 'stop_auto_only'):
                self.service.stop_auto_only()
        except Exception:
            pass

    def pause(self) -> None:
        if not self.service:
            return
        try:
            if hasattr(self.service, 'pause_auto_only'):
                self.service.pause_auto_only()
        except Exception:
            pass

    def resume(self) -> None:
        if not self.service:
            return
        try:
            if hasattr(self.service, 'resume_auto_only'):
                self.service.resume_auto_only()
        except Exception:
            pass

    def apply_settings(self, settings: dict):
        if not isinstance(settings, dict):
            return
        try:
            if 'tempo' in settings:
                self.settings['tempo'] = float(settings['tempo'])
        except Exception:
            pass
        try:
            km = settings.get('key_mapping')
            if isinstance(km, dict) and km:
                self.settings['key_mapping'] = km
        except Exception:
            pass
