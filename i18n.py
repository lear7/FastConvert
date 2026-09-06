#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast Convert i18n - 多语言国际化支持模块。

@author Gemini 3.8 Flash @date 2026-09-03
"""

from __future__ import annotations

import locale
import sys
from typing import Any
from PySide6.QtCore import QObject, Signal, QLocale

SUPPORTED_LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh_CN": {
        "app_title": "闪电转换",
        "window_title": "闪电转换 v{version}",
        "working_dir": "工作目录",
        "dir_placeholder": "选择包含视频的文件夹，或直接拖入视频",
        "browse": "浏览",
        "switch_lang": "切换语言",
        "mode": "工作模式",
        "mode_convert": "转码",
        "mode_compress": "压缩",
        "mode_remux": "重封",
        "hint_convert": "转码非 MP4 视频为 MP4，支持按需缩小分辨率",
        "hint_compress": "已有 MP4 二次重编码压缩，调大 CRF 或缩放可减小体积",
        "hint_remux": "流复制极速重封装为 MP4，不重新编码音视频",
        "param_remux": "重封模式直接复制音视频流，不使用画质与缩放参数",
        "param_crf": "CRF 越低画质越高 (推荐 18–23)",
        "crf": "CRF",
        "scale": "缩放",
        "threads": "线程",
        "speed": "速度",
        "preset_ultrafast": "极速 (最快)",
        "preset_superfast": "超快",
        "preset_veryfast": "快速 (推荐)",
        "preset_faster": "较快",
        "preset_fast": "标准",
        "preset_medium": "高质量",
        "scale_orig": "原尺寸",
        "scale_p75": "75%",
        "scale_p50": "50%",
        "scale_1080": "1080p",
        "scale_720": "720p",
        "scale_480": "480p",
        "drop_title_empty": "拖入视频或文件夹",
        "drop_sub_empty": "点击此处也可手动选文件",
        "drop_title_active": "松开以添加文件",
        "drop_title_has_files": "已选 {count} 个",
        "drop_clear": "清空",
        "log_caption": "运行日志",
        "btn_start_convert": "开始转码",
        "btn_start_compress": "开始压缩",
        "btn_start_remux": "开始重封",
        "btn_cancel": "取消任务",
        "btn_close": "关闭",
        "perf_idle": "CPU {cpu}%  内存 {mem}",
        "perf_tooltip_header": "【程序资源占用（主进程及转码子进程）】",
        "perf_tooltip_cpu": "总 CPU: {cpu}% (系统折算，等效单核 {raw}%)",
        "perf_tooltip_mem": "总内存: {mem}",
        "perf_tooltip_details": "进程明细:",
        "perf_tooltip_sys_header": "【系统整体资源概况】",
        "perf_tooltip_sys_cpu": "系统 CPU 使用率: {cpu}%",
        "perf_tooltip_sys_mem": "系统物理内存使用: {pct}% ({used} GB / {total} GB)",
        "perf_main_proc": "主程序",
        "perf_child_proc": "子进程 ({name})",
        "lang_dialog_title": "选择语言",
        "lang_zh": "简体中文",
        "lang_en": "English",
        "btn_ok": "确定",
        "btn_cancel_dialog": "取消",
        "msg_ffmpeg_missing_title": "FFmpeg 缺失",
        "msg_ffmpeg_missing_text": "未找到 FFmpeg 运行时:\n{path}\n请确认 resources/tools/ffmpeg/bin/ffmpeg.exe 是否存在。",
        "msg_workdir_warning_title": "工作目录",
        "msg_workdir_warning_text": "请先选择有效的工作目录，或从右侧拖入视频文件。",
        "log_batch_start": "开始批量处理，共 {count} 个文件…",
        "log_batch_done": "所有任务已完成！成功 {s}，失败 {f}，总耗时 {elapsed}",
        "log_cancelling": "正在取消…",
        "log_cancelled": "任务已取消，总耗时 {elapsed}。",
        "file_hint_count": "已选 {count} 个待转换视频",
        "file_hint_empty": "请选择目录或拖拽添加要转换的视频",
        "log_added_files": "已添加 {added} 个视频，当前共 {total} 个{extra}",
        "log_ignored_files": "，忽略 {ignored} 个非视频",
        "log_no_videos": "当前目录未发现待处理的视频文件，请拖入视频或更换目录。",
        "eta_estimating": "正在预估剩余时间…",
        "eta_single": "预计剩余 {eta} ({pct}%)",
        "eta_batch": "[{curr}/{total}] 预计剩余 {eta} ({pct}%)",
        "eta_tooltip_header": "【转码进度与剩余预估】",
        "eta_tooltip_file": "当前文件: {name}",
        "eta_tooltip_progress": "完成进度: {pct}% ({curr_time} / {total_time})",
        "eta_tooltip_speed": "当前速率: {speed}x",
        "eta_tooltip_remain": "预计剩余: 约 {eta}",
    },
    "en_US": {
        "app_title": "Fast Convert",
        "window_title": "Fast Convert v{version}",
        "working_dir": "Work Dir",
        "dir_placeholder": "Select folder containing videos, or drag videos here",
        "browse": "Browse",
        "switch_lang": "Switch Language",
        "mode": "Mode",
        "mode_convert": "Convert",
        "mode_compress": "Compress",
        "mode_remux": "Remux",
        "hint_convert": "Convert non-MP4 videos to MP4; downscaling supported",
        "hint_compress": "Re-encode MP4; increase CRF or downscale to reduce size",
        "hint_remux": "Fast stream-copy remux to MP4 without re-encoding",
        "param_remux": "Remux copies streams directly; quality params disabled",
        "param_crf": "Lower CRF gives higher quality (recommended 18–23)",
        "crf": "CRF",
        "scale": "Scale",
        "threads": "Threads",
        "speed": "Speed",
        "preset_ultrafast": "Ultra Fast (Fastest)",
        "preset_superfast": "Super Fast",
        "preset_veryfast": "Very Fast (Default)",
        "preset_faster": "Faster",
        "preset_fast": "Standard",
        "preset_medium": "High Quality",
        "scale_orig": "Original",
        "scale_p75": "75%",
        "scale_p50": "50%",
        "scale_1080": "1080p",
        "scale_720": "720p",
        "scale_480": "480p",
        "drop_title_empty": "Drop videos or folders",
        "drop_sub_empty": "or click here to select files",
        "drop_title_active": "Release to add files",
        "drop_title_has_files": "{count} selected",
        "drop_clear": "Clear",
        "log_caption": "Execution Log",
        "btn_start_convert": "Start Convert",
        "btn_start_compress": "Start Compress",
        "btn_start_remux": "Start Remux",
        "btn_cancel": "Cancel Task",
        "btn_close": "Close",
        "perf_idle": "CPU {cpu}%  RAM {mem}",
        "perf_tooltip_header": "【Process Resource Usage (Main & Child Processes)】",
        "perf_tooltip_cpu": "Total CPU: {cpu}% (System normalized, equivalent single-core {raw}%)",
        "perf_tooltip_mem": "Total RAM: {mem}",
        "perf_tooltip_details": "Process Details:",
        "perf_tooltip_sys_header": "【System Overall Resources】",
        "perf_tooltip_sys_cpu": "System CPU Usage: {cpu}%",
        "perf_tooltip_sys_mem": "System RAM Usage: {pct}% ({used} GB / {total} GB)",
        "perf_main_proc": "Main Process",
        "perf_child_proc": "Child ({name})",
        "lang_dialog_title": "Select Language",
        "lang_zh": "简体中文",
        "lang_en": "English",
        "btn_ok": "OK",
        "btn_cancel_dialog": "Cancel",
        "msg_ffmpeg_missing_title": "FFmpeg Missing",
        "msg_ffmpeg_missing_text": "FFmpeg executable not found:\n{path}\nPlease make sure resources/tools/ffmpeg/bin/ffmpeg.exe exists.",
        "msg_workdir_warning_title": "Working Directory",
        "msg_workdir_warning_text": "Please select a valid working directory, or drag videos into the drop zone.",
        "log_batch_start": "Starting batch processing, total {count} files...",
        "log_batch_done": "All tasks completed! Success: {s}, Failed: {f}, Elapsed: {elapsed}",
        "log_cancelling": "Cancelling...",
        "log_cancelled": "Task cancelled, elapsed: {elapsed}.",
        "file_hint_count": "{count} video(s) ready to convert",
        "file_hint_empty": "Select a directory or drag videos here to convert",
        "log_added_files": "Added {added} video(s), total {total}{extra}",
        "log_ignored_files": ", ignored {ignored} non-video file(s)",
        "log_no_videos": "No pending video files found in the current directory. Please drop videos or change directory.",
        "eta_estimating": "Estimating ETA…",
        "eta_single": "ETA: {eta} ({pct}%)",
        "eta_batch": "[{curr}/{total}] ETA: {eta} ({pct}%)",
        "eta_tooltip_header": "【Transcoding Progress & ETA】",
        "eta_tooltip_file": "Current File: {name}",
        "eta_tooltip_progress": "Progress: {pct}% ({curr_time} / {total_time})",
        "eta_tooltip_speed": "Speed: {speed}x",
        "eta_tooltip_remain": "ETA: approx. {eta}",
    },
}


def detect_system_language() -> str:
    """自动侦测操作系统首选语言，中文环境返回 zh_CN，其余默认 en_US。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    try:
        sys_loc = QLocale.system().name()
        if sys_loc.lower().startswith("zh"):
            return "zh_CN"
    except Exception:
        pass

    try:
        default_locale = locale.getdefaultlocale()[0]
        if default_locale and default_locale.lower().startswith("zh"):
            return "zh_CN"
    except Exception:
        pass

    return "en_US"


