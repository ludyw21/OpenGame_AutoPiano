"""
ChordEngine - 单一模式和弦识别与伴奏生成（精简版）

仅保留一种识别/生成策略，方便维护：
- 固定七个和弦：C, Dm, Em, F, G, Am, G7（键位 z,x,c,v,b,n,m）
- 识别规则（3.2）：
  C:  {1,3,5} -> C-E-G  (pc={0,4,7})
  Dm: {2,4,6} -> D-F-A  (pc={2,5,9})
  Em: {3,5,7} -> E-G-B  (pc={4,7,11})
  F:  {4,6,1} -> F-A-C  (pc={5,9,0})
  G:  {5,7,2} -> G-B-D  (pc={7,11,2})
  Am: {6,1,3} -> A-C-E  (pc={9,0,4})
  G7: {5,7,2,4} -> G-B-D-F (pc={7,11,2,5})

实现要点：
- 使用 200ms 窗口在主音的 note_on 上聚合音高类，按优先级顺序做“严格子集匹配”（必须完全包含和弦所需音高类；找到第一个即返回）。
- 仅输出固定和弦键的 note_on/note_off，时值用 options['chord_min_sustain_ms']，默认 1500ms。
- 不再支持多模式/贪心等可选项；无宽松匹配；相关代码全部移除。
"""
from typing import List, Dict, Any, Optional, Tuple

