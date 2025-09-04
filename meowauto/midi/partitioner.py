# -*- coding: utf-8 -*-
"""
MIDI 分部器（占位模块）

目标：
- 为鼓/贝斯/主旋律等分部解析提供统一入口与策略扩展点
- 保持“只向内依赖”，不直接依赖 UI 层

后续计划：
- 实现 StrategyDrums / StrategyBass，对事件与通道进行启发式分拣
- 提供组合策略，支持多角色（roles）输出给自动演奏层
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple, Any


@dataclass
class PartSection:
    """分部结果的数据结构。
    notes: 统一的事件结构列表（占位：任意结构，保持与现有分析结果兼容）
    meta:  可携带统计/置信度/来源策略等信息
    """
    name: str
    notes: List[Dict[str, Any]]
    meta: Dict[str, Any]


class Partitioner(Protocol):
    """分部器协议：输入原始 MIDI 或标准化事件，输出多分部结果。"""
    def split(self, events: List[Dict[str, Any]] | Any, *, tempo: float = 1.0) -> Dict[str, PartSection]:
        ...


class StrategyDrums:
    """鼓分部策略（占位）。
    设计思路：
    - 基于通道/打击乐音色（channel 10 或 percussion program）
    - 再结合音高集合/密度节奏特征进行筛选
    """
    def extract(self, events: List[Dict[str, Any]] | Any) -> PartSection:
        if not isinstance(events, list):
            return PartSection(name="drums", notes=[], meta={"strategy": "drums", "status": "invalid_input"})
        drums: List[Dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            et = ev.get("type")  # note_on/note_off 等
            if et not in ("note_on", "note_off"):
                continue
            ch = ev.get("channel")
            prog = ev.get("program")  # GM program number（0-127），鼓一般不依赖 program，但有时会标记为打击乐套件
            is_drum_flag = bool(ev.get("is_drum", False))
            pitch = ev.get("note")
            name = str(ev.get("instrument_name", "")).lower()

            # 规则：
            # 1) channel == 9 （MIDI 第10通道）
            # 2) 显式 is_drum 标志
            # 3) 名称包含 percussion/drum
            # 4) 对 pitch 使用典型鼓区（35-81，含底鼓到吊镲）作为兜底特征
            cond_channel = (ch == 9)
            cond_name = ("drum" in name or "percussion" in name)
            cond_prog = (prog in (112, 113, 114, 115))  # 部分工程约定：映射到打击乐套件，宽松处理
            cond_pitch = isinstance(pitch, int) and 35 <= pitch <= 81

            if cond_channel or is_drum_flag or cond_name or cond_prog or cond_pitch:
                drums.append(ev)

        return PartSection(
            name="drums",
            notes=drums,
            meta={
                "strategy": "drums",
                "count": len(drums),
                "hint": "channel==10/is_drum/name_contains/pitch_range",
            },
        )


class StrategyBass:
    """贝斯分部策略（占位）。
    设计思路：
    - 低音区音高分布与节奏稀疏度
    - 与和弦根音的贴合度（后续可接 chord 识别）
    """
    def extract(self, events: List[Dict[str, Any]] | Any) -> PartSection:
        if not isinstance(events, list):
            return PartSection(name="bass", notes=[], meta={"strategy": "bass", "status": "invalid_input"})
        bass: List[Dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            et = ev.get("type")
            if et not in ("note_on", "note_off"):
                continue
            ch = ev.get("channel")
            prog = ev.get("program")  # GM 32-39 为 Bass 类音色
            pitch = ev.get("note")
            name = str(ev.get("instrument_name", "")).lower()

            # 规则（宽松）：
            # - program 在 32..39
            # - 名称包含 "bass"
            # - 低音区音高：E1(28)~E3(52) 作为主范围，必要时放宽到 28..60
            cond_prog = isinstance(prog, int) and 32 <= prog <= 39
            cond_name = "bass" in name
            cond_pitch = isinstance(pitch, int) and 28 <= pitch <= 60

            if cond_prog or cond_name or cond_pitch:
                bass.append(ev)

        # 简单稀疏化（可选）：去掉极密集高音触发，当前仅占位，不做节奏分析
        return PartSection(
            name="bass",
            notes=bass,
            meta={
                "strategy": "bass",
                "count": len(bass),
                "hint": "program/name_contains/pitch_low_range",
            },
        )


class DefaultPartitioner:
    """默认分部器：按策略组合输出占位分部。"""
    def __init__(self, *, use_drums: bool = True, use_bass: bool = True):
        self.drums = StrategyDrums() if use_drums else None
        self.bass = StrategyBass() if use_bass else None

    def split(self, events: List[Dict[str, Any]] | Any, *, tempo: float = 1.0) -> Dict[str, PartSection]:
        parts: Dict[str, PartSection] = {}
        if self.drums:
            parts["drums"] = self.drums.extract(events)
        if self.bass:
            parts["bass"] = self.bass.extract(events)
        # TODO: 未来可加入 lead/chords 等更多角色
        return parts


class TrackChannelPartitioner:
    """按 轨(track) / 通道(channel) / 音色(program) / 乐器名(instrument_name) 分组的分部器。
    用途：
    - 为后续“单一乐器 MIDI”与“大合奏”准备可直接路由的粒度。
    - 不作乐器角色推断，只做结构化分离与标注。
    事件兼容：缺失字段时做安全兜底（track=-1, channel=-1, program=None）。
    """
    def __init__(self, *, include_meta: bool = True):
        self.include_meta = include_meta

    def _group_key(self, ev: Dict[str, Any]) -> Tuple[int, int, Any, str]:
        t = ev.get("track")
        ch = ev.get("channel")
        prog = ev.get("program")
        name = str(ev.get("instrument_name", ""))
        # 兜底
        try:
            t = int(t) if t is not None else -1
        except Exception:
            t = -1
        try:
            ch = int(ch) if ch is not None else -1
        except Exception:
            ch = -1
        return (t, ch, prog, name)

    def split(self, events: List[Dict[str, Any]] | Any, *, tempo: float = 1.0) -> Dict[str, PartSection]:
        if not isinstance(events, list):
            return {}
        buckets: Dict[Tuple[int, int, Any, str], List[Dict[str, Any]]] = {}
        for ev in events:
            if not isinstance(ev, dict):
                continue
            et = ev.get("type")
            if et not in ("note_on", "note_off"):
                # 仅对音符事件分组，其它事件暂忽略
                continue
            key = self._group_key(ev)
            buckets.setdefault(key, []).append(ev)

        parts: Dict[str, PartSection] = {}
        for (t, ch, prog, name), evs in buckets.items():
            part_name = f"track{t}_ch{ch}_prog{prog if prog is not None else 'NA'}"
            if name:
                part_name += f"_{name}"
            meta = {
                "strategy": "track_channel",
                "track": t,
                "channel": ch,
                "program": prog,
                "instrument_name": name,
                "count": len(evs),
            } if self.include_meta else {}
            parts[part_name] = PartSection(name=part_name, notes=evs, meta=meta)
        return parts


__all__ = [
    "PartSection",
    "Partitioner",
    "StrategyDrums",
    "StrategyBass",
    "DefaultPartitioner",
    "TrackChannelPartitioner",
]
