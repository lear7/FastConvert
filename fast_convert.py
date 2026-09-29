#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast Convert / 闪电转换 - 轻量独立的 MP4 视频转码、压缩与重封装工具。

@author Gemini 3.8 Flash @date 2026-09-03
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from i18n import SUPPORTED_LANGUAGES, get_i18n, t

APP_NAME_EN = "Fast Convert"
APP_NAME_ZH = "闪电转换"
APP_VERSION = "1.1.2"

VIDEO_EXTS = ("rmvb", "flv", "avi", "mkv", "mov", "wmv", "ts", "webm", "m4v", "mpeg", "mpg", "3gp", "vob")
VIDEO_SCALE_KEYS = ["orig", "p75", "p50", "1080", "720", "480"]
# 精简为三档梯级清晰的速度预设：快速(推荐)、标准、高质量
VIDEO_PRESET_KEYS = ["veryfast", "fast", "medium"]
VIDEO_MODES = ["convert", "compress", "remux"]

DURATION_REGEX = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
TIME_REGEX = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
SPEED_REGEX = re.compile(r"speed=\s*([\d\.]+)x")


def app_base_dir() -> Path:
    """获取程序基准目录（支持 PyInstaller _MEIPASS 打包态与普通源码态）。"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def asset_path(name: str) -> Path:
    """定位 assets 目录下的静态资源文件。"""
    return app_base_dir() / "assets" / name


@dataclass
class Runtime:
    app_dir: Path
    ffmpeg: Path


class RuntimeManager:
    """管理 FFmpeg 等核心外部工具的定位与初始化。

    @author Gemini 3.8 Flash @date 2026-09-03
    """

    def __init__(self, app_dir: Path, logger: logging.Logger) -> None:
        self.app_dir = app_dir
        self.logger = logger

    def ensure(self) -> Runtime:
        candidates = [
            app_base_dir() / "resources" / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
            self.app_dir / "resources" / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
            self.app_dir / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path(__file__).resolve().parent.parent / "quick_start" / "resources" / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            candidates.append(Path(sys_ffmpeg))

        for cand in candidates:
            if cand.exists():
                return Runtime(self.app_dir, cand.resolve())

        # 降级返回首选路径
        return Runtime(self.app_dir, candidates[0])


class ConfigManager:
    """读取与持久化保存用户偏好设置（工作目录、参数、语言等）。

    @author Gemini 3.8 Flash @date 2026-09-03
    """

    def __init__(self, config_file: Path) -> None:
        self.path = config_file

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": APP_VERSION,
            "port": 0,
            "language": "",
            "last_working_dir": "",
            "last_video_mode": "convert",
            "last_video_crf": 20,
            "last_video_scale": "orig",
            "last_video_threads": 4,
            "last_video_preset": "veryfast",
        }
        if self.path.exists():
            try:
                content = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    data.update(content)
            except Exception as exc:
                logging.getLogger("fast_convert").warning("读取 config.json 失败: %s", exc)
        data["version"] = APP_VERSION
        return data

    def save(self, data: dict[str, Any]) -> None:
        try:
            data["version"] = APP_VERSION
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logging.getLogger("fast_convert").warning("保存 config.json 失败: %s", exc)


def apply_system_spin_style(widget: QAbstractSpinBox) -> None:
    """让 SpinBox 使用 Windows 系统原生样式绘制上下垂直小箭头。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    widget.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
    widget.setFrame(True)
    widget.setAttribute(Qt.WA_StyledBackground, False)
    widget.setStyleSheet("")
    for key in ("windows11", "windowsvista", "Windows", "Fusion"):
        style = QStyleFactory.create(key)
        if style is not None:
            widget.setStyle(style)
            break