class ChordEngine:
    def __init__(self):
        # 和弦键映射：七个和弦键对应七个和弦
        self.chord_key_map: Dict[str, str] = {
            'C': 'z',     # C大三和弦
            'Dm': 'x',    # D小三和弦
            'Em': 'c',    # E小三和弦
            'F': 'v',     # F大三和弦
            'G': 'b',     # G大三和弦
            'Am': 'n',    # A小三和弦
            'G7': 'm'     # G属七和弦
        }
        # 和弦音高组合（pitch-class集合，0=C, 1=C#, 2=D...）
        self.chord_pc_sets: Dict[str, set] = {
            'C':  {0, 4, 7},      # C-E-G
            'Dm': {2, 5, 9},      # D-F-A
            'Em': {4, 7, 11},     # E-G-B
            'F':  {5, 9, 0},      # F-A-C
            'G':  {7, 11, 2},     # G-B-D
            'Am': {9, 0, 4},      # A-C-E
            'G7': {7, 11, 2, 5},  # G-B-D-F
        }
        # 候选优先级（按规则顺序，先尝试 G7 再三和弦）
        self.priority: List[str] = ['G7', 'C', 'Dm', 'Em', 'F', 'G', 'Am']

    # --- 公共 API（单一模式） ---
    def generate_accompaniment(self, events: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not events:
            return []
        # 伴奏持续（秒）：最短即默认
        sustain_sec = max(0.0, float(options.get('chord_min_sustain_ms', 1500)) / 1000.0)
        # 抽取节奏切分（主旋律 note_on）
        onsets = self._extract_onsets(events)
        segments = self._build_segments(onsets, events)
        if not segments:
            return []
        # 单一模式识别
        chords = self._detect_chords_for_segments(segments)
        # 合并相邻相同和弦
        merged = self._merge_segments(chords, sustain_sec)
        # 生成伴奏事件
        accomp = self._segments_to_events(merged, sustain_sec)
        try:
            accomp.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            accomp.sort(key=lambda x: x['start_time'])
        return accomp

    # --- 细节实现 ---
    def _extract_onsets(self, events: List[Dict[str, Any]]) -> List[float]:
        # 提取主音note_on事件作为和弦检测的时间点
        onsets = []
        for ev in events:
            if ev.get('type') != 'note_on':
                continue
            # 只处理有MIDI音高信息的主音事件
            if 'note' in ev and ev['note'] is not None:
                onsets.append(float(ev.get('start_time', 0.0)))
        if not onsets:
            return []
        onsets = sorted(set(onsets))
        # 去除过密的切分点（< 50ms），避免抖动
        pruned: List[float] = []
        last = None
        for t in onsets:
            if last is None or (t - last) >= 0.05:
                pruned.append(t)
                last = t
        return pruned

    def _build_segments(self, onsets: List[float], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not onsets:
            return []
        # 使用200ms时间窗口检测和弦
        window_size = 0.2  # 200ms
        segments = []
        
        for onset in onsets:
            # 为每个onset创建200ms窗口
            window_start = onset
            window_end = onset + window_size
            segments.append({'start': window_start, 'end': window_end})
        # 为每个时间窗口统计其中的主音pitch-class
        for seg in segments:
            pcs = set()
            # 查找窗口内的所有note_on事件
            for ev in events:
                if (ev.get('type') == 'note_on' and 
                    'note' in ev and ev['note'] is not None):
                    ev_time = float(ev.get('start_time', 0.0))
                    # 检查事件是否在时间窗口内
                    if seg['start'] <= ev_time <= seg['end']:
                        pc = int(ev['note']) % 12
                        pcs.add(pc)
            seg['pcs'] = pcs
        return segments

    def _detect_chords_for_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for seg in segments:
            name, conf = self._detect_from_pcs(seg['pcs'])
            out.append({
                'start': seg['start'],
                'end': seg['end'],
                'name': name,
                'confidence': conf
            })
        return out

    def _detect_from_pcs(self, pcs: set) -> Tuple[Optional[str], float]:
        """严格匹配：仅当和弦所需的 pitch-class 集完全为窗口内 pcs 的子集时才判定命中。"""
        if len(pcs) < 2:
            return None, 0.0
        for name in self.priority:
            chord_pcs = self.chord_pc_sets[name]
            if chord_pcs.issubset(pcs):
                # 严格子集命中，置信度恒为 1.0（或按覆盖比例，但此处固定为 1.0）
                return name, 1.0
        return None, 0.0

    def _prio(self, name: Optional[str]) -> int:
        if name is None:
            return 1_000_000
        try:
            return self.priority.index(name)
        except Exception:
            return 1_000_000

    def _merge_segments(self, chords: List[Dict[str, Any]], min_sustain: float) -> List[Dict[str, Any]]:
        if not chords:
            return []
        merged: List[Dict[str, Any]] = []
        cur = None
        for seg in chords:
            if seg['name'] is None:
                # 若遇到无和弦段，先收尾
                if cur is not None:
                    merged.append(cur)
                    cur = None
                continue
            if cur is None:
                cur = dict(seg)
            else:
                if seg['name'] == cur['name'] and abs(seg['start'] - cur['end']) < 1e-6:
                    # 相邻且同名则合并
                    cur['end'] = seg['end']
                    cur['confidence'] = max(cur['confidence'], seg['confidence'])
                else:
                    merged.append(cur)
                    cur = dict(seg)
        if cur is not None:
            merged.append(cur)
        # 应用最小延音：如果段长小于阈值，则与相邻段对齐（尽量向后扩）
        out: List[Dict[str, Any]] = []
        for i, seg in enumerate(merged):
            dur = seg['end'] - seg['start']
            if dur < min_sustain and i + 1 < len(merged) and merged[i+1]['name'] == seg['name']:
                merged[i+1]['start'] = seg['start']
                continue
            out.append(seg)
        return out

    def _segments_to_events(self, segments: List[Dict[str, Any]], min_sustain: float) -> List[Dict[str, Any]]:
        evs: List[Dict[str, Any]] = []
        active_chords: Dict[str, float] = {}  # 记录活跃和弦的结束时间
        
        for seg in segments:
            chord_name = seg['name']
            if not chord_name:
                continue
                
            key = self.chord_key_map.get(chord_name)
            if not key:
                continue
                
            start_time = float(seg['start'])
            
            # 检查同一和弦键是否仍在持续中
            if key in active_chords and start_time < active_chords[key]:
                continue  # 跳过，避免重复触发
            
            # 计算和弦持续时间
            sustain_time = min_sustain
            end_time = start_time + sustain_time
            
            # 记录和弦键的活跃状态
            active_chords[key] = end_time
            
            # 生成和弦键事件（与首个主音同步触发）
            evs.append({
                'start_time': start_time, 
                'type': 'note_on', 
                'key': key, 
                'velocity': 64, 
                'channel': 0, 
                'note': None
            })
            evs.append({
                'start_time': end_time, 
                'type': 'note_off', 
                'key': key, 
                'velocity': 0, 
                'channel': 0, 
                'note': None
            })
        return evs