class I18nManager(QObject):
    """全局国际化管理器。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    language_changed = Signal(str)

    def __init__(self, current_lang: str | None = None) -> None:
        super().__init__()
        if current_lang in SUPPORTED_LANGUAGES:
            self._current_lang = current_lang
        else:
            self._current_lang = detect_system_language()

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang: str) -> None:
        if lang in SUPPORTED_LANGUAGES and lang != self._current_lang:
            self._current_lang = lang
            self.language_changed.emit(lang)

    def t(self, key: str, **kwargs: Any) -> str:
        """根据 key 获取翻译并支持占位符渲染。"""
        bundle = TRANSLATIONS.get(self._current_lang, TRANSLATIONS["zh_CN"])
        pattern = bundle.get(key)
        if pattern is None:
            pattern = TRANSLATIONS["en_US"].get(key, key)
        if kwargs:
            try:
                return pattern.format(**kwargs)
            except Exception:
                return pattern
        return pattern


_i18n_instance: I18nManager | None = None


def get_i18n(initial_lang: str | None = None) -> I18nManager:
    """获取或初始化单例 I18nManager。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18nManager(initial_lang)
    elif initial_lang and initial_lang in SUPPORTED_LANGUAGES:
        _i18n_instance.set_language(initial_lang)
    return _i18n_instance


def t(key: str, **kwargs: Any) -> str:
    """快捷翻译函数。"""
    return get_i18n().t(key, **kwargs)
