# -*- coding: utf-8 -*-
"""
PreviewController: 处理试听控制器
- 负责协调电子琴页面与PreviewService之间的交互
- 提供处理试听功能的UI和逻辑支持
"""
from __future__ import annotations
from typing import Any, Optional, Callable
import os

from meowauto.app.services.preview_service import PreviewService, get_preview_service

class PreviewController:
    """处理试听控制器：负责页面到PreviewService的桥接。"""

    def __init__(self, app: Any = None, service: Optional[PreviewService] = None):
        self.app = app  # 主应用实例引用
        self.service = service or get_preview_service(logger=getattr(app, 'logger', None))
        self.is_previewing = False  # 试听状态标志
        self.current_midi_path = None  # 当前试听的MIDI文件路径
        self.settings = {
            'tempo': 1.0,  # 默认速度
            'volume': 0.7,  # 默认音量
            'use_analyzed': True,  # 默认使用已解析的数据
        }
        self.current_instrument = "电子琴"  # 用于识别乐器类型
        self.preview_button = None  # 试听按钮引用

    def init_preview_service(self) -> None:
        """初始化PreviewService"""
        try:
            self.service.init_processor()
        except Exception as e:
            self._log_message(f"初始化PreviewService失败: {e}", "ERROR")

    def toggle_preview(self) -> None:
        """切换试听状态：开始或停止试听"""
        if self.is_previewing:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self) -> bool:
        """开始处理试听"""
        try:
            # 确保应用实例和文件路径存在
            if not self.app or not hasattr(self.app, 'midi_path_var'):
                self._log_message("无法获取MIDI文件路径", "ERROR")
                return False

            # 获取MIDI文件路径
            midi_path = self.app.midi_path_var.get()
            if not midi_path or not os.path.exists(midi_path):
                self._log_message("MIDI文件不存在或未选择", "ERROR")
                return False

            # 获取当前设置
            tempo = self._get_tempo_value()
            volume = self.settings.get('volume', 0.7)
            use_analyzed = self.settings.get('use_analyzed', True)
            analyzed_notes = None
            analysis_file = None

            # 尝试获取已解析的音符数据
            if use_analyzed:
                try:
                    analyzed_notes = getattr(self.app, 'analysis_notes', None)
                    analysis_file = getattr(self.app, 'analysis_file', None)
                    # 检查解析文件是否与当前文件匹配
                    if analysis_file and os.path.abspath(analysis_file) != os.path.abspath(midi_path):
                        self._log_message(f"解析文件不匹配: {analysis_file} vs {midi_path}", "WARNING")
                        analyzed_notes = None
                except Exception as e:
                    self._log_message(f"获取解析数据时出错: {e}", "ERROR")
                    analyzed_notes = None

            # 配置分析设置（从主应用获取）
            try:
                self._apply_analysis_settings()
            except Exception as e:
                self._log_message(f"应用分析设置时出错: {e}", "WARNING")

            # 定义回调函数
            def on_progress(progress):
                """进度回调"""
                try:
                    self._update_preview_progress(progress)
                except Exception:
                    pass

            def on_complete():
                """完成回调"""
                try:
                    self._on_preview_complete()
                except Exception:
                    pass

            def on_error(error_msg):
                """错误回调"""
                try:
                    self._log_message(f"试听错误: {error_msg}", "ERROR")
                    self._reset_preview_state()
                except Exception:
                    pass

            # 开始试听
            success = self.service.process_and_preview_midi(
                midi_path,
                tempo=tempo,
                volume=volume,
                use_analyzed=use_analyzed and analyzed_notes is not None,
                analyzed_notes=analyzed_notes,
                on_progress=on_progress,
                on_complete=on_complete,
                on_error=on_error
            )

            if success:
                self.is_previewing = True
                self.current_midi_path = midi_path
                self._update_preview_button_state()
                file_name = os.path.basename(midi_path)
                self._log_message(f"开始处理试听: {file_name}", "SUCCESS")
                self._update_status(f"处理试听中: {file_name}")
            else:
                self.is_previewing = False
                self.current_midi_path = None
                self._log_message("处理试听失败", "ERROR")

            return success
        except Exception as e:
            self._log_message(f"开始试听时发生错误: {str(e)}", "ERROR")
            self.is_previewing = False
            self.current_midi_path = None
            return False

    def stop_preview(self) -> None:
        """停止当前的试听播放"""
        try:
            self.service.stop_preview()
            self._reset_preview_state()
            self._log_message("处理试听已停止", "INFO")
        except Exception as e:
            self._log_message(f"停止试听时出错: {e}", "ERROR")
            self._reset_preview_state()

    def _reset_preview_state(self) -> None:
        """重置试听状态"""
        self.is_previewing = False
        self.current_midi_path = None
        self._update_preview_button_state()

    def _get_tempo_value(self) -> float:
        """获取当前速度值"""
        try:
            # 优先从应用实例获取
            if self.app and hasattr(self.app, 'tempo_var'):
                return float(self.app.tempo_var.get())
            # 否则返回默认值
            return self.settings.get('tempo', 1.0)
        except Exception:
            return self.settings.get('tempo', 1.0)

    def _apply_analysis_settings(self) -> None:
        """应用分析设置"""
        try:
            if not self.app:
                return

            # 提取自动移调设置
            auto_transpose = False
            manual_k = 0
            min_ms = 0

            if hasattr(self.app, 'auto_transpose_enabled_var'):
                auto_transpose = bool(self.app.auto_transpose_enabled_var.get())
            if hasattr(self.app, 'manual_transpose_semi_var'):
                manual_k = int(self.app.manual_transpose_semi_var.get())
            if hasattr(self.app, 'min_note_duration_ms_var'):
                min_ms = int(self.app.min_note_duration_ms_var.get())

            # 配置分析设置
            self.service.configure_analysis_settings(
                auto_transpose=auto_transpose,
                manual_semitones=manual_k,
                min_note_duration_ms=min_ms
            )

            # 记录日志
            self._log_message(f"已配置分析设置: auto_transpose={auto_transpose}, manual_k={manual_k}, min_ms={min_ms}", "DEBUG")
        except Exception:
            pass

    def _update_preview_button_state(self) -> None:
        """更新试听按钮状态"""
        try:
            if self.preview_button:
                if self.is_previewing:
                    self.preview_button.configure(text="停止试听", state="normal")
                else:
                    self.preview_button.configure(text="处理试听", state="normal")
        except Exception:
            pass

    def _update_preview_progress(self, progress: float) -> None:
        """更新试听进度"""
        try:
            # 可以在这里更新UI进度条或状态显示
            # 由于不同页面的进度显示方式可能不同，这里提供基本实现
            if hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.set_status(f"处理试听中... {progress:.1f}%")
        except Exception:
            pass

    def _on_preview_complete(self) -> None:
        """试听完成处理"""
        try:
            self.is_previewing = False
            self.current_midi_path = None
            self._update_preview_button_state()
            self._log_message("处理试听已完成", "INFO")
            self._update_status("就绪")
        except Exception:
            pass

    def _log_message(self, message: str, level: str = "INFO") -> None:
        """记录日志"""
        try:
            if self.app and hasattr(self.app, '_log_message'):
                self.app._log_message(message, level)
        except Exception:
            # 如果无法使用应用的日志功能，则简单打印
            print(f"[{level}] {message}")

    def _update_status(self, status: str) -> None:
        """更新状态显示"""
        try:
            if self.app and hasattr(self.app, 'ui_manager'):
                self.app.ui_manager.set_status(status)
        except Exception:
            pass

    def get_preview_status(self) -> dict:
        """获取当前试听状态"""
        return {
            'is_previewing': self.is_previewing,
            'current_midi_path': self.current_midi_path,
            'service_status': self.service.get_preview_status() if self.service else {},
            'settings': self.settings.copy()
        }

    def set_preview_button(self, button: Any) -> None:
        """设置试听按钮引用"""
        self.preview_button = button
        self._update_preview_button_state()

    def configure_settings(self, **kwargs) -> None:
        """配置控制器设置"""
        for key, value in kwargs.items():
            if key in self.settings:
                self.settings[key] = value
        self._log_message(f"已更新控制器设置: {self.settings}", "DEBUG")

    def cleanup(self) -> None:
        """清理资源"""
        try:
            if self.is_previewing:
                self.stop_preview()
        except Exception:
            pass

# 单例模式支持
_preview_controller_instance = None

def get_preview_controller(app: Optional[Any] = None) -> PreviewController:
    """获取PreviewController的单例实例"""
    global _preview_controller_instance
    if _preview_controller_instance is None:
        _preview_controller_instance = PreviewController(app)
    return _preview_controller_instance