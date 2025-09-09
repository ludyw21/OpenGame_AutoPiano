"""
ChordEngine - 旧版 triad 模式（仅三和弦，排除 G7）

策略说明：
- 固定六个和弦：C, Dm, Em, F, G, Am（键位 z,x,c,v,b,n）
- 识别流程：
  1) 抽取主旋律 note_on 作为切分点（允许无 note 字段），30ms 去抖
  2) 以切分构建连续时间段 [onset[i], onset[i+1])，最后一段至全局 end_time
  3) 按时间轴滚动维护活跃 pitch-class（note_off 优先排序），段起点采样 pcs
  4) 使用“相交计数 + 微权重 + 优先级”对候选三和弦评分，择优输出（不含 G7）
- 事件生成：在段起点输出 note_on，note_off = max(段终点, note_on + 最小延音)
- 最小延音参数：优先读取 options['chord_accomp_min_sustain_ms']，若缺失则回退到 options['chord_min_sustain_ms']，默认 1500ms
"""
from typing import List, Dict, Any, Optional, Tuple

class ChordEngine:
    def __init__(self):
        # 和弦键映射：仅三和弦（排除 G7）
        self.chord_key_map: Dict[str, str] = {
            'C': 'z',     # C大三和弦
            'Dm': 'x',    # D小三和弦
            'Em': 'c',    # E小三和弦
            'F': 'v',     # F大三和弦
            'G': 'b',     # G大三和弦
            'Am': 'n'     # A小三和弦
        }
        # 和弦音高组合（pitch-class集合，0=C, 1=C#, 2=D...）
        self.chord_pc_sets: Dict[str, set] = {
            'C':  {0, 4, 7},      # C-E-G
            'Dm': {2, 5, 9},      # D-F-A
            'Em': {4, 7, 11},     # E-G-B
            'F':  {5, 9, 0},      # F-A-C
            'G':  {7, 11, 2},     # G-B-D
            'Am': {9, 0, 4}       # A-C-E
        }
        # 候选优先级（仅三和弦）
        self.priority: List[str] = ['C', 'Dm', 'Em', 'F', 'G', 'Am']

    # --- 公共 API（仅 triad 模式） ---
    def generate_accompaniment(self, events: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not events:
            return []
        # 最小延音（秒）：优先旧键名，其次新键名，默认 1500ms
        sustain_ms = options.get('chord_accomp_min_sustain_ms', options.get('chord_min_sustain_ms', 1500))
        sustain_sec = max(0.0, float(sustain_ms) / 1000.0)
        # 抽取节奏切分（主旋律 note_on）
        onsets = self._extract_onsets(events)
        segments = self._build_segments(onsets, events)
        if not segments:
            return []
        # triad 模式识别
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
        # 提取主音 note_on 事件作为和弦检测的时间点（允许无 note 字段），30ms 去抖
        onsets: List[float] = []
        for ev in events:
            if ev.get('type') != 'note_on':
                continue
            t = float(ev.get('start_time', 0.0))
            onsets.append(t)
        if not onsets:
            return []
        onsets = sorted(set(onsets))
        pruned: List[float] = []
        last = None
        for t in onsets:
            if last is None or (t - last) >= 0.03:
                pruned.append(t)
                last = t
        return pruned

    def _build_segments(self, onsets: List[float], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not onsets:
            return []
        end_time = max(float(e.get('start_time', 0.0)) for e in events) if events else onsets[-1]
        # 构建连续片段 [onsets[i], onsets[i+1])，最后一段到 end_time
        raw_segments: List[Dict[str, Any]] = []
        for i, st in enumerate(onsets):
            et = onsets[i+1] if i + 1 < len(onsets) else end_time
            if et <= st:
                continue
            raw_segments.append({'start': float(st), 'end': float(et)})
        # 为每段统计活跃的 pitch-class（依据 note_on/note_off 累积），严格对齐段起点
        # 先排序事件（note_off 优先）
        try:
            evs = sorted(events, key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            evs = list(events)
        pc_counts: Dict[int, int] = {}
        timeline = sorted(set([s['start'] for s in raw_segments] + [s['end'] for s in raw_segments]))
        boundary_state: Dict[float, set] = {}
        j = 0
        for t in timeline:
            # 推进到时间 t，更新活跃 pc
            while j < len(evs) and float(evs[j].get('start_time', 0.0)) <= t:
                ev = evs[j]
                n = ev.get('note', None)
                if n is not None:
                    pc = int(n) % 12
                    if ev.get('type') == 'note_on':
                        pc_counts[pc] = pc_counts.get(pc, 0) + 1
                    else:  # note_off
                        if pc in pc_counts:
                            pc_counts[pc] = max(0, pc_counts[pc] - 1)
                            if pc_counts[pc] == 0:
                                del pc_counts[pc]
                j += 1
            boundary_state[t] = set(pc_counts.keys())
        segments: List[Dict[str, Any]] = []
        for seg in raw_segments:
            pcs = boundary_state.get(seg['start'], set())
            segments.append({'start': seg['start'], 'end': seg['end'], 'pcs': pcs})
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
        """triad 模式的打分匹配：按交集计数 + 微权重 + 优先级 决定最佳和弦（不含 G7）。"""
        if not pcs:
            return None, 0.0
        best: Optional[str] = None
        best_score: float = -1.0
        for name in self.priority:
            patt = self.chord_pc_sets[name]
            inter = patt.intersection(pcs)
            base = float(len(inter))
            # 微权重：命中音各 +0.1
            bonus = 0.1 * len(inter)
            score = base + bonus
            if score > best_score or (abs(score - best_score) < 1e-6 and self._prio(name) < self._prio(best)):
                best = name
                best_score = score
        if best is None:
            return None, 0.0
        inter_sz = len(self.chord_pc_sets[best].intersection(pcs))
        patt_sz = max(1, len(self.chord_pc_sets[best]))
        confidence = min(1.0, (inter_sz / patt_sz) + 0.1 * inter_sz)
        return best, confidence

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
        for seg in segments:
            key = self.chord_key_map.get(seg['name'])
            if not key:
                continue
            on_t = float(seg['start'])
            off_t = max(float(seg['end']), on_t + min_sustain)
            evs.append({'start_time': on_t, 'type': 'note_on', 'key': key, 'velocity': 64, 'channel': 0, 'note': None})
            evs.append({'start_time': off_t, 'type': 'note_off', 'key': key, 'velocity': 0, 'channel': 0, 'note': None})
        return evs
