"""Shared dark palette, with NZXT-inspired indigo and vivid purple accents."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtSvg import QSvgRenderer  # Include Qt's SVG support in the frozen app.
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QMainWindow, QVBoxLayout

ACCENT = "#8A00FC"
INDIGO = "#51007A"
ASSETS = Path(__file__).resolve().parent / "assets"


class WindowChrome(QObject):
    """Colour only this application's native Windows title bars."""
    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show and isinstance(widget,(QMainWindow,QDialog)):
            import ctypes
            try:
                handle = ctypes.c_void_p(int(widget.winId()))
                for attribute, colour in ((20,1),(34,0x3B2A30),(35,0x141010),(36,0xF6F4F4)):
                    value = ctypes.c_uint32(colour)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(handle,attribute,ctypes.byref(value),ctypes.sizeof(value))
            except (AttributeError,OSError):
                pass  # Older Windows versions retain their native title bar.
        return super().eventFilter(widget,event)


def heading(layout, title, subtitle=None):
    label = QLabel(title)
    label.setObjectName("dialogTitle")
    layout.addWidget(label)
    if subtitle:
        label = QLabel(subtitle)
        label.setObjectName("muted")
        label.setWordWrap(True)
        layout.addWidget(label)


def surface(layout):
    frame = QFrame()
    frame.setObjectName("surface")
    inner = QVBoxLayout(frame)
    inner.setContentsMargins(18, 16, 18, 16)
    inner.setSpacing(12)
    layout.addWidget(frame)
    return inner


