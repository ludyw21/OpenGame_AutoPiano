"""
MIDI analyzer: parse notes, filter by pitch groups, simple melody extraction.
"""
from typing import List, Dict, Any, Optional, Tuple

try:
    import mido
except Exception:
    mido = None  # Analyzer will report error if unavailable

from .groups import filter_notes_by_groups, group_for_note


def _gather_notes(mid) -> List[Dict[str, Any]]:
    ticks_per_beat = getattr(mid, 'ticks_per_beat', 480)
    tempo = 500000  # default 120 BPM
    # 以绝对tick记录的tempo变化 (tick, tempo_us_per_beat)
    tempo_changes: List[Tuple[int, int]] = [(0, tempo)]
    # accumulate absolute time per track to the merged view
    events: List[Dict[str, Any]] = []

    for i, track in enumerate(mid.tracks):
        t = 0
        on_stack = {}
        cur_tempo = tempo
        for msg in track:
            t += msg.time
            if msg.type == 'set_tempo':
                cur_tempo = msg.tempo
                tempo_changes.append((int(t), int(cur_tempo)))
            if msg.type == 'note_on' and msg.velocity > 0:
                on_stack.setdefault((msg.channel, msg.note), []).append((t, msg.velocity))
            elif msg.type in ('note_off', 'note_on'):
                if msg.type == 'note_on' and msg.velocity > 0:
                    continue
                key = (msg.channel, msg.note)
                if key in on_stack and on_stack[key]:
                    start_tick, vel = on_stack[key].pop(0)
                    events.append({
                        'start_tick': start_tick,
                        'end_tick': t,
                        'channel': msg.channel,
                        'note': msg.note,
                        'velocity': vel,
                    })
    # 转换为精确时间：基于 tempo_changes 分段积分（PPQ），SMPTE 简化为常量换算
    if not events:
        return []

    # 统一排序并去除同tick重复，仅保留最后一次tempo（同tick后者覆盖前者）
    tempo_changes_sorted = sorted(tempo_changes, key=lambda x: int(x[0]))
    dedup: List[Tuple[int, int]] = []
    for tk, tp in tempo_changes_sorted:
        if not dedup or int(tk) != int(dedup[-1][0]):
            dedup.append((int(tk), int(tp)))
        else:
            dedup[-1] = (int(tk), int(tp))
    tempo_changes = dedup if dedup else [(0, tempo)]

    def tick_to_seconds_ppq(target_tick: int) -> float:
        if target_tick <= 0:
            return 0.0
        acc = 0.0
        prev_tick = 0
        prev_tempo = tempo_changes[0][1]
        for i in range(1, len(tempo_changes)):
            cur_tick, cur_tempo = tempo_changes[i]
            if cur_tick > target_tick:
                break
            dt = max(0, cur_tick - prev_tick)
            acc += (dt * prev_tempo) / (ticks_per_beat * 1_000_000.0)
            prev_tick = cur_tick
            prev_tempo = cur_tempo
        # tail
        dt_tail = max(0, int(target_tick) - int(prev_tick))
        acc += (dt_tail * prev_tempo) / (ticks_per_beat * 1_000_000.0)
        return acc

    is_smpte = bool(ticks_per_beat < 0)
    # SMPTE: 这里暂不从 division 拆解fps和ticks_per_frame，后续如需可与 auto_player 统一实现
    # 先按近似：若为SMPTE，尝试使用 mido.MidiFile.length 比例映射（保持相对位置），否则退化为PPQ路径
    mf_len = 0.0
    try:
        mf_len = float(getattr(mid, 'length', 0.0) or 0.0)
    except Exception:
        mf_len = 0.0

    if not is_smpte:
        for e in events:
            st = tick_to_seconds_ppq(int(e['start_tick']))
            et = tick_to_seconds_ppq(int(e['end_tick']))
            e['start_time'] = st
            e['end_time'] = max(et, st)
            e['duration'] = max(0.0, e['end_time'] - e['start_time'])
            e['group'] = group_for_note(e['note'])
    else:
        # 近似：按ticks线性映射到mido.length（若可用），保持事件相对位置
        max_tick = 0
        try:
            max_tick = max(int(e['end_tick']) for e in events)
        except Exception:
            max_tick = 0
        scale = (mf_len / max_tick) if (mf_len > 0.0 and max_tick > 0) else 0.0
        if scale <= 0.0:
            # 无法近似时退化为默认120BPM（尽量避免抖动）
            for e in events:
                st = (int(e['start_tick']) * tempo) / (ticks_per_beat * 1_000_000.0)
                et = (int(e['end_tick']) * tempo) / (ticks_per_beat * 1_000_000.0)
                e['start_time'] = st
                e['end_time'] = max(et, st)
                e['duration'] = max(0.0, e['end_time'] - e['start_time'])
                e['group'] = group_for_note(e['note'])
        else:
            for e in events:
                st = int(e['start_tick']) * scale
                et = int(e['end_tick']) * scale
                e['start_time'] = st
                e['end_time'] = max(et, st)
                e['duration'] = max(0.0, e['end_time'] - e['start_time'])
                e['group'] = group_for_note(e['note'])
    # expand to note_on/off style for event table if needed by caller
    return events


