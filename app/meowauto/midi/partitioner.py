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
    """鼓分部策略。
    严格模式（默认）：仅以 GM 第10通道（0-based 为 9）或显式 is_drum 标志识别，避免过度包含。
    宽松模式（loose=True）：额外启用名称/Program/音高区间等启发式，适用于数据缺失或非标准工程。
    """
    def __init__(self, *, loose: bool = False):
        self.loose = loose

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

            # 严格规则优先：
            cond_channel = (ch == 9)  # 第10通道
            if cond_channel or is_drum_flag:
                drums.append(ev)
                continue
            # 宽松扩展（可选）：
            if self.loose:
                cond_name = ("drum" in name or "percussion" in name)
                cond_prog = (isinstance(prog, int) and prog in (112, 113, 114, 115))
                cond_pitch = isinstance(pitch, int) and 35 <= pitch <= 81
                if cond_name or cond_prog or cond_pitch:
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
    def __init__(self, *, use_drums: bool = True, use_bass: bool = True, use_guitar: bool = False, use_keys: bool = False):
        self.drums = StrategyDrums() if use_drums else None
        self.bass = StrategyBass() if use_bass else None
        # 可选：吉他与键盘识别（默认关闭，避免与历史行为产生多余分部）
        self.guitar = StrategyGuitar() if use_guitar else None
        self.keys = StrategyKeys() if use_keys else None

    def split(self, events: List[Dict[str, Any]] | Any, *, tempo: float = 1.0) -> Dict[str, PartSection]:
        parts: Dict[str, PartSection] = {}
        if self.drums:
            parts["drums"] = self.drums.extract(events)
        if self.bass:
            parts["bass"] = self.bass.extract(events)
        if self.guitar:
            g = self.guitar.extract(events)
            if g.notes:
                parts["guitar"] = g
        if self.keys:
            k = self.keys.extract(events)
            if k.notes:
                parts["keys"] = k
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


# —— 新增：乐器识别策略 ——
class StrategyGuitar:
    """吉他分部策略。
    依据：
    - GM Program 24..31（0-based）：Guitars
    - 名称包含 guitar
    - pitch 典型分布（E2≈40 到 B5≈83），并排除 channel 10（打击乐）
    """
    def extract(self, events: List[Dict[str, Any]] | Any) -> PartSection:
        if not isinstance(events, list):
            return PartSection(name="guitar", notes=[], meta={"strategy": "guitar", "status": "invalid_input"})
        out: List[Dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("type") not in ("note_on", "note_off"):
                continue
            ch = ev.get("channel")
            prog = ev.get("program")
            name = str(ev.get("instrument_name", "")).lower()
            pitch = ev.get("note")
            if ch == 9:
                continue
            cond_prog = isinstance(prog, int) and 24 <= prog <= 31
            cond_name = "guitar" in name
            cond_pitch = isinstance(pitch, int) and 40 <= pitch <= 83
            if cond_prog or cond_name or cond_pitch:
                out.append(ev)
        return PartSection(
            name="guitar",
            notes=out,
            meta={
                "strategy": "guitar",
                "count": len(out),
                "hint": "program24-31/name_contains/pitch_40_83",
            },
        )


class StrategyKeys:
    """键盘/电子琴分部策略。
    依据：
    - GM Program 0..7（Acoustic Pianos）、4..5（Electric Piano1/2），以及 6..7（Harpsichord/Clav）
    - 名称包含 piano/epiano/keyboard/keys
    - pitch 分布宽（A0≈21 到 C7≈96），排除 channel 10
    说明：键盘类泛化，既涵盖钢琴也涵盖电子琴，后续可按需拆分。
    """
    def extract(self, events: List[Dict[str, Any]] | Any) -> PartSection:
        if not isinstance(events, list):
            return PartSection(name="keys", notes=[], meta={"strategy": "keys", "status": "invalid_input"})
        out: List[Dict[str, Any]] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("type") not in ("note_on", "note_off"):
                continue
            ch = ev.get("channel")
            prog = ev.get("program")
            name = str(ev.get("instrument_name", "")).lower()
            pitch = ev.get("note")
            if ch == 9:
                continue
            cond_prog = isinstance(prog, int) and (0 <= prog <= 7)
            cond_name = ("piano" in name) or ("epiano" in name) or ("keyboard" in name) or ("keys" in name)
            cond_pitch = isinstance(pitch, int) and 21 <= pitch <= 96
            if cond_prog or cond_name or cond_pitch:
                out.append(ev)
        return PartSection(
            name="keys",
            notes=out,
            meta={
                "strategy": "keys",
                "count": len(out),
                "hint": "program0-7/name_contains/pitch_21_96",
            },
        )


class CombinedInstrumentPartitioner:
    """组合乐器识别分部器：输出 drums/bass/guitar/keys 等可用分部。"""
    def __init__(self, *, include_drums: bool = True, include_bass: bool = True, include_guitar: bool = True, include_keys: bool = True, drums_loose: bool = False):
        # 智能聚类用于 UI 自动选择时，鼓默认严格识别，避免误将非鼓事件归入鼓
        self._drums = StrategyDrums(loose=drums_loose) if include_drums else None
        self._bass = StrategyBass() if include_bass else None
        self._guitar = StrategyGuitar() if include_guitar else None
        self._keys = StrategyKeys() if include_keys else None

    def split(self, events: List[Dict[str, Any]] | Any, *, tempo: float = 1.0) -> Dict[str, PartSection]:
        parts: Dict[str, PartSection] = {}
        if self._drums:
            d = self._drums.extract(events)
            if d.notes:
                parts["drums"] = d
        if self._bass:
            b = self._bass.extract(events)
            if b.notes:
                parts["bass"] = b
        if self._guitar:
            g = self._guitar.extract(events)
            if g.notes:
                parts["guitar"] = g
        if self._keys:
            k = self._keys.extract(events)
            if k.notes:
                parts["keys"] = k
        return parts
__all__ = [
    "PartSection",
    "Partitioner",
    "StrategyDrums",
    "StrategyBass",
    "DefaultPartitioner",
    "TrackChannelPartitioner",
    "StrategyGuitar",
    "StrategyKeys",
    "CombinedInstrumentPartitioner",
]