def dialog_style() -> str:
    """专业桌面工具浅色样式：柔和中性底 + 克制主色，弱化极客终端感。"""
    return """
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    color: #1C1C1E;
    font-size: 13px;
}
QWidget#FastConvertWindow {
    background: #F4F5F7;
}
QDialog {
    background: #FFFFFF;
}
QLabel#sectionLabel {
    color: #6B7280;
    font-weight: 500;
    font-size: 12px;
}
QLabel#hintLabel {
    color: #9CA3AF;
    font-size: 12px;
}
QLineEdit {
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 5px 10px;
    background: #FFFFFF;
    min-height: 18px;
    selection-background-color: #2F6FED;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border-color: #2F6FED;
}
QPushButton {
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 5px 14px;
    background: #FFFFFF;
    color: #1C1C1E;
    font-weight: 500;
    min-height: 18px;
}
QPushButton:hover {
    background: #F9FAFB;
    border-color: #C4C9D1;
}
QPushButton:pressed {
    background: #F3F4F6;
}
QPushButton#primaryButton {
    background: #2F6FED;
    color: #FFFFFF;
    border: 1px solid #2563EB;
    padding: 6px 18px;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #3B7CF0;
    border-color: #2F6FED;
}
QPushButton#primaryButton:pressed {
    background: #2563EB;
}
QPushButton#primaryButton:disabled {
    background: #93B4F5;
    color: #FFFFFF;
    border-color: #93B4F5;
}
QPushButton#dangerButton {
    background: #FFFFFF;
    color: #DC2626;
    border: 1px solid #D1D5DB;
}
QPushButton#dangerButton:hover {
    background: #FEF2F2;
    border-color: #FECACA;
}
QPushButton#dangerButton:disabled {
    color: #9CA3AF;
    background: #F9FAFB;
    border-color: #E5E7EB;
}
QPushButton#ghostButton {
    background: transparent;
    color: #6B7280;
    border: 1px solid transparent;
}
QPushButton#ghostButton:hover {
    background: #EEF0F3;
    color: #1C1C1E;
    border-color: #E5E7EB;
}
QPushButton#langBtn {
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    background: #FFFFFF;
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#langBtn:hover {
    background: #F9FAFB;
    border-color: #2F6FED;
}
QPushButton#modeSeg, QPushButton#modeSegFirst, QPushButton#modeSegLast {
    background: #FFFFFF;
    color: #6B7280;
    border: 1px solid #D1D5DB;
    padding: 0 16px;
    min-height: 28px;
    max-height: 28px;
    font-size: 12px;
    border-radius: 0;
}
QPushButton#modeSegFirst {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
}
QPushButton#modeSegLast {
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    margin-left: -1px;
}
QPushButton#modeSeg {
    margin-left: -1px;
}
QPushButton#modeSeg:checked, QPushButton#modeSegFirst:checked, QPushButton#modeSegLast:checked {
    background: #2F6FED;
    color: #FFFFFF;
    border-color: #2F6FED;
    font-weight: 600;
}
QPushButton#modeSeg:hover:!checked, QPushButton#modeSegFirst:hover:!checked, QPushButton#modeSegLast:hover:!checked {
    background: #F9FAFB;
    color: #1C1C1E;
}
QPushButton#modeSeg:disabled, QPushButton#modeSegFirst:disabled, QPushButton#modeSegLast:disabled {
    color: #C4C9D1;
    background: #F9FAFB;
}
QComboBox {
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 3px 10px;
    background: #FFFFFF;
    min-height: 18px;
}
QComboBox:focus {
    border-color: #2F6FED;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QPushButton#langItemBtn {
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    background: #FFFFFF;
    color: #1C1C1E;
    font-size: 13px;
    font-weight: 500;
    padding: 0 12px;
    min-height: 32px;
    max-height: 32px;
    text-align: center;
}
QPushButton#langItemBtn:hover {
    background: #EFF6FF;
    border-color: #2F6FED;
    color: #2F6FED;
}
QPushButton#langItemBtn[current="true"] {
    background: #EFF6FF;
    border: 1.5px solid #2F6FED;
    color: #2F6FED;
    font-weight: 600;
}
QLabel#perfLabel {
    color: #6B7280;
    background: transparent;
    border: none;
    padding: 0 2px;
    min-height: 24px;
    max-height: 24px;
    font-size: 11px;
}
QLabel#perfLabel:hover {
    color: #1C1C1E;
}
QLabel#etaLabel {
    color: #1D4ED8;
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 8px;
    padding: 0 10px;
    min-height: 26px;
    max-height: 26px;
    font-size: 12px;
    font-weight: 500;
}
QLabel#etaLabel:hover {
    background: #DBEAFE;
    border-color: #93C5FD;
}
QLabel#fileStatusHint {
    color: #9CA3AF;
    font-size: 12px;
}
QLabel#fileStatusHint[hasFiles="true"] {
    color: #2F6FED;
    font-weight: 600;
}
QPushButton#logToggle {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    color: #4B5563;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    padding: 7px 12px;
    min-height: 20px;
}
QPushButton#logToggle:hover {
    background: #F9FAFB;
    border-color: #D1D5DB;
    color: #1C1C1E;
}
QPushButton#logToggle[expanded="true"] {
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    border-bottom-color: #EEF0F3;
    color: #1C1C1E;
}
QPushButton#logToggle[hasOutput="true"] {
    color: #2F6FED;
}
QPlainTextEdit#logView {
    background-color: #FFFFFF;
    color: #374151;
    border: 1px solid #E5E7EB;
    border-top: none;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
    padding: 8px 12px;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
    selection-background-color: #DBEAFE;
    selection-color: #1D4ED8;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 4px 2px 4px 0px;
}
QScrollBar::handle:vertical {
    background: #D1D5DB;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #9CA3AF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


class LanguageDialog(QDialog):
    """语言切换选择对话框。

    @author Gemini 3.8 Flash @date 2026-09-03
    """

    def __init__(self, current_lang: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LanguageDialog")
        self.setWindowTitle(t("lang_dialog_title"))
        self.setFixedSize(200, 98)

        # 弹窗不显示图标
        transparent_pixmap = QPixmap(16, 16)
        transparent_pixmap.fill(Qt.transparent)
        self.setWindowIcon(QIcon(transparent_pixmap))
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.CustomizeWindowHint)
        self.setStyleSheet(dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.chosen_lang = current_lang

        self.zh_btn = QPushButton(t("lang_zh"))
        self.zh_btn.setObjectName("langItemBtn")
        self.zh_btn.setCursor(Qt.PointingHandCursor)
        if current_lang == "zh_CN":
            self.zh_btn.setProperty("current", "true")
        self.zh_btn.clicked.connect(lambda: self._select_and_accept("zh_CN"))
        layout.addWidget(self.zh_btn)

        self.en_btn = QPushButton(t("lang_en"))
        self.en_btn.setObjectName("langItemBtn")
        self.en_btn.setCursor(Qt.PointingHandCursor)
        if current_lang == "en_US":
            self.en_btn.setProperty("current", "true")
        self.en_btn.clicked.connect(lambda: self._select_and_accept("en_US"))
        layout.addWidget(self.en_btn)

    def _select_and_accept(self, lang: str) -> None:
        self.chosen_lang = lang
        self.accept()

    def selected_language(self) -> str:
        return self.chosen_lang


class VideoDropZone(QFrame):
    """右侧拖放区：支持拖拽文件/文件夹及点选。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    filesDropped = Signal(object)
    pickRequested = Signal()
    clearRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("videoDropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(210)
        self.setMinimumHeight(148)

        self._dragging = False
        self._has_files = False
        self._count = 0
        self._first_name = ""
        self._busy = False

        self._build_ui()

    def _update_mark_icon(self) -> None:
        if self._has_files:
            icon_file = asset_path("drop_checked.svg")
        else:
            icon_file = asset_path("drop_tray.svg")
        if icon_file.exists():
            pm = QPixmap(str(icon_file))
            self.mark_label.setPixmap(pm)
            self.mark_label.setText("")
        else:
            self.mark_label.setText("✔" if self._has_files else "📥")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self.mark_label = QLabel()
        self.mark_label.setAlignment(Qt.AlignCenter)
        self.mark_label.setFixedHeight(30)
        self.mark_label.setStyleSheet("background:transparent;")
        layout.addWidget(self.mark_label)
        self._update_mark_icon()

        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.sub_label = QLabel()
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setWordWrap(True)
        self.sub_label.setStyleSheet("color:#9CA3AF; font-size:11px; background:transparent;")
        layout.addWidget(self.sub_label)

        self.clear_btn = QPushButton()
        self.clear_btn.setObjectName("dropClear")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setFixedHeight(22)
        self.clear_btn.setStyleSheet("""
            QPushButton#dropClear {
                background:transparent; color:#6B7280; border:1px solid #D1D5DB;
                border-radius:6px; padding:0 10px; font-size:11px;
            }
            QPushButton#dropClear:hover { background:#FEF2F2; color:#DC2626; border-color:#FECACA; }
            QPushButton#dropClear:disabled { color:#C4C9D1; border-color:#E5E7EB; }
        """)
        self.clear_btn.clicked.connect(self.clearRequested.emit)
        self.clear_btn.setVisible(False)
        layout.addWidget(self.clear_btn, 0, Qt.AlignHCenter)

        self.retranslate()

    def retranslate(self) -> None:
        """按当前状态刷新拖放区文案；拖拽悬停或已选文件时标题高亮为主色。

        @author GLM-5.3 Flash @date 2026-09-03
        """
        self.clear_btn.setText(t("drop_clear"))
        if self._dragging:
            self.title_label.setText(t("drop_title_active"))
            self.sub_label.setText("")
            title_color = "#2F6FED"
        elif self._has_files:
            self.title_label.setText(t("drop_title_has_files", count=self._count))
            self.sub_label.setText(self._first_name)
            title_color = "#2563EB"
        else:
            self.title_label.setText(t("drop_title_empty"))
            self.sub_label.setText(t("drop_sub_empty"))
            title_color = "#1C1C1E"
        self.title_label.setStyleSheet(
            f"color:{title_color}; font-size:13px; font-weight:600; background:transparent;"
        )

    def set_files(self, files: list[Path]) -> None:
        self._count = len(files)
        self._has_files = self._count > 0
        if self._has_files:
            name = files[0].name
            self._first_name = (name[:20] + "…") if len(name) > 23 else name
            self.clear_btn.setVisible(True)
        else:
            self._first_name = ""
            self.clear_btn.setVisible(False)
        self._update_mark_icon()
        self.retranslate()
        self.update()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.setAcceptDrops(not busy)
        self.clear_btn.setEnabled(not busy)
        self.setCursor(Qt.ArrowCursor if busy else Qt.PointingHandCursor)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        if self._dragging:
            pen = QPen(QColor("#2F6FED"), 1.6, Qt.DashLine)
            painter.fillPath(path, QColor("#EFF6FF"))
        elif self._has_files:
            pen = QPen(QColor("#93C5FD"), 1.2, Qt.DashLine)
            painter.fillPath(path, QColor("#F8FAFC"))
        else:
            pen = QPen(QColor("#D1D5DB"), 1.2, Qt.DashLine)
            painter.fillPath(path, QColor("#FFFFFF"))

        painter.setPen(pen)
        painter.drawPath(path)

    def dragEnterEvent(self, event: Any) -> None:
        if self._busy or not event.mimeData().hasUrls():
            event.ignore()
            return
        self._dragging = True
        self.retranslate()
        self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: Any) -> None:
        self._dragging = False
        self.retranslate()
        self.update()
        event.accept()

    def dropEvent(self, event: Any) -> None:
        self._dragging = False
        if self._busy or not event.mimeData().hasUrls():
            event.ignore()
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.retranslate()
        self.update()
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.LeftButton and not self._busy:
            if not self.clear_btn.geometry().contains(event.pos()) or not self.clear_btn.isVisible():
                self.pickRequested.emit()
                return
        super().mousePressEvent(event)