def parse_midi(file_path: str) -> Dict[str, Any]:
    if mido is None:
        return {'ok': False, 'error': 'mido 不可用'}
    try:
        mid = mido.MidiFile(file_path)
        notes = _gather_notes(mid)
        channels = sorted({n['channel'] for n in notes}) if notes else []
        return {'ok': True, 'notes': notes, 'channels': channels, 'ticks_per_beat': getattr(mid, 'ticks_per_beat', 480)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def filter_by_groups(notes: List[Dict[str, Any]], selected_groups: List[str]) -> List[Dict[str, Any]]:
    return filter_notes_by_groups(notes, selected_groups)


def _rhythm_entropy(times: List[float]) -> float:
    if not times:
        return 0.0
    import math
    from collections import Counter
    # quantize intervals to 50ms bins to compute a discrete distribution
    intervals = [max(1, int(round(dt / 0.05))) for dt in times if dt > 1e-4]
    if not intervals:
        return 0.0
    c = Counter(intervals)
    total = sum(c.values())
    ent = 0.0
    for v in c.values():
        p = v / total
        ent -= p * math.log(p + 1e-12)
    return ent


def _dominant_ioi_period(times: List[float]) -> Optional[float]:
    """估计主导节拍周期（Inter-Onset Interval）"""
    if not times:
        return None
    from collections import Counter
    # 量化到20ms，更灵敏
    bins = [max(1, int(round(t / 0.02))) for t in times if t > 1e-3]
    if not bins:
        return None
    c = Counter(bins)
    best_bin, _ = max(c.items(), key=lambda kv: kv[1])
    return best_bin * 0.02


def _channel_scores(
    notes: List[Dict[str, Any]],
    entropy_weight: float,
    *,
    prefer_programs: Optional[List[int]] = None,
    prefer_name_keywords: Optional[List[str]] = None,
    density_target: float = 3.0,
    density_weight: float = 0.5,
) -> Dict[int, float]:
    """给各通道打分（更稳健）：
    - 自适应音高焦点：以全局中位数±12为主旋律高发区。
    - 乐器/音色加权：lead类program/名称包含solo/lead等加分。
    - 节奏密度惩罚：过稠或过稀都扣分，目标密度默认为3音/秒。
    - 熵（越稳定越好）仍生效。
    """
    by_ch: Dict[int, List[Dict[str, Any]]] = {}
    all_pitches: List[int] = []
    for n in notes:
        by_ch.setdefault(n['channel'], []).append(n)
        try:
            all_pitches.append(int(n.get('note', 0)))
        except Exception:
            pass

    # 全局音高中位数估计旋律区中心
    import statistics
    if all_pitches:
        try:
            med = int(statistics.median(all_pitches))
        except Exception:
            med = 72
    else:
        med = 72  # C5 作为兜底
    low = max(40, med - 12)
    high = min(96, med + 12)

    prefer_programs = prefer_programs or [40, 41, 42, 43, 44, 45, 46, 47, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88]
    prefer_name_keywords = prefer_name_keywords or ["lead", "melody", "vocal", "violin", "flute", "sax", "oboe", "solo"]

    scores: Dict[int, float] = {}
    # 全曲时长用于密度
    try:
        total_time = max((float(n.get('end_time', 0.0)) for n in notes), default=0.0)
    except Exception:
        total_time = 0.0

    for ch, arr in by_ch.items():
        arr_sorted = sorted(arr, key=lambda x: x['start_time'])
        pitches = [int(n.get('note', 0)) for n in arr]
        focus_hits = sum(1 for p in pitches if low <= p <= high)
        ioi = [max(0.0, arr_sorted[i]['start_time'] - arr_sorted[i-1]['start_time']) for i in range(1, len(arr_sorted))]
        ent = _rhythm_entropy(ioi)

        # program/name boost
        prog_vals = {n.get('program') for n in arr}
        prog_boost = 0.0
        for pv in prog_vals:
            try:
                if pv in prefer_programs:
                    prog_boost += 1.0
            except Exception:
                pass
        name_vals = {str(n.get('instrument_name', '')).lower() for n in arr}
        name_boost = 0.0
        for nm in name_vals:
            if any(kw in nm for kw in prefer_name_keywords):
                name_boost += 1.0

        # density penalty（按通道自身密度，也与全曲时长关联以避免短样本放大）
        if total_time > 0.0:
            density = len(arr) / max(1e-3, total_time)
            density_penalty = density_weight * abs(float(density) - float(density_target))
        else:
            density_penalty = 0.0

        scores[ch] = float(focus_hits) + prog_boost + name_boost - float(entropy_weight) * float(ent) - density_penalty
    return scores


def _filter_by_repetition(notes: List[Dict[str, Any]], strength: float = 1.0, pitch_repeat_penalty: float = 1.0,
                          min_keep: int = 8) -> List[Dict[str, Any]]:
    """基于全曲音高重复度的过滤。强度越大越严格。"""
    if not notes:
        return []
    from collections import Counter
    cnt = Counter([int(n.get('note', 0)) for n in notes])
    total = len(notes)
    # 频率阈值：强度线性映射到 [0.05, 0.25]
    thr = 0.05 + 0.20 * max(0.0, min(1.0, strength))
    keep = []
    for n in notes:
        p = int(n.get('note', 0))
        freq = cnt[p] / max(1, total)
        # 频率越高越可能被过滤
        score = 1.0 - pitch_repeat_penalty * freq
        if score > thr:
            keep.append(n)
    # 若过度过滤，放宽阈值一次（而不是直接返回原集）
    if len(keep) < min_keep:
        thr *= 0.8
        keep2 = []
        for n in notes:
            p = int(n.get('note', 0))
            freq = cnt[p] / max(1, total)
            score = 1.0 - pitch_repeat_penalty * freq
            if score > thr:
                keep2.append(n)
        return keep2 if keep2 else notes[:min(len(notes), min_keep)]
    return keep


def _filter_by_beat_similarity(notes: List[Dict[str, Any]], strength: float = 1.0) -> List[Dict[str, Any]]:
    """基于节拍相似度的过滤：保留接近主导节拍周期的音符起始间隔。"""
    if not notes:
        return []
    arr = sorted(notes, key=lambda x: x.get('start_time', 0.0))
    ioi = [max(0.0, arr[i]['start_time'] - arr[i-1]['start_time']) for i in range(1, len(arr))]
    period = _dominant_ioi_period(ioi)
    if not period:
        return notes
    # 允许偏差：强度线性映射到容忍度 [35%, 12%]
    tol = 0.35 - 0.23 * max(0.0, min(1.0, strength))
    keep = [arr[0]]
    for i in range(1, len(arr)):
        dt = max(0.0, arr[i]['start_time'] - arr[i-1]['start_time'])
        if abs(dt - period) <= tol * period:
            keep.append(arr[i])
    # 若过度过滤，扩大容忍度一次
    if len(keep) < max(8, len(arr) // 4):
        tol *= 1.5
        keep2 = [arr[0]]
        for i in range(1, len(arr)):
            dt = max(0.0, arr[i]['start_time'] - arr[i-1]['start_time'])
            if abs(dt - period) <= tol * period:
                keep2.append(arr[i])
        return keep2 if len(keep2) >= 8 else keep
    return keep


def _enforce_monophony(notes: List[Dict[str, Any]], window: float = 0.06, prefer: str = 'highest') -> List[Dict[str, Any]]:
    """将多声部序列压成单声部旋律。按起始时间窗口聚类，每窗口选1个音符。
    prefer: 'highest' 挑最高音, 'velocity' 挑力度大, 'longest' 挑时值长。
    """
    if not notes:
        return []
    arr = sorted(notes, key=lambda x: (x.get('start_time', 0.0), -x.get('note', 0)))
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(arr):
        j = i + 1
        start_i = arr[i].get('start_time', 0.0)
        cluster = [arr[i]]
        while j < len(arr) and (arr[j].get('start_time', 0.0) - start_i) <= window:
            cluster.append(arr[j])
            j += 1
        # 选择代表音
        if prefer == 'velocity':
            chosen = max(cluster, key=lambda n: n.get('velocity', 0))
        elif prefer == 'longest':
            chosen = max(cluster, key=lambda n: n.get('duration', 0.0))
        else:
            chosen = max(cluster, key=lambda n: n.get('note', 0))
        out.append(chosen)
        i = j
    # 合并相邻相同音高的短间隙片段
    merged: List[Dict[str, Any]] = []
    for n in out:
        if merged and n.get('note') == merged[-1].get('note') and (n.get('start_time', 0.0) - merged[-1].get('end_time', 0.0)) <= window:
            merged[-1]['end_time'] = max(merged[-1]['end_time'], n.get('end_time', merged[-1]['end_time']))
            merged[-1]['duration'] = max(0.0, merged[-1]['end_time'] - merged[-1]['start_time'])
        else:
            merged.append(dict(n))
    return merged


def extract_melody(notes: List[Dict[str, Any]], prefer_channel: Optional[int] = None,
                   entropy_weight: float = 0.5, min_score: Optional[float] = None,
                   mode: str = 'entropy', strength: float = 0.5,
                   repetition_penalty: float = 1.0,
                   prefer_programs: Optional[List[int]] = None,
                   prefer_name_keywords: Optional[List[str]] = None,
                   density_target: float = 3.0,
                   density_weight: float = 0.5) -> List[Dict[str, Any]]:
    """
    主旋律提取：支持多种模式
    - mode='entropy': 原有策略（默认），通过中高音命中与节奏熵评分选择通道
    - mode='beat': 先按熵评分选通道，再按节拍相似度过滤
    - mode='repetition': 先按熵评分选通道，再按全曲重复度过滤
    - mode='hybrid': 同时按节拍相似度与重复度进行联合过滤
    参数 strength ∈ [0,1]：过滤强度；repetition_penalty 越大越严
    保持兼容：未传新参数时等同旧实现
    """
    if not notes:
        return []
    # 评分选通道（即便指定 prefer_channel 也计算评分，便于最小得分判断）
    try:
        ew = float(entropy_weight)
    except Exception:
        ew = 0.5
    scores = _channel_scores(
        notes, ew,
        prefer_programs=prefer_programs,
        prefer_name_keywords=prefer_name_keywords,
        density_target=density_target,
        density_weight=density_weight,
    )
    if not scores:
        return []
    chosen: List[Dict[str, Any]]
    chosen_ch: Optional[int] = None
    if prefer_channel is not None:
        cand = [n for n in notes if n['channel'] == prefer_channel]
        if cand:
            chosen = cand
            chosen_ch = prefer_channel
        else:
            # 回退到评分最高的通道
            chosen_ch = max(scores.items(), key=lambda kv: kv[1])[0]
            chosen = [n for n in notes if n['channel'] == chosen_ch]
    else:
        chosen_ch = max(scores.items(), key=lambda kv: kv[1])[0]
        chosen = [n for n in notes if n['channel'] == chosen_ch]

    # 最小得分门限（对通道评分）
    if min_score is not None and chosen_ch is not None:
        try:
            if scores.get(chosen_ch, -1e9) < float(min_score):
                return []
        except Exception:
            pass

    m = (mode or 'entropy').lower()
    s = max(0.0, min(1.0, float(strength)))
    if m == 'beat':
        seq = _filter_by_beat_similarity(chosen, strength=s)
        result = _enforce_monophony(seq, window=0.06 + 0.04*(1.0 - s), prefer='highest')
    elif m == 'repetition':
        seq = _filter_by_repetition(chosen, strength=s, pitch_repeat_penalty=float(repetition_penalty))
        result = _enforce_monophony(seq, window=0.06 + 0.04*(1.0 - s), prefer='highest')
    elif m == 'hybrid':
        tmp = _filter_by_repetition(chosen, strength=s, pitch_repeat_penalty=float(repetition_penalty))
        seq = _filter_by_beat_similarity(tmp, strength=s)
        result = _enforce_monophony(seq, window=0.06 + 0.04*(1.0 - s), prefer='highest')
    else:
        # 默认：熵启发（通道选择 + 可选单声部约束，强度>0则应用）
        result = _enforce_monophony(chosen, window=0.08 + 0.05*(1.0 - s), prefer='highest') if s > 0 else chosen

    # 兜底：若过滤过度导致为空，回退到所选通道的「力度优先/时值优先」TOP样本
    if not result:
        arr = sorted(chosen, key=lambda x: (int(x.get('velocity', 0)), float(x.get('duration', 0.0))), reverse=True)
        k = min(16, len(arr))
        # 再施加单声部约束
        return _enforce_monophony(arr[:k], window=0.08, prefer='highest') if k > 0 else []
    return result
