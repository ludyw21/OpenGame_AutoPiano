"""
MIDI analyzer: parse notes using pretty_midi library for accurate timing.
"""
from typing import List, Dict, Any, Optional

try:
    import pretty_midi
except Exception:
    pretty_midi = None
try:
    import miditoolkit
except Exception:
    miditoolkit = None

from .groups import filter_notes_by_groups, group_for_note

# ===== 解析引擎选择（默认：miditoolkit，更稳健处理不规范MIDI） =====
DEFAULT_ENGINE = 'miditoolkit'  # 'auto' | 'pretty_midi' | 'miditoolkit'

def set_default_engine(engine: str) -> None:
    global DEFAULT_ENGINE
    e = (engine or '').strip().lower()
    if e in ('auto', 'pretty_midi', 'miditoolkit'):
        DEFAULT_ENGINE = e
    else:
        DEFAULT_ENGINE = 'miditoolkit'


def _gather_notes(pm_data) -> List[Dict[str, Any]]:
    """使用pretty_midi收集音符事件，直接获得准确的秒级时间"""
    events: List[Dict[str, Any]] = []
    
    # 调试信息
    print(f"[DEBUG] 解析到 {len(pm_data.instruments)} 个乐器")
    
    # 遍历所有乐器
    for instrument_idx, instrument in enumerate(pm_data.instruments):
        print(f"[DEBUG] 乐器 {instrument_idx}: {len(instrument.notes)} 个音符, is_drum={instrument.is_drum}, program={instrument.program}")
        
        # 遍历乐器中的所有音符
        for note_idx, note in enumerate(instrument.notes):
            # 保持原始通道信息，不强制修改
            channel = 9 if instrument.is_drum else instrument_idx
            duration = note.end - note.start
            
            # 调试前几个音符的时长
            if note_idx < 3:
                print(f"[DEBUG] 音符 {note_idx}: start={note.start:.4f}s, end={note.end:.4f}s, duration={duration:.4f}s, pitch={note.pitch}")
            
            events.append({
                'start_time': note.start,  # 直接以秒为单位
                'end_time': note.end,      # 直接以秒为单位
                'duration': duration,      # 准确的时长（秒）
                'note': note.pitch,        # MIDI音符号
                'velocity': note.velocity, # 力度
                'channel': channel,        # 使用乐器索引作为通道
                'track': instrument_idx,   # 轨道索引
                'program': instrument.program,  # 乐器程序号
                'instrument_name': instrument.name or f"Instrument_{instrument_idx}",
                'is_drum': instrument.is_drum  # 添加鼓标识
            })
    
    print(f"[DEBUG] 总共收集到 {len(events)} 个音符事件")
    
    # 打印最高音和最低音符，并添加超限判定
    max_note = 0
    min_note = 127
    max_group = "未知"
    min_group = "未知"
    max_status = "未超限"
    min_status = "未超限"
    above_83_count = 0
    below_48_count = 0
    
    if events:
        notes = [e['note'] for e in events]
        max_note = max(notes)
        min_note = min(notes)
        max_group = group_for_note(max_note)
        min_group = group_for_note(min_note)
        
        # 统计超限数量
        above_83_count = len([note for note in notes if note > 83])
        below_48_count = len([note for note in notes if note < 48])
        
        # 最高音超限判定
        max_over_limit = max_note > 83
        max_status = "已超限" if max_over_limit else "未超限"
        
        # 最低音超限判定
        min_over_limit = min_note < 48
        min_status = "已超限" if min_over_limit else "未超限"
        
        # 按照要求格式打印
        print(f"[DEBUG] 最高音：{max_note}  {max_group}  {max_status} 超限数量 {above_83_count}")
        print(f"[DEBUG] 最低音：{min_note} {min_group}  {min_status} 超限数量 {below_48_count}")
    
    # 添加音符分组信息
    for e in events:
        e['group'] = group_for_note(e['note'])
    
    # 按时间排序
    events.sort(key=lambda x: x['start_time'])
    
    return events


