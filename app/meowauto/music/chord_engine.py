"""
ChordEngine - 更完善的和弦识别与伴奏生成

目标：
- 用精细的时间切分与主旋律节奏对齐
- 提升和弦识别稳健性（pitch-class 统计 + 模式评分）
- 兼容现有 7 个和弦键位（z,x,c,v,b,n,m -> C,Dm,Em,F,G,Am,G7）
- 向外提供 generate_accompaniment(events, options) API

输入 events: List[Dict]
- 必须包含: 'start_time' (float), 'type' in ('note_on','note_off'), 'key' (str)
- 可选: 'note' (int, MIDI 音高)；若提供则会用于更准的和弦检测

输出: List[Dict] 附加的伴奏事件（note_on/note_off, 使用固定和弦键）
"""
from typing import List, Dict, Any, Optional, Tuple

class ChordEngine:
    def __init__(self):
        # 固定的和弦键映射
        self.chord_key_map: Dict[str, str] = {
            'C': 'z', 'Dm': 'x', 'Em': 'c', 'F': 'v', 'G': 'b', 'Am': 'n', 'G7': 'm'
        }
        # 候选和弦的模式（pitch-class 集合）
        # 以 C 大调常用和弦为主，匹配时按集合交集评分
        self.chord_pc_sets: Dict[str, set] = {
            'C':  {0, 4, 7},
            'Dm': {2, 5, 9},
            'Em': {4, 7, 11},
            'F':  {5, 9, 0},
            'G':  {7, 11, 2},
            'Am': {9, 0, 4},
            'G7': {7, 11, 2, 5},
        }
        # 候选优先级（打分持平时按此顺序）
        self.priority: List[str] = ['G7', 'C', 'Dm', 'Em', 'F', 'G', 'Am']

    # --- 公共 API ---
    def generate_accompaniment(self, events: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not events:
            return []
        mode = str(options.get('chord_accomp_mode', 'triad')).lower()  # triad/triad7/greedy
        min_sustain = max(0.0, float(options.get('chord_accomp_min_sustain_ms', 120)) / 1000.0)
        # 抽取节奏切分（主旋律 onsets）
        onsets = self._extract_onsets(events)
        # 构建时间段
        segments = self._build_segments(onsets, events)
        if not segments:
            return []
        # 对每个段进行和弦识别
        chords = self._detect_chords_for_segments(segments, mode)
        # 合并相邻相同和弦并应用最小延音
        merged = self._merge_segments(chords, min_sustain)
        # 生成伴奏键位事件
        accomp = self._segments_to_events(merged, min_sustain)
        # 排序（note_off 优先）
        try:
            accomp.sort(key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            accomp.sort(key=lambda x: x['start_time'])
        return accomp

    # --- 细节实现 ---
    def _extract_onsets(self, events: List[Dict[str, Any]]) -> List[float]:
        # 使用含 note 的 note_on 作为候选主旋律切分；若都没有 note 字段，则退化为所有 note_on
        onsets = []
        for ev in events:
            if ev.get('type') != 'note_on':
                continue
            if 'note' in ev and ev['note'] is not None:
                onsets.append(float(ev.get('start_time', 0.0)))
            elif 'note' not in ev:
                onsets.append(float(ev.get('start_time', 0.0)))
        if not onsets:
            return []
        onsets = sorted(set(onsets))
        # 去除过密的切分点（< 30ms），避免抖动
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
        # 片段 [onsets[i], onsets[i+1])，最后一个到 end_time
        raw_segments = []
        for i, st in enumerate(onsets):
            et = onsets[i+1] if i + 1 < len(onsets) else end_time
            if et <= st:
                continue
            raw_segments.append({'start': float(st), 'end': float(et)})
        # 为每段统计活跃的 pitch-class（依据 note_on/note_off 累积），严格对齐边界
        # 先排序事件（note_off 优先）
        try:
            evs = sorted(events, key=lambda x: (x['start_time'], 0 if x.get('type') == 'note_off' else 1))
        except Exception:
            evs = list(events)
        pc_counts: Dict[int, int] = {}
        seg_idx = 0
        timeline = sorted(set([s['start'] for s in raw_segments] + [s['end'] for s in raw_segments]))
        # 扫描时间线，更新 pc 并在段边界采样
        # 建立从边界时间到 pc 集的映射
        boundary_state: Dict[float, set] = {}
        j = 0
        for t in timeline:
            # 推进到时间 t
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
        # 为每段赋值 pcs（取段内恒定假设：使用段起点的 pcs）
        segments = []
        for seg in raw_segments:
            pcs = boundary_state.get(seg['start'], set())
            segments.append({'start': seg['start'], 'end': seg['end'], 'pcs': pcs})
        return segments

    def _detect_chords_for_segments(self, segments: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
        out = []
        for seg in segments:
            name, conf = self._detect_from_pcs(seg['pcs'], mode)
            out.append({
                'start': seg['start'],
                'end': seg['end'],
                'name': name,
                'confidence': conf
            })
        return out

    def _detect_from_pcs(self, pcs: set, mode: str) -> Tuple[Optional[str], float]:
        if not pcs:
            return None, 0.0
        # 根据模式筛选候选
        candidates: List[str]
        if mode == 'triad7':
            candidates = self.priority  # 含 G7
        elif mode == 'triad':
            candidates = [n for n in self.priority if n != 'G7']
        else:  # greedy
            candidates = self.priority
        # 评分：交集 |pcs ∩ chord|，并对三度/根音给予额外权重
        best = None
        best_score = -1.0
        for name in candidates:
            patt = self.chord_pc_sets[name]
            inter = patt.intersection(pcs)
            base = float(len(inter))
            # 额外权重：根音(和弦集合中的最小 pc) + 三度
            # 这里以集合中取一个稳定代表：对于三和弦，根音可视为集合中距 0 最近者的相对根；为简化，直接对集合所有音各+微权重
            bonus = 0.0
            for pc in inter:
                bonus += 0.1
            score = base + bonus
            if score > best_score or (abs(score - best_score) < 1e-6 and self._prio(name) < self._prio(best)):
                best = name
                best_score = score
        # 置信度：min(1.0, |inter| / |patt| + 0.1*|inter|)
        if best is None:
            return None, 0.0
        inter_sz = len(self.chord_pc_sets[best].intersection(pcs))
        patt_sz = max(1, len(self.chord_pc_sets[best]))
        confidence = min(1.0, (inter_sz / patt_sz) + 0.1 * inter_sz)
        # 若 greedy 模式且匹配小于2个音，视为不确定
        if mode == 'greedy' and inter_sz < 2:
            return None, 0.0
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