class FastConvertWindow(QWidget):
    """Fast Convert / 闪电转换 主窗口。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    log_signal = Signal(str)
    log_highlight_signal = Signal(str, str)
    done_signal = Signal()
    eta_signal = Signal(dict)

    def __init__(self, runtime: Runtime, config_manager: ConfigManager) -> None:
        super().__init__()
        self.runtime = runtime
        self.config_manager = config_manager
        self.config = self.config_manager.load()
        self.logger = logging.getLogger("fast_convert")

        # 语言初始化
        saved_lang = str(self.config.get("language") or "")
        self.i18n = get_i18n(saved_lang if saved_lang in SUPPORTED_LANGUAGES else None)
        if not saved_lang:
            self.config["language"] = self.i18n.current_language
            self.config_manager.save(self.config)
        self.i18n.language_changed.connect(self._on_language_changed)

        # 核心状态
        saved_dir = str(self.config.get("last_working_dir") or "").strip()
        self.working_dir = Path(saved_dir) if saved_dir and Path(saved_dir).exists() else Path.home()
        self._active_proc: subprocess.Popen[str] | None = None
        self._proc_lock = threading.Lock()
        self._cancel_batch = False
        self._busy = False
        self._manual_files: list[Path] | None = None

        # 性能监控定时器
        self._perf_timer = QTimer(self)
        self._perf_timer.setInterval(1000)
        self._perf_timer.timeout.connect(self._update_perf_stats)
        self._tracked_procs: dict[int, Any] = {}
        self._main_proc: Any = None

        # 窗口样式与属性
        self.setObjectName("FastConvertWindow")
        self.setMinimumSize(780, 560)
        self.setWindowIcon(QIcon(str(asset_path("app.png"))))
        self.setStyleSheet(dialog_style())

        # 日志面板默认折叠；任务开始时自动展开
        self._log_expanded = False
        self._log_has_output = False

        self.log_signal.connect(self.write_log)
        self.log_highlight_signal.connect(self.write_highlight_log)
        self.done_signal.connect(self._on_batch_done)
        self.eta_signal.connect(self._on_eta_updated)

        self._build_ui()
        self._retranslate_ui()
        self._set_log_expanded(False, animate=False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        # 顶部工作目录行
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.dir_label = QLabel()
        self.dir_label.setObjectName("sectionLabel")
        self.dir_label.setFixedWidth(60)

        self.dir_edit = QLineEdit(str(self.working_dir))
        self.dir_edit.editingFinished.connect(self._on_dir_edited)

        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._browse_dir)

        # 地球图标语言切换按钮
        self.lang_btn = QPushButton()
        self.lang_btn.setObjectName("langBtn")
        self.lang_btn.setCursor(Qt.PointingHandCursor)
        self.lang_btn.setFixedSize(28, 28)
        globe_icon = QIcon(str(asset_path("globe.svg")))
        if not globe_icon.isNull():
            self.lang_btn.setIcon(globe_icon)
            self.lang_btn.setIconSize(QSize(16, 16))
        self.lang_btn.clicked.connect(self._open_language_dialog)

        dir_row.addWidget(self.dir_label)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.browse_btn)
        dir_row.addWidget(self.lang_btn)
        root.addLayout(dir_row)

        # 中部主体区
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(10)

        # 工作模式行
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.mode_label = QLabel()
        self.mode_label.setObjectName("sectionLabel")
        self.mode_label.setFixedWidth(60)
        mode_row.addWidget(self.mode_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        segment = QWidget()
        seg_layout = QHBoxLayout(segment)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        saved_mode = str(self.config.get("last_video_mode") or "convert")
        if saved_mode not in VIDEO_MODES:
            saved_mode = "convert"

        self._mode_buttons: dict[str, QPushButton] = {}
        for index, key in enumerate(VIDEO_MODES):
            btn = QPushButton()
            if index == 0:
                btn.setObjectName("modeSegFirst")
            elif index == len(VIDEO_MODES) - 1:
                btn.setObjectName("modeSegLast")
            else:
                btn.setObjectName("modeSeg")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("modeKey", key)
            self.mode_group.addButton(btn, index)
            self._mode_buttons[key] = btn
            seg_layout.addWidget(btn)
            if key == saved_mode:
                btn.setChecked(True)

        if not any(b.isChecked() for b in self._mode_buttons.values()):
            self._mode_buttons["convert"].setChecked(True)

        self.mode_group.idClicked.connect(lambda _id: self._apply_mode_state())
        mode_row.addWidget(segment)
        mode_row.addStretch(1)
        left.addLayout(mode_row)

        # 模式描述提示
        self.mode_hint = QLabel()
        self.mode_hint.setObjectName("hintLabel")
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setContentsMargins(68, 0, 0, 0)
        left.addWidget(self.mode_hint)

        # 参数行（CRF / 缩放 / 线程 / 速度）
        param_row = QHBoxLayout()
        param_row.setSpacing(8)
        param_row.setAlignment(Qt.AlignVCenter)

        self.crf_label = QLabel()
        self.crf_label.setObjectName("sectionLabel")
        self.crf_label.setFixedWidth(60)
        param_row.addWidget(self.crf_label)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(16, 32)
        self.crf_spin.setValue(self._saved_int("last_video_crf", 20, 16, 32))
        apply_system_spin_style(self.crf_spin)
        self.crf_spin.setFixedWidth(78)
        param_row.addWidget(self.crf_spin)

        param_row.addSpacing(8)
        self.scale_label = QLabel()
        param_row.addWidget(self.scale_label)

        self.scale_combo = QComboBox()
        self.scale_combo.setMinimumWidth(88)
        param_row.addWidget(self.scale_combo)

        param_row.addSpacing(8)
        self.thread_label = QLabel()
        param_row.addWidget(self.thread_label)

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 16)
        self.thread_spin.setValue(self._saved_int("last_video_threads", 4, 1, 16))
        apply_system_spin_style(self.thread_spin)
        self.thread_spin.setFixedWidth(78)
        param_row.addWidget(self.thread_spin)

        param_row.addSpacing(8)
        self.preset_label = QLabel()
        param_row.addWidget(self.preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(102)
        param_row.addWidget(self.preset_combo)

        param_row.addStretch(1)
        left.addLayout(param_row)
        self._sync_param_row_height()

        # 参数说明提示
        self.param_hint = QLabel()
        self.param_hint.setObjectName("hintLabel")
        self.param_hint.setWordWrap(True)
        self.param_hint.setContentsMargins(68, 0, 0, 0)
        left.addWidget(self.param_hint)
        left.addStretch(1)

        # 右侧拖放区
        self.drop_zone = VideoDropZone(self)
        self.drop_zone.filesDropped.connect(self._on_paths_dropped)
        self.drop_zone.pickRequested.connect(self._browse_files)
        self.drop_zone.clearRequested.connect(self._clear_manual_files)

        body.addLayout(left, 1)
        body.addWidget(self.drop_zone, 0, Qt.AlignTop)
        root.addLayout(body, 1)

        # 可折叠运行日志：标题条点击切换，任务开始时自动展开
        self.log_toggle_btn = QPushButton()
        self.log_toggle_btn.setObjectName("logToggle")
        self.log_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.log_toggle_btn.setFocusPolicy(Qt.NoFocus)
        self.log_toggle_btn.setMinimumHeight(32)
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        root.addWidget(self.log_toggle_btn)

        # 兼容旧引用名（翻译/外部如有使用）
        self.log_caption = self.log_toggle_btn

        self.log = QPlainTextEdit()
        self.log.setObjectName("logView")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(0)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.log, 2)

        # 底部操作栏（左侧监控，右侧操作按钮）
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        bottom_row.setAlignment(Qt.AlignVCenter)

        self.perf_label = QLabel()
        self.perf_label.setObjectName("perfLabel")
        bottom_row.addWidget(self.perf_label)

        bottom_row.addSpacing(8)
        self.eta_label = QLabel()
        self.eta_label.setObjectName("etaLabel")
        self.eta_label.setVisible(False)
        bottom_row.addWidget(self.eta_label)

        bottom_row.addStretch(1)

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_batch)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("ghostButton")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)

        bottom_row.addWidget(self.start_btn)
        bottom_row.addWidget(self.cancel_btn)
        bottom_row.addWidget(self.close_btn)
        root.addLayout(bottom_row)

    def _saved_int(self, key: str, default: int, lo: int, hi: int) -> int:
        try:
            val = int(self.config.get(key, default))
        except (TypeError, ValueError):
            val = default
        return max(lo, min(hi, val))

    def _sync_param_row_height(self) -> None:
        """让 CRF / 缩放 / 线程三个控件高度对齐。

        @author Gemini 3.8 Flash @date 2026-09-03
        """
        row_h = max(self.crf_spin.sizeHint().height(), self.thread_spin.sizeHint().height(), 26)
        self.crf_spin.setFixedHeight(row_h)
        self.thread_spin.setFixedHeight(row_h)
        self.scale_combo.setFixedHeight(row_h)
        self.preset_combo.setFixedHeight(row_h)

    def _format_seconds(self, seconds: float) -> str:
        s = max(0, int(round(seconds)))
        if s < 3600:
            m = s // 60
            rem_s = s % 60
            return f"{m:02d}:{rem_s:02d}"
        else:
            h = s // 3600
            m = (s % 3600) // 60
            rem_s = s % 60
            return f"{h:02d}:{m:02d}:{rem_s:02d}"

    def _on_eta_updated(self, data: dict[str, Any]) -> None:
        """更新底栏中央预计剩余时间标签与详细 Tooltip。

        @author Gemini 3.8 Flash @date 2026-09-03
        """
        eta_sec = data.get("eta_sec")
        pct = data.get("pct", 0.0)
        curr = data.get("curr", 1)
        total = data.get("total", 1)
        filename = data.get("filename", "")
        speed = data.get("speed", 0.0)
        curr_time = data.get("curr_time", 0.0)
        total_dur = data.get("total_duration", 0.0)

        if eta_sec is not None and eta_sec >= 0:
            eta_str = self._format_seconds(eta_sec)
            if total > 1:
                text = t("eta_batch", curr=curr, total=total, eta=eta_str, pct=f"{pct:.0f}")
            else:
                text = t("eta_single", eta=eta_str, pct=f"{pct:.0f}")
        else:
            text = t("eta_estimating")

        self.eta_label.setText(text)
        self.eta_label.setVisible(True)

        curr_str = self._format_seconds(curr_time)
        dur_str = self._format_seconds(total_dur)
        remain_tip = self._format_seconds(eta_sec) if (eta_sec is not None and eta_sec >= 0) else "--:--"
        tooltip_lines = [
            t("eta_tooltip_header"),
            t("eta_tooltip_file", name=filename),
            t("eta_tooltip_progress", pct=f"{pct:.1f}", curr_time=curr_str, total_time=dur_str),
            t("eta_tooltip_speed", speed=f"{speed:.2f}"),
            t("eta_tooltip_remain", eta=remain_tip),
        ]
        self.eta_label.setToolTip("\n".join(tooltip_lines))

    def _on_language_changed(self, lang: str) -> None:
        self.config["language"] = lang
        self.config_manager.save(self.config)
        self._retranslate_ui()

    def _open_language_dialog(self) -> None:
        dlg = LanguageDialog(self.i18n.current_language, self)
        if dlg.exec() == QDialog.Accepted:
            self.i18n.set_language(dlg.selected_language())

    def _retranslate_ui(self) -> None:
        """动态更新并刷新所有界面控件的文案。

        @author Gemini 3.8 Flash @date 2026-09-03
        """
        self.setWindowTitle(t("window_title", version=APP_VERSION))
        self.dir_label.setText(t("working_dir"))
        self.dir_edit.setPlaceholderText(t("dir_placeholder"))
        self.browse_btn.setText(t("browse"))
        self.lang_btn.setText("")
        self.lang_btn.setToolTip(t("switch_lang"))
        self.mode_label.setText(t("mode"))

        # 工作模式分段按钮
        self._mode_buttons["convert"].setText(t("mode_convert"))
        self._mode_buttons["compress"].setText(t("mode_compress"))
        self._mode_buttons["remux"].setText(t("mode_remux"))

        self.crf_label.setText(t("crf"))
        self.scale_label.setText(t("scale"))
        self.thread_label.setText(t("threads"))
        self.preset_label.setText(t("speed"))

        # 下拉缩放列表重新翻译并保持选中项
        curr_data = self.scale_combo.currentData() or self.config.get("last_video_scale", "orig")
        self.scale_combo.blockSignals(True)
        self.scale_combo.clear()
        for key in VIDEO_SCALE_KEYS:
            self.scale_combo.addItem(t(f"scale_{key}"), key)
        found_idx = self.scale_combo.findData(curr_data)
        self.scale_combo.setCurrentIndex(max(0, found_idx))
        self.scale_combo.blockSignals(False)

        # 下拉速度预设列表重新翻译并保持选中项
        curr_preset = self.preset_combo.currentData() or self.config.get("last_video_preset", "veryfast")
        if curr_preset not in VIDEO_PRESET_KEYS:
            curr_preset = "veryfast"
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for p_key in VIDEO_PRESET_KEYS:
            self.preset_combo.addItem(t(f"preset_{p_key}"), p_key)
        found_p_idx = self.preset_combo.findData(curr_preset)
        self.preset_combo.setCurrentIndex(max(0, found_p_idx))
        self.preset_combo.blockSignals(False)

        self.cancel_btn.setText(t("btn_cancel"))
        self.close_btn.setText(t("btn_close"))

        self.drop_zone.retranslate()
        self._apply_mode_state()
        self._update_log_header()
        self._update_perf_stats()

    def _current_mode(self) -> str:
        for key, btn in self._mode_buttons.items():
            if btn.isChecked():
                return key
        return "convert"

    def _apply_mode_state(self) -> None:
        mode = self._current_mode()
        remux = (mode == "remux")
        enable_quality = (not remux) and (not self._busy)

        self.crf_spin.setEnabled(enable_quality)
        self.scale_combo.setEnabled(enable_quality)
        self.preset_combo.setEnabled(enable_quality)

        self.mode_hint.setText(t(f"hint_{mode}"))
        if remux:
            self.param_hint.setText(t("param_remux"))
            self.start_btn.setText(t("btn_start_remux"))
        elif mode == "compress":
            self.param_hint.setText(t("param_crf"))
            self.start_btn.setText(t("btn_start_compress"))
        else:
            self.param_hint.setText(t("param_crf"))
            self.start_btn.setText(t("btn_start_convert"))

        self.start_btn.setEnabled(not self._busy)

    def _on_dir_edited(self) -> None:
        path = self._resolved_dir()
        if path:
            self._apply_working_dir(path, clear_manual=True)

    def _apply_working_dir(self, directory: Path, *, clear_manual: bool) -> None:
        self.working_dir = directory
        self.dir_edit.setText(str(directory))
        if clear_manual:
            self._manual_files = None
            self.drop_zone.set_files([])
        self.config["last_working_dir"] = str(directory)
        self.config_manager.save(self.config)

    def _resolved_dir(self) -> Path | None:
        text = self.dir_edit.text().strip()
        if not text:
            return None
        candidate = Path(text)
        return candidate if candidate.is_dir() else None

    def _browse_dir(self) -> None:
        initial = str(self.working_dir if self.working_dir.exists() else Path.home())
        chosen = QFileDialog.getExistingDirectory(self, t("working_dir"), initial)
        if chosen:
            self._apply_working_dir(Path(chosen), clear_manual=True)

    def _browse_files(self) -> None:
        if self._busy:
            return
        initial = str(self.working_dir if self.working_dir.exists() else Path.home())
        patterns = " ".join(f"*.{ext}" for ext in VIDEO_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("drop_title_empty"),
            initial,
            f"Video Files ({patterns});;All Files (*.*)",
        )
        if files:
            self._on_paths_dropped([Path(f) for f in files])

    def _on_paths_dropped(self, paths: list[Path]) -> None:
        if not paths or self._busy:
            return

        collected: list[Path] = []
        ignored = 0
        inferred_dir: Path | None = None

        for p in paths:
            if p.is_dir():
                if inferred_dir is None:
                    inferred_dir = p
                for sub in p.rglob("*"):
                    if sub.is_file():
                        if sub.suffix.lstrip(".").lower() in VIDEO_EXTS:
                            collected.append(sub)
                        else:
                            ignored += 1
            elif p.is_file():
                if inferred_dir is None:
                    inferred_dir = p.parent
                if p.suffix.lstrip(".").lower() in VIDEO_EXTS:
                    collected.append(p)
                else:
                    ignored += 1

        if not collected:
            if len(paths) == 1 and paths[0].is_dir():
                self._apply_working_dir(paths[0], clear_manual=True)
            return

        before = set(self._manual_files or [])
        merged: list[Path] = list(self._manual_files or [])
        added = 0
        for item in collected:
            if item not in before:
                merged.append(item)
                before.add(item)
                added += 1

        self._manual_files = merged
        self.drop_zone.set_files(merged)

        # 核心：无论之前是什么目录，自动切换为添加的第一个文件所在目录并持久化保存
        if merged:
            target_dir = inferred_dir if (inferred_dir and inferred_dir.is_dir()) else merged[0].parent
            self._apply_working_dir(target_dir, clear_manual=False)

        extra = t("log_ignored_files", ignored=ignored) if ignored else ""
        self.write_log(t("log_added_files", added=added, total=len(merged), extra=extra))

    def _clear_manual_files(self) -> None:
        if self._busy:
            return
        self._manual_files = None
        self.drop_zone.set_files([])

    def _toggle_log(self) -> None:
        """用户点击日志标题条时展开/收起日志面板。"""
        self._set_log_expanded(not self._log_expanded)

    def _set_log_expanded(self, expanded: bool, *, animate: bool = True) -> None:
        """设置日志面板展开状态；收起时把纵向空间还给主操作区。

        @author Grok @date 2026-03-23
        """
        del animate  # 预留：当前用显隐切换，避免高度动画抖动
        self._log_expanded = bool(expanded)
        self.log.setVisible(self._log_expanded)
        if self._log_expanded:
            self.log.setMinimumHeight(140)
            self.log.setMaximumHeight(16777215)
        else:
            self.log.setMinimumHeight(0)
            self.log.setMaximumHeight(0)
        self._update_log_header()

    def _update_log_header(self) -> None:
        """按折叠状态 / 是否有输出 / 是否忙碌刷新日志标题条文案与样式。"""
        if not hasattr(self, "log_toggle_btn"):
            return
        if self._log_expanded:
            # 纯文案，避免部分中文字体缺箭头字形导致方框
            label = t("log_toggle_collapse")
            tip = t("log_toggle_collapse")
        elif self._busy:
            label = t("log_collapsed_running")
            tip = t("log_toggle_expand")
        elif self._log_has_output:
            label = t("log_collapsed_has_output")
            tip = t("log_toggle_expand")
        else:
            label = t("log_collapsed_hint")
            tip = t("log_toggle_expand")

        self.log_toggle_btn.setText(label)
        self.log_toggle_btn.setToolTip(tip)
        self.log_toggle_btn.setProperty("expanded", "true" if self._log_expanded else "false")
        self.log_toggle_btn.setProperty("hasOutput", "true" if (self._log_has_output and not self._log_expanded) else "false")
        # 触发 QSS 动态属性刷新
        self.log_toggle_btn.style().unpolish(self.log_toggle_btn)
        self.log_toggle_btn.style().polish(self.log_toggle_btn)

    def write_log(self, text: str) -> None:
        self._log_has_output = True
        self.log.appendPlainText(text)
        if not self._log_expanded:
            self._update_log_header()

    def write_highlight_log(self, text: str, level: str = "success") -> None:
        """在运行日志中以醒目的前景色与背景色插入高亮结论行。

        @author Gemini 3.8 Flash @date 2026-09-04
        """
        self._log_has_output = True
        if not self._log_expanded:
            self._set_log_expanded(True)

        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        if level == "success":
            fmt.setForeground(QColor("#059669"))
            fmt.setBackground(QColor("#ECFDF5"))
        elif level == "warning":
            fmt.setForeground(QColor("#D97706"))
            fmt.setBackground(QColor("#FFFBEB"))
        elif level == "error":
            fmt.setForeground(QColor("#DC2626"))
            fmt.setBackground(QColor("#FEF2F2"))
        else:
            fmt.setForeground(QColor("#1D4ED8"))
            fmt.setBackground(QColor("#EFF6FF"))
        fmt.setFontWeight(QFont.Bold)

        cursor.insertText(f"\n{text}\n", fmt)
        cursor.setCharFormat(QTextCharFormat())
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()
        self._update_log_header()

    def _format_elapsed_text(self, seconds: float) -> str:
        """将耗时秒数格式化为中英自然语言描述（如 5分57秒 (357s)）。

        @author Gemini 3.8 Flash @date 2026-09-04
        """
        s = max(1, int(round(seconds)))
        is_zh = (self.i18n.current_language == "zh_CN")
        if s < 60:
            return f"{s}秒" if is_zh else f"{s}s"
        elif s < 3600:
            m = s // 60
            rem_s = s % 60
            if rem_s > 0:
                return f"{m}分{rem_s:02d}秒 ({s}s)" if is_zh else f"{m}m {rem_s:02d}s ({s}s)"
            else:
                return f"{m}分钟 ({s}s)" if is_zh else f"{m}m ({s}s)"
        else:
            h = s // 3600
            m = (s % 3600) // 60
            rem_s = s % 60
            return f"{h}小时{m:02d}分{rem_s:02d}秒 ({s}s)" if is_zh else f"{h}h {m:02d}m {rem_s:02d}s ({s}s)"

    def start(self) -> None:
        """开始执行批量视频转码/压缩/重封任务。

        @author Gemini 3.8 Flash @date 2026-09-03
        """
        if self._busy:
            return
        if not self.runtime.ffmpeg.exists():
            QMessageBox.critical(
                self,
                t("msg_ffmpeg_missing_title"),
                t("msg_ffmpeg_missing_text", path=self.runtime.ffmpeg),
            )
            return

        workdir = self._resolved_dir()
        if workdir is None and self._manual_files:
            workdir = self._manual_files[0].parent
            self._apply_working_dir(workdir, clear_manual=False)

        if workdir is None:
            QMessageBox.warning(
                self,
                t("msg_workdir_warning_title"),
                t("msg_workdir_warning_text"),
            )
            return

        mode = self._current_mode()
        files = self._manual_files or self._scan_files(workdir, mode)
        if not files:
            self._set_log_expanded(True)
            self.write_log(t("log_no_videos"))
            return

        self._busy = True
        self._cancel_batch = False
        self._set_log_expanded(True)
        self._set_controls_enabled(False)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.eta_label.setText(t("eta_estimating"))
        self.eta_label.setVisible(True)

        crf = self.crf_spin.value()
        threads = self.thread_spin.value()
        scale = str(self.scale_combo.currentData() or "orig")
        preset = str(self.preset_combo.currentData() or "veryfast")

        self.config["last_video_mode"] = mode
        self.config["last_video_crf"] = crf
        self.config["last_video_threads"] = threads
        self.config["last_video_scale"] = scale
        self.config["last_video_preset"] = preset
        self.config_manager.save(self.config)

        threading.Thread(
            target=self._run_batch,
            args=(files, mode, crf, threads, scale, preset, workdir),
            daemon=True,
        ).start()

    def _scan_files(self, workdir: Path, mode: str) -> list[Path]:
        results: list[Path] = []
        try:
            for item in workdir.iterdir():
                if item.is_file():
                    ext = item.suffix.lstrip(".").lower()
                    if mode in ("compress", "remux") and ext == "mp4":
                        results.append(item)
                    elif mode == "convert" and ext in VIDEO_EXTS and ext != "mp4":
                        results.append(item)
        except Exception as exc:
            self.write_log(f"扫描目录出错: {exc}")
        return sorted(results)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.dir_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.lang_btn.setEnabled(enabled)
        for btn in self._mode_buttons.values():
            btn.setEnabled(enabled)
        self.thread_spin.setEnabled(enabled)
        self.drop_zone.set_busy(not enabled)
        if enabled:
            self._apply_mode_state()
        else:
            self.crf_spin.setEnabled(False)
            self.scale_combo.setEnabled(False)
            self.preset_combo.setEnabled(False)

    def cancel_batch(self) -> None:
        self._cancel_batch = True
        self._stop_active_proc()
        self.write_log(t("log_cancelling"))
        self.cancel_btn.setEnabled(False)
        self.eta_label.setVisible(False)

    def _stop_active_proc(self) -> None:
        with self._proc_lock:
            proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        except Exception as exc:
            self.logger.warning("终止 FFmpeg 进程失败: %s", exc)
        finally:
            with self._proc_lock:
                if self._active_proc is proc:
                    self._active_proc = None

    def _run_batch(
        self,
        files: list[Path],
        mode: str,
        crf: int,
        threads: int,
        scale: str,
        preset: str,
        workdir: Path,
    ) -> None:
        outdir = workdir / "converted"
        outdir.mkdir(parents=True, exist_ok=True)
        self.log_signal.emit(t("log_batch_start", count=len(files)))
        batch_start_time = time.time()

        success_count = 0
        fail_count = 0

        def _scale_filter(scale_key: str) -> str | None:
            if scale_key in ("", "orig"):
                return None
            if scale_key == "p75":
                return "scale=trunc(iw*0.75/2)*2:trunc(ih*0.75/2)*2"
            if scale_key == "p50":
                return "scale=trunc(iw*0.5/2)*2:trunc(ih*0.5/2)*2"
            heights = {"1080": 1080, "720": 720, "480": 480}
            h = heights.get(scale_key)
            if h is None:
                return None
            return f"scale=-2:'trunc(min(ih,{h})/2)*2'"

        for idx, src in enumerate(files, 1):
            if self._cancel_batch:
                break
            dst = outdir / f"{src.stem}.mp4"
            if mode == "compress" and src.resolve() == dst.resolve():
                dst = outdir / f"{src.stem}_compressed.mp4"

            self.log_signal.emit(f"\n[{idx}/{len(files)}] {src.name} -> {dst.name}")
            cmd = [str(self.runtime.ffmpeg), "-y", "-ignore_unknown", "-i", str(src)]

            if mode == "remux":
                cmd += ["-c", "copy", "-movflags", "+faststart", str(dst)]
            else:
                cmd += [
                    "-c:v", "libx264",
                    "-crf", str(crf),
                    "-preset", preset,
                    "-threads", str(threads),
                ]
                vf = _scale_filter(scale)
                if vf:
                    cmd += ["-vf", vf]
                cmd += [
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(dst),
                ]

            rc = self._execute_ffmpeg(
                cmd,
                workdir,
                file_index=idx,
                total_files=len(files),
                src_name=src.name,
            )
            if rc == 0:
                success_count += 1
            else:
                fail_count += 1
                if self._cancel_batch:
                    break

        total_elapsed = max(0.1, time.time() - batch_start_time)
        elapsed_str = self._format_elapsed_text(total_elapsed)

        if self._cancel_batch:
            self.log_highlight_signal.emit(t("log_cancelled", elapsed=elapsed_str), "warning")
        else:
            level = "success" if fail_count == 0 else "error"
            self.log_highlight_signal.emit(t("log_batch_done", s=success_count, f=fail_count, elapsed=elapsed_str), level)
        self.done_signal.emit()

    def _execute_ffmpeg(
        self,
        cmd: list[str],
        workdir: Path,
        *,
        file_index: int = 1,
        total_files: int = 1,
        src_name: str = "",
    ) -> int:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        with self._proc_lock:
            self._active_proc = subprocess.Popen(
                cmd,
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
            proc = self._active_proc

        total_duration = 0.0
        start_real = time.time()
        last_emit_time = 0.0

        try:
            if proc.stdout:
                for line in proc.stdout:
                    if self._cancel_batch:
                        break
                    line_str = line.rstrip()
                    if line_str:
                        self.log_signal.emit(line_str)

                        # 1. 探测输入文件的总时长
                        if total_duration <= 0.0:
                            m_dur = DURATION_REGEX.search(line_str)
                            if m_dur:
                                h, m, s = float(m_dur.group(1)), float(m_dur.group(2)), float(m_dur.group(3))
                                total_duration = h * 3600 + m * 60 + s

                        # 2. 探测转码进度与速率并计算预估剩余时间
                        m_time = TIME_REGEX.search(line_str)
                        if m_time and total_duration > 0.0:
                            now = time.time()
                            if now - last_emit_time >= 0.4:
                                last_emit_time = now
                                h, m, s = float(m_time.group(1)), float(m_time.group(2)), float(m_time.group(3))
                                curr_time = h * 3600 + m * 60 + s

                                m_speed = SPEED_REGEX.search(line_str)
                                speed_val = float(m_speed.group(1)) if m_speed else 0.0

                                remain_video = max(0.0, total_duration - curr_time)
                                eta_sec = None
                                if speed_val > 0.05:
                                    eta_sec = remain_video / speed_val
                                else:
                                    elapsed = max(0.1, now - start_real)
                                    if curr_time > 0.5:
                                        eta_sec = (elapsed / curr_time) * remain_video

                                pct = min(100.0, max(0.0, (curr_time / total_duration) * 100.0))
                                self.eta_signal.emit({
                                    "curr": file_index,
                                    "total": total_files,
                                    "filename": src_name,
                                    "eta_sec": eta_sec,
                                    "pct": pct,
                                    "speed": speed_val,
                                    "curr_time": curr_time,
                                    "total_duration": total_duration,
                                })

            if self._cancel_batch and proc.poll() is None:
                self._stop_active_proc()
                return -1
            return proc.wait()
        finally:
            with self._proc_lock:
                if self._active_proc is proc:
                    self._active_proc = None

    def _on_batch_done(self) -> None:
        self._busy = False
        self._set_controls_enabled(True)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.eta_label.setVisible(False)
        self._apply_mode_state()
        self._update_log_header()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._perf_timer.isActive():
            self._perf_timer.start()
        self._update_perf_stats()

    def hideEvent(self, event: Any) -> None:
        self._perf_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event: Any) -> None:
        self._perf_timer.stop()
        self._cancel_batch = True
        self._stop_active_proc()
        super().closeEvent(event)

    def _update_perf_stats(self) -> None:
        """实时采集当前程序及转码子进程的 CPU 与内存占用。

        @author Gemini 3.8 Flash @date 2026-09-03
        """
        if psutil is None:
            self.perf_label.setText("CPU --  RAM --")
            self.perf_label.setToolTip("psutil not available")
            return

        try:
            main_pid = os.getpid()
            if self._main_proc is None or self._main_proc.pid != main_pid:
                try:
                    self._main_proc = psutil.Process(main_pid)
                    self._main_proc.cpu_percent(None)
                except Exception:
                    self._main_proc = None

            if self._main_proc is None:
                return

            active_pids = {main_pid}
            try:
                for c in self._main_proc.children(recursive=True):
                    active_pids.add(c.pid)
            except Exception:
                pass

            self._tracked_procs = {pid: p for pid, p in self._tracked_procs.items() if pid in active_pids}
            for pid in active_pids:
                if pid not in self._tracked_procs:
                    try:
                        p = self._main_proc if pid == main_pid else psutil.Process(pid)
                        p.cpu_percent(None)
                        self._tracked_procs[pid] = p
                    except Exception:
                        pass

            total_cpu = 0.0
            total_rss = 0
            details: list[str] = []

            for pid, p in list(self._tracked_procs.items()):
                try:
                    c_cpu = p.cpu_percent(None)
                    c_mem = p.memory_info().rss
                    total_cpu += c_cpu
                    total_rss += c_mem
                    name = p.name()
                    tag = t("perf_main_proc") if pid == main_pid else t("perf_child_proc", name=name)
                    details.append(f"  • {tag} [PID {pid}]: CPU {c_cpu:.1f}%, RAM {c_mem / (1024 * 1024):.1f} MB")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    self._tracked_procs.pop(pid, None)

            cpu_count = psutil.cpu_count() or 1
            norm_cpu = total_cpu / cpu_count

            if total_rss >= 1024 * 1024 * 1024:
                mem_str = f"{total_rss / (1024 ** 3):.2f} GB"
            else:
                mem_str = f"{total_rss / (1024 ** 2):.1f} MB"

            self.perf_label.setText(t("perf_idle", cpu=f"{norm_cpu:.1f}", mem=mem_str))

            tooltip_parts = [
                t("perf_tooltip_header"),
                t("perf_tooltip_cpu", cpu=f"{norm_cpu:.1f}", raw=f"{total_cpu:.1f}"),
                t("perf_tooltip_mem", mem=mem_str),
            ]
            if details:
                tooltip_parts.append(t("perf_tooltip_details"))
                tooltip_parts.extend(details)

            try:
                sys_cpu = psutil.cpu_percent(None)
                vm = psutil.virtual_memory()
                sys_mem_used = vm.used / (1024 ** 3)
                sys_mem_total = vm.total / (1024 ** 3)
                tooltip_parts.extend([
                    "",
                    t("perf_tooltip_sys_header"),
                    t("perf_tooltip_sys_cpu", cpu=f"{sys_cpu:.1f}"),
                    t("perf_tooltip_sys_mem", pct=f"{vm.percent:.1f}", used=f"{sys_mem_used:.1f}", total=f"{sys_mem_total:.1f}"),
                ])
            except Exception:
                pass

            self.perf_label.setToolTip("\n".join(tooltip_parts))
        except Exception as exc:
            self.logger.debug("update perf stats failed: %s", exc)


def main() -> int:
    """Fast Convert 应用程序入口点。

    @author Gemini 3.8 Flash @date 2026-09-03
    """
    app_dir = Path(__file__).resolve().parent
    config_manager = ConfigManager(app_dir / "config.json")
    runtime = RuntimeManager(app_dir, logging.getLogger("fast_convert")).ensure()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_EN)
    app.setApplicationVersion(APP_VERSION)

    window = FastConvertWindow(runtime, config_manager)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
