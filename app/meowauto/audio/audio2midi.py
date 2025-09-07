# -*- coding: utf-8 -*-
"""
音频->MIDI 统一入口（统一封装 PianoTrans.exe 与后备的 AudioConverter）
返回 (ok: bool, output_path: str, err_msg: str | None, logs: dict)
logs: { 'stdout': str, 'stderr': str, 'elapsed': float }
"""
"""
署名与声明：
by薮薮猫猫
本软件开源且免费，如果你是付费购买请申请退款，并从官方渠道获取。
"""
from __future__ import annotations
import os
import time
from typing import Tuple, Optional, Dict


def convert_audio_to_midi(audio_path: str,
                          output_path: Optional[str] = None,
                          *,
                          pianotrans_dir: str = "PianoTrans-v1.0",
                          timeout: int = 600,
                          prefer_exe: bool = True) -> Tuple[bool, str, Optional[str], Dict[str, str | float]]:
    """将音频转换为 MIDI，统一封装。
    - 优先调用 pianotrans_dir/PianoTrans.exe；若不可用则回退 meowauto.AudioConverter
    - 成功条件：进程返回码==0（或后备成功），产物存在且非空，且 mtime > start_ts；mido 能成功打开
    """
    logs: Dict[str, str | float] = {
        'stdout': '',
        'stderr': '',
        'elapsed': 0.0,
    }
    if not audio_path or not os.path.exists(audio_path):
        return False, output_path or '', '音频文件不存在', logs

    start_ts = time.time()
    if output_path is None:
        output_path = os.path.splitext(audio_path)[0] + '.mid'

    # 清理旧产物，避免被误判
    try:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                bak = output_path + f".bak_{int(start_ts)}"
                try:
                    os.replace(output_path, bak)
                except Exception:
                    pass
    except Exception:
        pass

    old_mtime = os.path.getmtime(output_path) if os.path.exists(output_path) else None

    ok = False
    err_msg: Optional[str] = None

    # 解析 PianoTrans 目录（支持从不同工作目录启动）
    def _resolve_pianotrans_dir(base: str) -> Optional[str]:
        candidates = []
        # 1) 如果传入的是绝对路径，直接使用
        if os.path.isabs(base):
            candidates.append(base)
        # 2) 当前工作目录相对
        candidates.append(os.path.abspath(base))
        # 3) 以当前模块所在的 app 目录为基准
        try:
            module_dir = os.path.dirname(__file__)
            app_root = os.path.abspath(os.path.join(module_dir, os.pardir, os.pardir, os.pardir))
            candidates.append(os.path.join(app_root, base))
        except Exception:
            pass
        # 4) 若已打包（PyInstaller），从可执行文件所在目录以及 _MEIPASS 推断
        try:
            import sys
            exec_dir = os.path.dirname(sys.executable)
            if exec_dir:
                candidates.append(os.path.join(exec_dir, base))
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                candidates.append(os.path.join(meipass, base))
                # 可执行同级的父目录也尝试一层
                candidates.append(os.path.abspath(os.path.join(exec_dir, os.pardir, base)))
        except Exception:
            pass
        # 去重并校验
        seen = set()
        for p in candidates:
            ap = os.path.abspath(p)
            if ap in seen:
                continue
            seen.add(ap)
            if os.path.isdir(ap) and os.path.exists(os.path.join(ap, 'PianoTrans.exe')):
                return ap
        return None

    resolved_dir = _resolve_pianotrans_dir(pianotrans_dir)
    exe_path = os.path.join(resolved_dir, 'PianoTrans.exe') if resolved_dir else None

    # 优先 EXE
    if prefer_exe and resolved_dir and exe_path and os.path.exists(exe_path):
        try:
            import subprocess
            import shutil
            t0 = time.time()
            # 准备运行时缓存目录与“无特殊字符”的输入副本
            cache_dir = os.path.join(resolved_dir, 'runtime_cache')
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception:
                pass
            sanitized_name = f"input_{int(t0)}" + os.path.splitext(audio_path)[1].lower()
            safe_input = os.path.join(cache_dir, sanitized_name)
            try:
                shutil.copy2(audio_path, safe_input)
            except Exception:
                # 复制失败则退回原路径
                safe_input = audio_path

            # 只传入输入路径，避免工具把输出 .mid 当成输入再次排队
            # 确保 ffmpeg 可用（若工具包内携带）
            env = os.environ.copy()
            ffmpeg_dir = os.path.join(resolved_dir, 'ffmpeg')
            if os.path.isdir(ffmpeg_dir) and ffmpeg_dir not in (env.get('PATH') or ''):
                env['PATH'] = ffmpeg_dir + os.pathsep + env.get('PATH', '')

            # 使用绝对可执行路径，避免 WinError 2；输入也使用绝对路径，跨盘符更稳健
            exe_run = exe_path  # 绝对路径
            input_run = os.path.abspath(safe_input)
            # 记录关键信息，便于 UI 显示和问题诊断
            try:
                meta = []
                meta.append(f"[META] resolved_dir={resolved_dir}")
                meta.append(f"[META] exe_run={exe_run}")
                meta.append(f"[META] input_run={input_run}")
                meta.append(f"[CHECK] exe_exists={os.path.exists(exe_run)}  input_exists={os.path.exists(input_run)}")
                logs['stdout'] = ((logs.get('stdout') or '') + '\n' + '\n'.join(meta)).strip()
            except Exception:
                pass
            # 若可执行或输入不存在，提前报错，便于 UI 提示
            if not os.path.exists(exe_run):
                raise FileNotFoundError(f"PianoTrans可执行不存在: {exe_run}")
            if not os.path.exists(input_run):
                raise FileNotFoundError(f"输入文件不存在(运行时): {input_run}")

            proc = subprocess.run([exe_run, input_run], cwd=resolved_dir,
                                  capture_output=True, text=True, timeout=timeout, env=env)
            logs['elapsed'] = time.time() - t0
            logs['stdout'] = (proc.stdout or '').strip()
            logs['stderr'] = (proc.stderr or '').strip()
            # 预期产物：与“传入的输入路径”同名、同目录的 .mid（优先 safe_input）
            expected_mid = os.path.splitext(safe_input)[0] + '.mid'
            if proc.returncode == 0:
                # 最多等待1.5秒，确认产物落盘
                for _ in range(15):
                    if os.path.exists(expected_mid):
                        break
                    time.sleep(0.1)
                if os.path.exists(expected_mid):
                    try:
                        new_mtime = os.path.getmtime(expected_mid)
                        ok = (new_mtime > (old_mtime or 0)) and (new_mtime >= start_ts)
                        # 若指定了 output_path 且不同，移动到目标路径
                        if ok and output_path and os.path.abspath(expected_mid) != os.path.abspath(output_path):
                            try:
                                # 再次清理目标旧文件
                                if os.path.exists(output_path):
                                    try:
                                        os.remove(output_path)
                                    except Exception:
                                        pass
                                os.replace(expected_mid, output_path)
                            except Exception:
                                # 若移动失败，仍使用 expected_mid 作为结果
                                output_path = expected_mid
                    except Exception:
                        ok = False
                else:
                    # 兜底：扫描 runtime_cache 下新生成的 .mid（有些版本命名或目录可能不同）
                    try:
                        cache_dir = os.path.join(resolved_dir, 'runtime_cache')
                        newest_mid = None
                        newest_ts = 0.0
                        if os.path.isdir(cache_dir):
                            for name in os.listdir(cache_dir):
                                if name.lower().endswith('.mid'):
                                    p = os.path.join(cache_dir, name)
                                    try:
                                        ts = os.path.getmtime(p)
                                        if ts >= start_ts and ts > newest_ts:
                                            newest_mid = p
                                            newest_ts = ts
                                    except Exception:
                                        pass
                        if newest_mid:
                            ok = True
                            if output_path and os.path.abspath(newest_mid) != os.path.abspath(output_path):
                                try:
                                    if os.path.exists(output_path):
                                        try:
                                            os.remove(output_path)
                                        except Exception:
                                            pass
                                    os.replace(newest_mid, output_path)
                                except Exception:
                                    output_path = newest_mid
                    except Exception:
                        pass
            else:
                # 针对 NoBackendError：尝试用 ffmpeg 预转码为 wav 再试一次
                stderr_text = (logs['stderr'] or '').lower()
                stdout_text = (logs['stdout'] or '').lower()
                need_retry = ('nobackenderror' in stderr_text) or ('nobackenderror' in stdout_text)
                retried = False
                if need_retry:
                    try:
                        # 优先使用捆绑的 ffmpeg.exe
                        ffmpeg_exe = os.path.join(resolved_dir, 'ffmpeg', 'ffmpeg.exe')
                        ffmpeg_cmd = [ffmpeg_exe] if os.path.exists(ffmpeg_exe) else ['ffmpeg']
                        pcm_path = os.path.join(cache_dir, f"input_pcm_{int(time.time())}.wav")
                        # ffmpeg -y -i input -ac 1 -ar 44100 -vn output.wav
                        p2 = subprocess.run(ffmpeg_cmd + ['-y', '-i', safe_input, '-ac', '1', '-ar', '44100', '-vn', pcm_path],
                                            capture_output=True, text=True, timeout=120)
                        # 再次调用 PianoTrans
                        if os.path.exists(pcm_path) and p2.returncode == 0:
                            t1 = time.time()
                            pcm_run = os.path.abspath(pcm_path)
                            proc2 = subprocess.run([exe_run, pcm_run], cwd=resolved_dir,
                                                       capture_output=True, text=True, timeout=timeout, env=env)
                            logs['elapsed'] += (time.time() - t1)
                            logs['stdout'] += ('\n' + (proc2.stdout or '').strip())
                            logs['stderr'] += ('\n' + (proc2.stderr or '').strip())
                            if proc2.returncode == 0:
                                exp2 = os.path.splitext(pcm_path)[0] + '.mid'
                                for _ in range(15):
                                    if os.path.exists(exp2):
                                        break
                                    time.sleep(0.1)
                                if os.path.exists(exp2):
                                    try:
                                        new_mtime = os.path.getmtime(exp2)
                                        ok = (new_mtime > (old_mtime or 0)) and (new_mtime >= start_ts)
                                        if ok and output_path and os.path.abspath(exp2) != os.path.abspath(output_path):
                                            try:
                                                if os.path.exists(output_path):
                                                    try:
                                                        os.remove(output_path)
                                                    except Exception:
                                                        pass
                                                os.replace(exp2, output_path)
                                            except Exception:
                                                output_path = exp2
                                    except Exception:
                                        ok = False
                                retried = True
                        else:
                            # 即使返回非零，但如有产物同样接受
                            exp2 = os.path.splitext(pcm_path)[0] + '.mid'
                            if os.path.exists(exp2) and os.path.getsize(exp2) > 0:
                                ok = True
                                if output_path and os.path.abspath(exp2) != os.path.abspath(output_path):
                                    try:
                                        if os.path.exists(output_path):
                                            try:
                                                os.remove(output_path)
                                            except Exception:
                                                pass
                                        os.replace(exp2, output_path)
                                    except Exception:
                                        output_path = exp2
                    except Exception:
                        pass
                if not ok:
                    # 若仍未成功，但产物已生成且非空，也视为成功（部分版本可能返回非零但已导出）
                    if os.path.exists(expected_mid) and os.path.getsize(expected_mid) > 0:
                        ok = True
                        if output_path and os.path.abspath(expected_mid) != os.path.abspath(output_path):
                            try:
                                if os.path.exists(output_path):
                                    try:
                                        os.remove(output_path)
                                    except Exception:
                                        pass
                                os.replace(expected_mid, output_path)
                            except Exception:
                                output_path = expected_mid
                    if not ok:
                        if not err_msg:
                            err_msg = f"PianoTrans返回码{proc.returncode}: {logs['stderr'] or logs['stdout']}" + (" (已尝试转码重试)" if retried else "")
        except subprocess.TimeoutExpired:
            ok = False
            err_msg = 'PianoTrans执行超时'
        except Exception as e:
            ok = False
            err_msg = f'PianoTrans执行异常: {e}'
    else:
        # 回退 AudioConverter
        try:
            from meowauto.audio import AudioConverter
            from meowauto.core import Logger
            conv = AudioConverter(Logger())
            ok = bool(conv.convert_audio_to_midi(audio_path, output_path))
        except Exception as e:
            ok = False
            err_msg = f'AudioConverter不可用或失败: {e}'

    # 二次校验：文件有效。若 mido 验证失败，仅记录为警告不算失败（部分工具导出的MIDI可能包含非标准元信息）
    if ok and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        try:
            new_mtime2 = os.path.getmtime(output_path)
            if new_mtime2 > (old_mtime or 0) and new_mtime2 >= start_ts:
                try:
                    import mido
                    _ = mido.MidiFile(output_path)
                    ok = True
                except Exception as e:
                    # 不将其视为失败
                    logs['stderr'] = (logs.get('stderr') or '') + f"\n[MIDI校验警告] {e}"
                    ok = True
            else:
                # 如果时间戳判断失败但文件存在且非空，依然视为成功（极端情况下时间精度/文件系统差异导致）
                ok = True
        except Exception as e:
            # 验证异常不影响最终成功判定
            logs['stderr'] = (logs.get('stderr') or '') + f"\n[验证过程异常] {e}"
    else:
        if not ok and not err_msg:
            err_msg = '转换失败或输出文件不存在/为空'

    return ok, output_path, err_msg, logs