def parse_midi(file_path: str) -> Dict[str, Any]:
    """解析MIDI文件，优先使用 pretty_midi；失败或结果异常时回退 miditoolkit。
    返回统一结构：{'ok': bool, 'notes': list, 'channels': list, 'resolution': int|None, 'initial_tempo': float, 'end_time': float, 'total_notes': int, 'source': 'pretty_midi'|'miditoolkit', 'max_note': int, 'min_note': int, 'max_group': str, 'min_group': str, 'max_status': str, 'min_status': str, 'above_83_count': int, 'below_48_count': int}
    """
    # 根据 DEFAULT_ENGINE 决定优先顺序
    engine = DEFAULT_ENGINE
    try:
        print(f"[DEBUG] 解析引擎请求: engine={engine}, file={file_path}")
    except Exception:
        pass
    if engine == 'miditoolkit':
        # 先走 miditoolkit
        try:
            if miditoolkit is None:
                # 无 miditoolkit 则退回 auto（后续尝试 pretty_midi）
                pass
            else:
                midi_obj = miditoolkit.midi.parser.MidiFile(file_path)
                notes: List[Dict[str, Any]] = []
                try:
                    if midi_obj.tempo_changes:
                        initial_tempo = float(midi_obj.tempo_changes[0].tempo)
                    else:
                        initial_tempo = 120.0
                except Exception:
                    initial_tempo = 120.0
                try:
                    end_time = float(midi_obj.max_tick) * (60.0 / (initial_tempo * float(midi_obj.ticks_per_beat))) if midi_obj.ticks_per_beat else 0.0
                except Exception:
                    end_time = 0.0
                for ti, inst in enumerate(midi_obj.instruments):
                    is_drum = bool(getattr(inst, 'is_drum', False))
                    program = int(getattr(inst, 'program', 0) or 0)
                    name = str(getattr(inst, 'name', '') or f"Instrument_{ti}")
                    for note in inst.notes:
                        rec = {
                            'start_time': float(note.start),
                            'end_time': float(note.end),
                            'duration': max(0.0, float(note.end) - float(note.start)),
                            'note': int(note.pitch),
                            'velocity': int(note.velocity),
                            'channel': 9 if is_drum else ti,
                            'track': ti,
                            'program': program,
                            'instrument_name': name,
                            'is_drum': is_drum,
                        }
                        rec['group'] = group_for_note(rec['note'])
                        notes.append(rec)
                notes.sort(key=lambda x: x['start_time'])

                # 对齐旧版：若 t≈0 存在多条 tempo 且 BPM 不同，选慢速BPM并整体缩放
                try:
                    tmps = getattr(midi_obj, 'tempo_changes', []) or []
                    # miditoolkit 的 tempo_changes 元素一般含 .time(秒) 与 .tempo(BPM)
                    zero_bpms_mt = []
                    for tc in tmps:
                        try:
                            t0 = float(getattr(tc, 'time', 0.0) or 0.0)
                            bpm0 = float(getattr(tc, 'tempo', initial_tempo))
                            if t0 <= 1e-9:
                                zero_bpms_mt.append(bpm0)
                        except Exception:
                            continue
                    if zero_bpms_mt:
                        desired_bpm_mt = min(zero_bpms_mt)
                        cur_bpm_mt = float(initial_tempo)
                        if desired_bpm_mt > 0 and cur_bpm_mt > 0 and desired_bpm_mt < (cur_bpm_mt - 1e-6):
                            scale_mt = cur_bpm_mt / desired_bpm_mt
                            for e in notes:
                                st = float(e.get('start_time', 0.0)) * scale_mt
                                et = float(e.get('end_time', st)) * scale_mt
                                e['start_time'] = st
                                e['end_time'] = et
                                e['duration'] = max(0.0, et - st)
                            initial_tempo = desired_bpm_mt
                            end_time = float(end_time) * scale_mt if end_time else (notes[-1]['end_time'] if notes else 0.0)
                except Exception:
                    pass
                channels = sorted({n['channel'] for n in notes}) if notes else []
                # 计算最高音和最低音信息
                max_note = 0
                min_note = 127
                max_group = "未知"
                min_group = "未知"
                max_status = "未超限"
                min_status = "未超限"
                above_83_count = 0
                below_48_count = 0
                
                if notes:
                    note_values = [n['note'] for n in notes]
                    max_note = max(note_values)
                    min_note = min(note_values)
                    max_group = group_for_note(max_note)
                    min_group = group_for_note(min_note)
                    
                    # 统计超限数量
                    above_83_count = len([note for note in note_values if note > 83])
                    below_48_count = len([note for note in note_values if note < 48])
                    
                    # 最高音超限判定
                    max_over_limit = max_note > 83
                    max_status = "已超限" if max_over_limit else "未超限"
                    
                    # 最低音超限判定
                    min_over_limit = min_note < 48
                    min_status = "已超限" if min_over_limit else "未超限"
                
                out = {
                    'ok': True,
                    'notes': notes,
                    'channels': channels,
                    'resolution': int(getattr(midi_obj, 'ticks_per_beat', 480) or 480),
                    'initial_tempo': initial_tempo,
                    'end_time': end_time if end_time > 0 else (notes[-1]['end_time'] if notes else 0.0),
                    'total_notes': len(notes),
                    'source': 'miditoolkit',
                    'max_note': max_note,
                    'min_note': min_note,
                    'max_group': max_group,
                    'min_group': min_group,
                    'max_status': max_status,
                    'min_status': min_status,
                    'above_83_count': above_83_count,
                    'below_48_count': below_48_count,
                }
                try:
                    print(f"[DEBUG] 解析完成: source=miditoolkit, total_notes={out['total_notes']}, end_time={out['end_time']:.3f}s")
                except Exception:
                    pass
                return out
        except Exception:
            # 失败则继续走 auto 路径
            pass

    # 其余情况统一走 auto（pretty_midi 优先，失败/异常回退 miditoolkit，并内置一致性校验）
    pm_ok = False
    try:
        if pretty_midi is not None:
            pm_data = pretty_midi.PrettyMIDI(file_path)
            notes = _gather_notes(pm_data)
            channels = sorted({n['channel'] for n in notes}) if notes else []
            # pretty_midi.get_tempo_changes() -> (times, tempi[BPM])
            tempo_changes = pm_data.get_tempo_changes()
            times_arr = tempo_changes[0] if len(tempo_changes) > 0 else []
            tempi_arr = tempo_changes[1] if len(tempo_changes) > 1 else []
            initial_tempo = float(tempi_arr[0]) if len(tempi_arr) > 0 else 120.0
            end_time = pm_data.get_end_time()

            # 当同一时刻（t≈0）存在多个 set_tempo 时，优先采用更慢的起始BPM（对齐旧版感知），
            # 并将事件的绝对秒时间进行全局缩放，使整体时长贴近旧版。
            applied_initial_tempo_scale = False
            try:
                zero_bpms = [float(tempi_arr[i]) for i, t in enumerate(times_arr) if float(t) <= 1e-9]
                if zero_bpms:
                    desired_bpm = min(zero_bpms)  # 更慢的BPM
                    current_bpm = float(initial_tempo)
                    if desired_bpm > 0 and current_bpm > 0 and desired_bpm < (current_bpm - 1e-6):
                        scale = current_bpm / desired_bpm  # >1 放慢
                        # 缩放所有音符时间与时长
                        for e in notes:
                            st = float(e.get('start_time', 0.0)) * scale
                            et = float(e.get('end_time', st)) * scale
                            e['start_time'] = st
                            e['end_time'] = et
                            e['duration'] = max(0.0, et - st)
                        # 更新初始BPM与总时长
                        initial_tempo = desired_bpm
                        end_time = float(end_time) * scale if end_time else (notes[-1]['end_time'] if notes else 0.0)
                        applied_initial_tempo_scale = True
            except Exception:
                # 任何异常下维持原pretty_midi时序
                pass

            # 若 pretty_midi 未暴露同刻多tempo（zero_bpms仅1个或为空），尝试用 mido 探测 tick=0 的多 tempo 冲突
            if not applied_initial_tempo_scale:
                try:
                    import mido  # type: ignore
                    mf = mido.MidiFile(file_path)
                    # 收集所有轨道的绝对tick，并抓取 tick==0 的 set_tempo（微秒/拍）
                    tempos_at_zero: list[int] = []
                    for track in mf.tracks:
                        tick = 0
                        for msg in track:
                            tick += msg.time
                            if getattr(msg, 'type', None) == 'set_tempo':
                                if tick == 0:
                                    try:
                                        tempos_at_zero.append(int(msg.tempo))
                                    except Exception:
                                        pass
                            # 避免遍历整首，超过少量事件后可跳出（性能优化）
                            if tick > 0 and len(tempos_at_zero) >= 2:
                                break
                        if len(tempos_at_zero) >= 2:
                            break
                    if tempos_at_zero:
                        # 将微秒/拍转换为 BPM：60_000_000 / tempo
                        bpms = [60_000_000.0 / max(1, t) for t in tempos_at_zero]
                        desired_bpm2 = min(bpms)
                        current_bpm2 = float(initial_tempo)
                        if desired_bpm2 > 0 and current_bpm2 > 0 and desired_bpm2 < (current_bpm2 - 1e-6):
                            scale2 = current_bpm2 / desired_bpm2
                            for e in notes:
                                st = float(e.get('start_time', 0.0)) * scale2
                                et = float(e.get('end_time', st)) * scale2
                                e['start_time'] = st
                                e['end_time'] = et
                                e['duration'] = max(0.0, et - st)
                            initial_tempo = desired_bpm2
                            end_time = float(end_time) * scale2 if end_time else (notes[-1]['end_time'] if notes else 0.0)
                            applied_initial_tempo_scale = True
                except Exception:
                    pass
            if notes and end_time > 0:
                # 可选一致性校验：与 miditoolkit 对比若差异过大则回退
                try:
                    if miditoolkit is not None and not applied_initial_tempo_scale:
                        midi_obj = miditoolkit.midi.parser.MidiFile(file_path)
                        mk_notes: List[Dict[str, Any]] = []
                        for ti, inst in enumerate(midi_obj.instruments):
                            is_drum = bool(getattr(inst, 'is_drum', False))
                            program = int(getattr(inst, 'program', 0) or 0)
                            name = str(getattr(inst, 'name', '') or f"Instrument_{ti}")
                            for note in inst.notes:
                                mk_notes.append({
                                    'start_time': float(note.start),
                                    'end_time': float(note.end),
                                    'duration': max(0.0, float(note.end) - float(note.start)),
                                    'note': int(note.pitch),
                                    'velocity': int(note.velocity),
                                    'channel': 9 if is_drum else ti,
                                    'track': ti,
                                    'program': program,
                                    'instrument_name': name,
                                    'is_drum': is_drum,
                                    'group': group_for_note(int(note.pitch)),
                                })
                        mk_notes.sort(key=lambda x: x['start_time'])
                        # 取前N条比对时间差
                        N = min(200, len(notes), len(mk_notes))
                        max_ds = 0.0
                        max_de = 0.0
                        for i in range(N):
                            ds = abs(float(notes[i]['start_time']) - float(mk_notes[i]['start_time']))
                            de = abs(float(notes[i]['end_time']) - float(mk_notes[i]['end_time']))
                            if ds > max_ds:
                                max_ds = ds
                            if de > max_de:
                                max_de = de
                        # 阈值：>50ms 认为不一致，优先采用 miditoolkit
                        if max_ds > 0.05 or max_de > 0.05:
                            print(f"[DEBUG] pretty_midi 时序与 miditoolkit 差异过大(max_ds={max_ds:.3f}, max_de={max_de:.3f})，回退到 miditoolkit 结果")
                            channels_mk = sorted({n['channel'] for n in mk_notes}) if mk_notes else []
                            return {
                                'ok': True,
                                'notes': mk_notes,
                                'channels': channels_mk,
                                'resolution': int(getattr(midi_obj, 'ticks_per_beat', 480) or 480),
                                'initial_tempo': float(midi_obj.tempo_changes[0].tempo) if getattr(midi_obj, 'tempo_changes', None) else 120.0,
                                'end_time': mk_notes[-1]['end_time'] if mk_notes else 0.0,
                                'total_notes': len(mk_notes),
                                'source': 'miditoolkit',
                            }
                except Exception:
                    # 校验失败不影响正常返回
                    pass
                pm_ok = True
                out = {
                    'ok': True,
                    'notes': notes,
                    'channels': channels,
                    'resolution': pm_data.resolution,
                    'initial_tempo': initial_tempo,
                    'end_time': end_time,
                    'total_notes': len(notes),
                    'source': 'pretty_midi',
                }
                try:
                    print(f"[DEBUG] 解析完成: source=pretty_midi, total_notes={out['total_notes']}, end_time={out['end_time']:.3f}s")
                except Exception:
                    pass
                return out
    except Exception as e:
        # 打印调试信息但继续尝试回退
        print(f"[DEBUG] pretty_midi解析失败，尝试回退: {e}")

    # 回退到 miditoolkit
    try:
        if miditoolkit is None:
            return {'ok': False, 'error': '解析失败：pretty_midi异常且未安装miditoolkit（pip install miditoolkit）'}
        midi_obj = miditoolkit.midi.parser.MidiFile(file_path)
        notes: List[Dict[str, Any]] = []
        # 采集 tempo（BPM）与 end_time
        try:
            if midi_obj.tempo_changes:
                initial_tempo = float(midi_obj.tempo_changes[0].tempo)
            else:
                initial_tempo = 120.0
        except Exception:
            initial_tempo = 120.0
        try:
            end_time = float(midi_obj.max_tick) * (60.0 / (initial_tempo * float(midi_obj.ticks_per_beat))) if midi_obj.ticks_per_beat else 0.0
        except Exception:
            end_time = 0.0

        # 遍历乐器/轨道
        for ti, inst in enumerate(midi_obj.instruments):
            is_drum = bool(getattr(inst, 'is_drum', False))
            program = int(getattr(inst, 'program', 0) or 0)
            name = str(getattr(inst, 'name', '') or f"Instrument_{ti}")
            for note in inst.notes:
                try:
                    # miditoolkit 的时间是 tick 基于 tempo_map 归一到秒，可直接用 start/end（秒）
                    st = float(note.start)
                    et = float(note.end)
                    dur = max(0.0, et - st)
                    pitch = int(note.pitch)
                    velocity = int(note.velocity)
                    channel = 9 if is_drum else ti
                    rec = {
                        'start_time': st,
                        'end_time': et,
                        'duration': dur,
                        'note': pitch,
                        'velocity': velocity,
                        'channel': channel,
                        'track': ti,
                        'program': program,
                        'instrument_name': name,
                        'is_drum': is_drum,
                    }
                    rec['group'] = group_for_note(rec['note'])
                    notes.append(rec)
                except Exception:
                    continue
        notes.sort(key=lambda x: x['start_time'])
        channels = sorted({n['channel'] for n in notes}) if notes else []
        return {
            'ok': True,
            'notes': notes,
            'channels': channels,
            'resolution': int(getattr(midi_obj, 'ticks_per_beat', 480) or 480),
            'initial_tempo': initial_tempo,
            'end_time': end_time if end_time > 0 else (notes[-1]['end_time'] if notes else 0.0),
            'total_notes': len(notes),
            'source': 'miditoolkit',
        }
    except Exception as e:
        return {'ok': False, 'error': f'解析MIDI失败（回退miditoolkit也失败）: {str(e)}'}


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
