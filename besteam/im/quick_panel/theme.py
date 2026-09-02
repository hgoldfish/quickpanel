"""根据用户背景图亮度自动切换 UI 亮/暗模式。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

__all__ = ["image_luminance", "apply_for_image", "mode",
           "text", "text_sub", "text_faint", "divider", "ink_sub",
           "card", "card_border", "grid", "dialog_bg", "dialog_border",
           "layout_grid", "menu_button"]

_mode = "light"
_light_palette = None
_dark_palette = None

_LUMINANCE_THRESHOLD = 128

# (light, dark) — 每项为 QColor 构造参数：RGB 三元组或 RGBA 四元组
_COLORS = {
    "text": ((38, 48, 66), (235, 238, 245)),
    "text_sub": ((110, 122, 144), (160, 170, 185)),
    "text_faint": ((150, 160, 178), (140, 150, 165)),
    "divider": ((150, 160, 178, 60), (255, 255, 255, 40)),
    "ink_sub": ((110, 122, 144), (200, 210, 225)),
    "card": ((255, 255, 255, 25), (255, 255, 255, 16)),
    "card_border": ((140, 150, 170, 90), (200, 210, 230, 90)),
    "grid": ((110, 122, 144, 70), (255, 255, 255, 50)),
    "dialog_bg": ((255, 255, 255), (53, 53, 58)),
    "dialog_border": ((200, 200, 200), (90, 95, 105)),
    "layout_grid": ((255, 255, 255), (180, 190, 205)),
}

_MENU_BUTTON_QSS = {
    "light": """
        QToolButton { background: rgba(255,255,255,215); border: 1px solid rgba(130,142,160,130);
            border-radius: 4px; }
        QToolButton:hover { background: rgba(255,255,255,255); }
        QToolButton::menu-indicator { image: none; }
    """,
    "dark": """
        QToolButton { background: rgba(60,60,65,215); border: 1px solid rgba(120,130,145,130);
            border-radius: 4px; color: #f0f0f0; }
        QToolButton:hover { background: rgba(75,75,82,255); }
        QToolButton::menu-indicator { image: none; }
    """,
}


def image_luminance(image):
    """返回背景图平均亮度（0~255）。"""
    if image is None or image.isNull():
        return 255.0
    small = image.scaled(64, 64, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    count = small.width() * small.height()
    if count == 0:
        return 255.0
    total = 0.0
    for y in range(small.height()):
        for x in range(small.width()):
            c = small.pixelColor(x, y)
            total += 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return total / count


def _light_palette_cached():
    global _light_palette
    if _light_palette is None:
        app = QApplication.instance()
        if app is not None:
            _light_palette = app.style().standardPalette()
        else:
            _light_palette = QPalette()
    return _light_palette


def _dark_palette_cached():
    global _dark_palette
    if _dark_palette is None:
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#353535"))
        p.setColor(QPalette.WindowText, QColor("#f0f0f0"))
        p.setColor(QPalette.Base, QColor("#292929"))
        p.setColor(QPalette.AlternateBase, QColor("#353535"))
        p.setColor(QPalette.ToolTipBase, QColor("#353535"))
        p.setColor(QPalette.ToolTipText, QColor("#f0f0f0"))
        p.setColor(QPalette.Text, QColor("#f0f0f0"))
        p.setColor(QPalette.Button, QColor("#353535"))
        p.setColor(QPalette.ButtonText, QColor("#f0f0f0"))
        p.setColor(QPalette.BrightText, QColor("#ffffff"))
        p.setColor(QPalette.Link, QColor("#2a82da"))
        p.setColor(QPalette.Highlight, QColor("#2a82da"))
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        p.setColor(QPalette.PlaceholderText, QColor("#888888"))
        p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#787878"))
        p.setColor(QPalette.Disabled, QPalette.Text, QColor("#787878"))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#787878"))
        _dark_palette = p
    return _dark_palette


def apply_for_image(image):
    """分析背景图亮度并切换 app palette；模式变化时返回 True。"""
    global _mode
    new_mode = "dark" if image_luminance(image) < _LUMINANCE_THRESHOLD else "light"
    if new_mode == _mode:
        return False
    app = QApplication.instance()
    if app is not None:
        if new_mode == "dark":
            app.setPalette(_dark_palette_cached())
        else:
            app.setPalette(_light_palette_cached())
    _mode = new_mode
    return True


def mode():
    return _mode


def _color(name):
    light, dark = _COLORS[name]
    return QColor(*(dark if _mode == "dark" else light))


def text():
    return _color("text")


def text_sub():
    return _color("text_sub")


def text_faint():
    return _color("text_faint")


def divider():
    return _color("divider")


def ink_sub():
    return _color("ink_sub")


def card():
    return _color("card")


def card_border():
    return _color("card_border")


def grid():
    return _color("grid")


def dialog_bg():
    return _color("dialog_bg")


def dialog_border():
    return _color("dialog_border")


def layout_grid():
    return _color("layout_grid")


def menu_button():
    return _MENU_BUTTON_QSS[_mode]