def apply_theme(app):
    app.setStyle("Fusion")
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisym.ttf"):
            if (fonts / filename).exists():
                QFontDatabase.addApplicationFont(str(fonts / filename))
    font = QFont("Segoe UI", 10)
    font.setFamilies(["Segoe UI", "Segoe UI Symbol"])
    app.setFont(font)
    palette = QPalette()
    for role, colour in ((QPalette.Window,"#101014"), (QPalette.WindowText,"#F4F4F6"),
                         (QPalette.Base,"#19191F"), (QPalette.AlternateBase,"#24232C"),
                         (QPalette.Text,"#F4F4F6"), (QPalette.Button,"#292631"),
                         (QPalette.ButtonText,"#F4F4F6"), (QPalette.Highlight,ACCENT),
                         (QPalette.HighlightedText,"#FFFFFF"), (QPalette.ToolTipBase,"#292631"),
                         (QPalette.ToolTipText,"#F4F4F6")):
        palette.setColor(role,QColor(colour))
    app.setPalette(palette)
    if sys.platform == "win32" and app.platformName() == "windows":
        app._lsc_chrome = WindowChrome(app)
        app.installEventFilter(app._lsc_chrome)
    app.setStyleSheet("""
        QWidget { color: #F4F4F6; font-size: 13px; }
        QMainWindow, QDialog { background: #101014; }
        QLabel { background: transparent; }
        QLabel#heading { font-size: 24px; font-weight: 600; padding: 10px 0; }
        QLabel#dialogTitle { font-size: 24px; font-weight: 600; }
        QLabel#muted, QLabel#subtitle, QLabel#fieldLabel { color: #AAA5B7; }
        QLabel#fieldLabel { font-size: 12px; }
        QLabel#status { color: #C7A3EF; padding-bottom: 6px; }
        QLabel#countdownValue { font-size: 36px; font-weight: 600; }
        QLabel#scheduleTime { font-size: 28px; font-weight: 600; }
        QLabel#scheduleAction { color: #D3B3F0; font-weight: 600; }
        QFrame#surface, QFrame#scheduleCard { background: #19191F; border: 1px solid #302A3B; border-radius: 14px; }
        QFrame#scheduleCard[active="true"] { border-color: #513365; }
        QGroupBox { background: #19191F; border: 1px solid #302A3B; border-radius: 14px; margin-top: 16px; padding: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 5px; font-weight: 600; }
        QPushButton { background: #292631; border: 1px solid transparent; border-radius: 8px; padding: 10px 16px; }
        QPushButton:hover { background: #393044; }
        QPushButton:pressed { background: #51007A; }
        QPushButton:focus { border-color: #BC83FF; }
        QPushButton:disabled { color: #716A80; background: #211E28; }
        QPushButton[role="primary"], QPushButton#powerButton { background: #8A00FC; color: white; font-weight: 600; }
        QPushButton[role="primary"]:hover, QPushButton#powerButton:hover { background: #9B2CFF; }
        QPushButton[role="primary"]:pressed, QPushButton#powerButton:pressed { background: #51007A; }
        QPushButton[role="primary"]:disabled { background: #3E2255; color: #A596B1; }
        QPushButton[role="ghost"] { background: transparent; color: #C8C2D3; }
        QPushButton[role="ghost"]:hover { background: #292631; }
        QPushButton[role="danger"] { background: transparent; color: #DF9DAE; }
        QPushButton[role="danger"]:hover { background: #3C222C; }
        QPushButton[role="preset"] { background: #25202E; color: #D7B6F8; padding: 8px 12px; }
        QPushButton:checked { background: #51007A; border-color: #8A00FC; }
        QPushButton[role="toggle"] { padding: 6px 12px; color: #AAA5B7; }
        QPushButton[role="toggle"]:checked { background: #342044; border-color: #77459D; color: #E3C6FF; }
        QLineEdit, QComboBox, QSpinBox, QTimeEdit { background: #201D27; border: 1px solid #44394F; border-radius: 8px; padding: 9px 12px; selection-background-color: #51007A; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus { border-color: #A54DFF; }
        QSpinBox#durationInput { font-size: 28px; font-weight: 600; padding: 12px 4px; }
        QTimeEdit#timeInput { font-size: 36px; font-weight: 600; padding: 12px 24px; }
        QComboBox::drop-down { border: none; width: 26px; }
        QComboBox::down-arrow { image: url("$CHEVRON"); width: 12px; height: 12px; }
        QComboBox QAbstractItemView { background: #24202C; selection-background-color: #51007A; padding: 6px; }
        QCheckBox { spacing: 10px; background: transparent; padding: 3px 0; }
        QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #70617F; background: #24202C; }
        QCheckBox::indicator:checked { background: #8A00FC; border-color: #A54DFF; image: url("$CHECK"); }
        QPushButton[role="day"] { background: #25202E; border: 1px solid #44394F; border-radius: 8px; padding: 9px 4px; }
        QPushButton[role="day"]:checked { background: #51007A; border-color: #A54DFF; color: white; }
        QPushButton[role="day"]:focus { border-color: #D3B3F0; }
        QSlider::groove:horizontal { height: 6px; background: #3D3449; border-radius: 3px; }
        QSlider::sub-page:horizontal { background: #8A00FC; border-radius: 2px; }
        QSlider::handle:horizontal { background: #D1ACFF; width: 18px; margin: -6px 0; border-radius: 9px; }
        QSlider::handle:horizontal:hover { background: #E5D1FF; }
        QTabWidget::pane { border: none; background: transparent; }
        QTabBar::tab { background: transparent; color: #AAA5B7; padding: 12px 20px; border-bottom: 2px solid #302A3B; }
        QTabBar::tab:selected { color: #F4F4F6; border-bottom: 2px solid #8A00FC; }
        QScrollArea { background: transparent; border: none; }
        QWidget#scheduleContent { background: transparent; }
        QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
        QScrollBar::handle:vertical { background: #53435F; border-radius: 4px; min-height: 28px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        QMenu { background: #19191F; border: 1px solid #44394F; padding: 6px; }
        QMenu::item { padding: 7px 24px 7px 12px; }
        QMenu::item:selected { background: #51007A; border-radius: 4px; }
        QMenu::item:disabled { color: #AAA5B7; }
        QToolTip { background: #292631; color: #F4F4F6; border: 1px solid #513365; padding: 6px; }
    """.replace("$CHECK",(ASSETS / "check.svg").as_posix()).replace("$CHEVRON",(ASSETS / "chevron.svg").as_posix()))
