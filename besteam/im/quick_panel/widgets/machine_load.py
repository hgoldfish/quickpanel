import math
import os
import io
import sys
import time
import random
import ctypes
from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, \
        QRadialGradient
from PyQt5.QtWidgets import QApplication, QMenu, QToolButton, QWidget

__all__ = ["MachineLoadWidget"]

# 保留最近 60 秒的历史记录
HISTORY_SECONDS = 60
# 采样间隔
SAMPLE_INTERVAL = 500

# ---- 明亮风格配色 ----
INK_SUB = QColor(110, 122, 144)   # 次要线条/网格
CARD = QColor(255, 255, 255, 25)  # 接近透明的卡片背景（约 90% 透明）
CARD_BORDER = QColor(140, 150, 170, 90)
GRID = QColor(110, 122, 144, 70)
CYAN = QColor(0, 168, 235)
VIOLET = QColor(124, 92, 255)
PINK = QColor(255, 64, 160)
AMBER = QColor(255, 190, 40)
ORANGE = QColor(255, 132, 20)
RED = QColor(255, 66, 58)
WOOD = QColor(122, 78, 44)
GREEN = QColor(34, 190, 110)


class ColorKit:
    """颜色与数值的纯数学工具。"""

    @staticmethod
    def clamp(v, a, b):
        return max(a, min(b, v))

    @staticmethod
    def lerp(a, b, t):
        return a + (b - a) * t

    @staticmethod
    def mix(c1, c2, t):
        t = ColorKit.clamp(t, 0.0, 1.0)
        return QColor(int(ColorKit.lerp(c1.red(), c2.red(), t)),
                      int(ColorKit.lerp(c1.green(), c2.green(), t)),
                      int(ColorKit.lerp(c1.blue(), c2.blue(), t)))

    @staticmethod
    def lighten(c, f):
        return QColor(min(255, int(c.red() * f)), min(255, int(c.green() * f)),
                      min(255, int(c.blue() * f)))

    @staticmethod
    def darken(c, f):
        return QColor(int(c.red() * f), int(c.green() * f), int(c.blue() * f))

    @staticmethod
    def alpha(c, a):
        return QColor(c.red(), c.green(), c.blue(), a)

    @staticmethod
    def load_color(v):
        if v <= 50:
            return ColorKit.mix(CYAN, VIOLET, v / 50.0)
        return ColorKit.mix(VIOLET, PINK, (v - 50) / 50.0)

    @staticmethod
    def lava_color(v):
        if v <= 50:
            return ColorKit.mix(AMBER, ORANGE, v / 50.0)
        return ColorKit.mix(ORANGE, RED, (v - 50) / 50.0)


class CpuHistory:
    """最近一段时间的 CPU 采样历史（新样本在头部）。"""

    def __init__(self, seconds=HISTORY_SECONDS, max_samples=400):
        self.seconds = seconds
        self.max_samples = max_samples
        self.samples = []

    def add(self, value, now):
        self.samples.insert(0, (now, value))
        if len(self.samples) > self.max_samples:
            self.samples.pop(-1)

    def clear(self):
        self.samples = []

    def is_empty(self):
        return not self.samples

    def series(self, now):
        """最近 seconds 秒内的采样值（旧 → 新）。"""
        vals = []
        for t, v in self.samples:
            if now - t > self.seconds:
                break
            vals.append(v)
        vals.reverse()
        return vals

    def current(self, now):
        """当前负载：最近一个采样点的值；无采样时返回 0。"""
        for t, v in self.samples:
            if now - t <= self.seconds:
                return v
        return 0

    def bars(self, now, nbar):
        """把最近 seconds 秒的采样折算成 nbar 个柱值（旧 → 新）。"""
        filtered = self.series(now)
        if not filtered:
            return []
        step = max(1, len(filtered) // nbar)
        vals = []
        i = 0
        while i < len(filtered) and len(vals) < nbar:
            chunk = filtered[i:i + step]
            vals.append(sum(chunk) / len(chunk))
            i += step
        return vals


class ChartStyle(ColorKit):
    """所有显示风格的基类。"""

    key = ""
    title = ""
    group = ""

    def paint(self, p, rect, history, now):
        raise NotImplementedError

    # ---- 通用绘制 ----
    def _plot_area(self, rect):
        """绘图区：撑满画布，留少量边距。"""
        return rect.adjusted(2, 2, -2, -2)

    def _bar_count(self, width, per=9, min_n=12):
        """按宽度估算柱数：每 per 像素一根，至少 min_n 根。"""
        return max(min_n, int(width // per))

    def _paint_timeaxis(self, p, rect):
        """浅色水平分隔线，表示历史时间流向，不含文字。"""
        axis = QRectF(rect.left(), rect.bottom() - 2, rect.width(), 2)
        p.setPen(QPen(self.alpha(INK_SUB, 60), 1))
        p.drawLine(QPointF(axis.left(), axis.center().y()), QPointF(axis.right(), axis.center().y()))


class BarChartStyle(ChartStyle):
    """柱状图风格基类：立体柱 + 顶部粒子。"""

    def _draw_prism(self, p, area, vals, colorfn, depth=None):
        if not vals:
            return area.bottom()
        if depth is None:
            depth = max(6, int(area.height() * 0.10))
        bw = (area.width() - depth) / len(vals)
        floor = area.bottom()
        p.setPen(QPen(GRID, 1))
        for i in range(len(vals) + 1):
            x = area.left() + i * bw
            p.drawLine(QPointF(x, floor), QPointF(x + depth, floor - depth))
        p.drawLine(QPointF(area.left(), floor), QPointF(area.right(), floor - depth))
        p.drawLine(QPointF(area.left(), floor), QPointF(area.right(), floor))
        p.setPen(QPen(QColor(0, 0, 0, 26), 1))
        p.drawLine(QPointF(area.left(), floor), QPointF(area.left() + depth, floor - depth))
        for i, v in enumerate(vals):
            h = self.clamp(v, 0, 100) / 100.0 * (area.height() - depth)
            x = area.left() + i * bw
            y = floor - h
            col = colorfn(i, v)
            top = QPolygonF([QPointF(x, y), QPointF(x + bw, y),
                             QPointF(x + bw + depth, y - depth), QPointF(x + depth, y - depth)])
            p.setPen(QPen(QColor(0, 0, 0, 28), 1))
            p.setBrush(self.lighten(col, 1.4))
            p.drawPolygon(top)
            side = QPolygonF([QPointF(x + bw, y), QPointF(x + bw + depth, y - depth),
                              QPointF(x + bw + depth, y - depth + h), QPointF(x + bw, floor)])
            p.setBrush(self.darken(col, 0.72))
            p.drawPolygon(side)
            p.setBrush(col)
            p.drawRect(QRectF(x, y, bw, h))
        return floor

    def _bar_vents(self, area, vals, depth=None):
        if not vals:
            return []
        if depth is None:
            depth = max(6, int(area.height() * 0.10))
        bw = (area.width() - depth) / len(vals)
        floor = area.bottom()
        out = []
        for i, v in enumerate(vals):
            h = self.clamp(v, 0, 100) / 100.0 * (area.height() - depth)
            out.append((area.left() + i * bw + bw / 2, floor - h, v / 100.0))
        return out

    def _rising_particles(self, p, vents, count, colors, height, seed, t, spread=0.5):
        """从 vent 顶部向上漂浮的粒子。位置由种子决定，随时间平稳漂移。"""
        if not vents or not colors:
            return
        rnd = random.Random(seed)
        for i in range(count):
            vx, vy, k = vents[i % len(vents)]
            off = rnd.random()
            phase = (t * 0.08 + off) % 1.0
            x = vx + math.sin(off * 12.7 + t * 0.5) * spread * (1 - phase) * 26
            y = vy - phase * height * (0.4 + 0.6 * k)
            col = colors[i % len(colors)]
            a = int(200 * (1 - phase * 0.75) * (0.35 + 0.65 * k))
            r = 1.2 + 2.4 * (1 - phase)
            p.setPen(Qt.NoPen)
            p.setBrush(self.alpha(col, a))
            p.drawEllipse(QPointF(x, y), r, r)


class NeonEmberStyle(BarChartStyle):
    """风格 02 · 霓虹余烬墙"""
    key = "neon_ember"
    title = "霓虹余烬墙"
    group = "常规"

    def paint(self, p, rect, history, now):
        area = self._plot_area(rect)
        vals = history.bars(now, self._bar_count(rect.width()))
        self._draw_prism(p, area, vals, lambda i, v: self.load_color(v))
        vents = self._bar_vents(area, vals)
        for vx, vy, k in vents:
            p.setPen(Qt.NoPen)
            p.setBrush(self.alpha(QColor(255, 255, 255), 190))
            p.drawEllipse(QPointF(vx, vy), 1.6, 1.6)
        self._rising_particles(p, vents, max(8, int(area.width() * area.height() / 2600)),
                               [CYAN, VIOLET, PINK], area.height() * 0.5, 7, now)
        self._paint_timeaxis(p, rect)


class LavaRiverStyle(BarChartStyle):
    """风格 05 · 熔岩之河"""
    key = "lava_river"
    title = "熔岩之河"
    group = "常规"

    def paint(self, p, rect, history, now):
        area = self._plot_area(rect)
        vals = history.bars(now, self._bar_count(rect.width()))
        floor = self._draw_prism(p, area, vals, lambda i, v: self.lava_color(v))
        river = QRectF(area.left(), floor - 5, area.width(), 10)
        rg = QLinearGradient(river.left(), 0, river.right(), 0)
        rg.setColorAt(0.0, self.alpha(AMBER, 0))
        rg.setColorAt(0.2, self.alpha(AMBER, 210))
        rg.setColorAt(0.5, self.alpha(ORANGE, 235))
        rg.setColorAt(0.8, self.alpha(AMBER, 210))
        rg.setColorAt(1.0, self.alpha(AMBER, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawRoundedRect(river, 4, 4)
        # 河流上流动的火星
        rnd = random.Random(8)
        p.setPen(Qt.NoPen)
        for i in range(40):
            ph = (now * 0.02 + rnd.random()) % 1.0
            x = river.left() + ph * river.width()
            y = river.top() + 2 + math.sin(i * 7.3 + now * 0.9) * 2
            p.setBrush(self.alpha(self.mix(AMBER, RED, rnd.random()),
                                  int(190 * (0.5 + 0.5 * math.sin(now + i)))))
            p.drawEllipse(QPointF(x, y), 1.0, 1.0)
        self._rising_particles(p, self._bar_vents(area, vals),
                               max(5, int(area.width() * area.height() / 4000)),
                               [AMBER, ORANGE, RED], area.height() * 0.3, 5, now)
        self._paint_timeaxis(p, rect)


class EnergyCrystalStyle(BarChartStyle):
    """风格 07 · 能量水晶"""
    key = "energy_crystal"
    title = "能量水晶"
    group = "常规"

    def paint(self, p, rect, history, now):
        area = self._plot_area(rect)
        vals = history.bars(now, self._bar_count(rect.width(), 12, 10))
        if not vals:
            return
        bw = area.width() / len(vals)
        floor = area.bottom()
        spike = max(5, bw * 0.7)
        vents = []
        for i, v in enumerate(vals):
            h = self.clamp(v, 0, 100) / 100.0 * (area.height() - spike - 6)
            x = area.left() + i * bw
            y = floor - h
            col = self.load_color(v)
            cxp = x + bw / 2
            top = QPolygonF([QPointF(cxp - bw * 0.32, y), QPointF(cxp + bw * 0.32, y),
                             QPointF(cxp, y - spike)])
            p.setPen(QPen(QColor(255, 255, 255, 90), 1))
            p.setBrush(self.lighten(col, 1.8))
            p.drawPolygon(top)
            left = QPolygonF([QPointF(x, y), QPointF(cxp - bw * 0.32, y),
                              QPointF(cxp - bw * 0.32, y + h), QPointF(x, floor)])
            p.setPen(QPen(QColor(0, 0, 0, 24), 1))
            p.setBrush(self.lighten(col, 1.3))
            p.drawPolygon(left)
            right = QPolygonF([QPointF(cxp + bw * 0.32, y), QPointF(x + bw, y),
                               QPointF(x + bw, floor), QPointF(cxp + bw * 0.32, y + h)])
            p.setBrush(self.darken(col, 0.72))
            p.drawPolygon(right)
            ig = QLinearGradient(0, y, 0, floor)
            ig.setColorAt(0.0, self.alpha(col, 130))
            ig.setColorAt(1.0, self.alpha(col, 30))
            p.setBrush(ig)
            p.drawRect(QRectF(cxp - bw * 0.10, y + h * 0.12, bw * 0.20, h * 0.88))
            vents.append((cxp, y - spike, v / 100.0))
        self._rising_particles(p, vents, max(6, int(area.width() * area.height() / 3600)),
                               [QColor(150, 220, 255), QColor(200, 170, 255)],
                               area.height() * 0.4, 13, now, spread=0.25)
        self._paint_timeaxis(p, rect)


class DataPyreStyle(BarChartStyle):
    """风格 08 · 数据圣火"""
    key = "data_pyre"
    title = "数据圣火"
    group = "常规"

    def paint(self, p, rect, history, now):
        area = self._plot_area(rect)
        vals = history.bars(now, self._bar_count(rect.width()))
        if not vals:
            return
        bw = area.width() / len(vals)
        floor = area.bottom()
        rnd = random.Random(2)
        p.save()
        for i, v in enumerate(vals):
            h = self.clamp(v, 0, 100) / 100.0 * (area.height() - 14)
            x = area.left() + i * bw
            y = floor - h
            col = self.mix(WOOD, self.lighten(WOOD, 1.35), v / 100.0)
            p.setPen(QPen(QColor(0, 0, 0, 30), 1))
            p.setBrush(self.darken(col, 0.8))
            p.drawRect(QRectF(x, y, bw, h))
            p.setBrush(self.lighten(col, 1.2))
            p.drawRect(QRectF(x + 1, y + 1, bw - 2, max(2, h * 0.15)))
            k = v / 100.0
            if k < 0.25:
                continue
            # 柱顶火焰
            cxp = x + bw / 2
            fh = (10 + 40 * k) * (0.7 + 0.6 * rnd.random())
            fw = bw * (1.6 + 1.2 * rnd.random())
            path = QPainterPath()
            path.moveTo(cxp - fw / 2, y)
            path.quadTo(cxp - fw * 0.38, y - fh * 0.6, cxp, y - fh)
            path.quadTo(cxp + fw * 0.38, y - fh * 0.6, cxp + fw / 2, y)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(self.alpha(self.mix(ORANGE, AMBER, k), int(120 + 100 * k)))
            p.drawPath(path)
            inner = QPainterPath()
            inner.moveTo(cxp - fw * 0.28, y)
            inner.quadTo(cxp - fw * 0.10, y - fh * 0.45, cxp, y - fh * 0.72)
            inner.quadTo(cxp + fw * 0.10, y - fh * 0.45, cxp + fw * 0.28, y)
            inner.closeSubpath()
            p.setBrush(self.alpha(self.mix(AMBER, QColor(255, 240, 170), 0.6), int(150 + 100 * k)))
            p.drawPath(inner)
        p.restore()
        self._paint_timeaxis(p, rect)


class LavaTunnelStyle(BarChartStyle):
    """风格 09 · 熔岩隧视"""
    key = "lava_tunnel"
    title = "熔岩隧视"
    group = "常规"

    def paint(self, p, rect, history, now):
        area = self._plot_area(rect)
        vals = history.bars(now, self._bar_count(rect.width(), 7, 14))
        if len(vals) < 2:
            return
        n = len(vals)
        bw = area.width() / n
        floor = area.bottom()
        # 隧道形状：中间高两侧低
        tunnel = []
        for i, v in enumerate(vals):
            side = (i - (n - 1) / 2.0) / ((n - 1) / 2.0)
            arch = (1 - abs(side) * 0.55)
            tunnel.append(self.clamp(v * 0.55 + arch * 45, 5, 99))
        p.setPen(QPen(GRID, 1))
        for i in range(n + 1):
            x = area.left() + i * bw
            p.drawLine(QPointF(x, floor), QPointF(area.center().x(), floor - area.height() * 0.35))
        for t in range(1, 5):
            yy = floor - (area.height() - 10) * t / 5.0
            p.drawLine(QPointF(area.left(), yy), QPointF(area.right(), yy))
        for i, v in enumerate(tunnel):
            h = self.clamp(v, 0, 100) / 100.0 * (area.height() - 10)
            x = area.left() + i * bw
            y = floor - h
            col = self.lava_color(self.clamp(v * 1.1, 0, 100))
            p.setPen(QPen(QColor(0, 0, 0, 28), 1))
            p.setBrush(self.darken(col, 0.65))
            p.drawRect(QRectF(x, y, bw, h))
            p.setBrush(col)
            p.drawRect(QRectF(x + bw * 0.12, y + 2, bw * 0.76, max(1, h - 4)))
        # 深处涌出的熔岩粒子
        rnd = random.Random(31)
        p.setPen(Qt.NoPen)
        for i in range(max(8, int(area.width() * area.height() / 2400))):
            side = rnd.random() * 2 - 1
            phase = (now * 0.05 + rnd.random()) % 1.0
            x = area.center().x() + side * area.width() * (0.5 - 0.45 * phase)
            y = floor - phase * area.height() * 0.85 - rnd.random() * 6
            col = self.mix(AMBER, RED, rnd.random() * 0.8)
            r = 0.8 + 3.2 * phase
            a = int(40 + 200 * phase * (0.5 + 0.5 * rnd.random()))
            p.setBrush(self.alpha(col, a))
            p.drawEllipse(QPointF(x, y), r, r)
        self._paint_timeaxis(p, rect)


class RadarStyle(ChartStyle):
    """雷达风格基类。"""

    def _center(self, rect):
        return rect.center().x(), rect.center().y()

    def _radius(self, rect):
        return min(rect.width(), rect.height()) * 0.46

    def _draw_grid(self, p, cx, cy, R, n_rings=4, n_rays=4):
        p.setPen(QPen(self.alpha(INK_SUB, 55), 1))
        for i in range(1, n_rings + 1):
            p.drawEllipse(QPointF(cx, cy), R * i / n_rings, R * i / n_rings)
        for a in range(0, 180, 180 // n_rays):
            p.drawLine(QPointF(cx, cy),
                       QPointF(cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))))

    def _paint_center_glow(self, p, cx, cy, R, cur):
        """雷达中心光斑，表示当前负载强度（无文字）。"""
        col = self.load_color(cur)
        rg = QRadialGradient(QPointF(cx, cy), R * 0.35)
        rg.setColorAt(0.0, self.alpha(col, 90))
        rg.setColorAt(1.0, self.alpha(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawEllipse(QPointF(cx, cy), R * 0.35, R * 0.35)


class RadarSpectrumStyle(RadarStyle):
    """雷达 02 · 环形频谱"""
    key = "radar_spectrum"
    title = "环形频谱"
    group = "雷达"

    def paint(self, p, rect, history, now):
        cx, cy = self._center(rect)
        R = self._radius(rect)
        self._draw_grid(p, cx, cy, R)
        vals = history.bars(now, self._bar_count(rect.width(), 3, 40))
        if len(vals) > 1:
            n = len(vals)
            for i, v in enumerate(vals):
                a = -90 + 300 * (i / (n - 1))
                h = R * 0.72 * v / 100
                col = self.load_color(v)
                x1 = cx + R * 0.26 * math.cos(math.radians(a))
                y1 = cy + R * 0.26 * math.sin(math.radians(a))
                x2 = cx + (R * 0.26 + h) * math.cos(math.radians(a))
                y2 = cy + (R * 0.26 + h) * math.sin(math.radians(a))
                p.setPen(QPen(self.alpha(col, 180), max(2, int(R * 0.016))))
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        ang = -90 + 300
        p.setPen(QPen(PINK, 2.5))
        p.drawLine(QPointF(cx, cy), QPointF(cx + R * math.cos(math.radians(ang)),
                                            cy + R * math.sin(math.radians(ang))))
        self._paint_center_glow(p, cx, cy, R, history.current(now))
        self._paint_timeaxis(p, rect)


class RadarBioStyle(RadarStyle):
    """雷达 05 · 生物荧光"""
    key = "radar_bio"
    title = "生物荧光"
    group = "雷达"

    def paint(self, p, rect, history, now):
        cx, cy = self._center(rect)
        R = self._radius(rect)
        screen = QRectF(cx - R - 16, cy - R - 16, 2 * R + 32, 2 * R + 32)
        p.setBrush(QColor(8, 26, 36, 220))
        p.setPen(QPen(self.alpha(CYAN, 70), 1))
        p.drawEllipse(screen)
        series = history.series(now)
        if len(series) > 1:
            n = len(series)
            p.save()
            p.setClipRect(screen)
            p.setPen(QPen(self.alpha(QColor(0, 230, 190), 55), 1))
            for i in range(1, 4):
                p.drawEllipse(QPointF(cx, cy), R * i / 4, R * i / 4)
            for a in range(0, 180, 30):
                p.drawLine(QPointF(cx, cy),
                           QPointF(cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))))
            for i, v in enumerate(series):
                a = -90 + 300 * (i / (n - 1))
                rad = R * (0.15 + 0.75 * v / 100)
                x = cx + rad * math.cos(math.radians(a))
                y = cy + rad * math.sin(math.radians(a))
                p.setPen(Qt.NoPen)
                p.setBrush(self.alpha(self.mix(QColor(0, 230, 190), QColor(0, 170, 255), v / 100),
                                      int(70 + 180 * i / (n - 1))))
                p.drawEllipse(QPointF(x, y), 2 + 2.2 * (i / (n - 1)), 2 + 2.2 * (i / (n - 1)))
            ang = -90 + 300
            p.setPen(QPen(QColor(0, 245, 210), 2.5))
            p.drawLine(QPointF(cx, cy), QPointF(cx + R * math.cos(math.radians(ang)),
                                                cy + R * math.sin(math.radians(ang))))
            p.restore()
        self._paint_timeaxis(p, rect)


class RadarRadialStyle(RadarStyle):
    """雷达 07 · 放射柱状雷达"""
    key = "radar_radial"
    title = "放射柱状雷达"
    group = "雷达"

    def paint(self, p, rect, history, now):
        cx, cy = self._center(rect)
        R = self._radius(rect)
        self._draw_grid(p, cx, cy, R)
        vals = history.bars(now, self._bar_count(rect.width(), 3, 40))
        if len(vals) > 1:
            n = len(vals)
            for i, v in enumerate(vals):
                a = -90 + 300 * (i / (n - 1))
                h = R * 0.80 * v / 100
                col = self.load_color(v)
                x0 = cx + R * 0.14 * math.cos(math.radians(a))
                y0 = cy + R * 0.14 * math.sin(math.radians(a))
                x1 = cx + (R * 0.14 + h) * math.cos(math.radians(a))
                y1 = cy + (R * 0.14 + h) * math.sin(math.radians(a))
                p.setPen(QPen(self.alpha(col, 170), max(1.8, R * 0.010)))
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                p.setPen(Qt.NoPen)
                p.setBrush(self.alpha(col, 230))
                p.drawEllipse(QPointF(x1, y1), 2.6, 2.6)
        ang = -90 + 300
        p.setPen(QPen(PINK, 2.5))
        p.drawLine(QPointF(cx, cy), QPointF(cx + R * math.cos(math.radians(ang)),
                                            cy + R * math.sin(math.radians(ang))))
        self._paint_center_glow(p, cx, cy, R, history.current(now))
        self._paint_timeaxis(p, rect)


class RadarDigitalStyle(RadarStyle):
    """雷达 09 · 数码雷达"""
    key = "radar_digital"
    title = "数码雷达"
    group = "雷达"

    def paint(self, p, rect, history, now):
        cx, cy = self._center(rect)
        R = self._radius(rect)
        self._draw_grid(p, cx, cy, R, n_rays=12)
        series = history.series(now)
        if len(series) > 1:
            n = len(series)
            for i, v in enumerate(series):
                a = -90 + 300 * (i / (n - 1))
                rad = R * (0.18 + 0.70 * v / 100)
                x = cx + rad * math.cos(math.radians(a))
                y = cy + rad * math.sin(math.radians(a))
                col = self.load_color(v)
                p.setPen(Qt.NoPen)
                p.setBrush(self.alpha(col, int(80 + 175 * i / (n - 1))))
                p.drawRect(QRectF(x - 1.8, y - 1.8, 3.6, 3.6))
        ang = -90 + 300
        hx = cx + R * math.cos(math.radians(ang))
        hy = cy + R * math.sin(math.radians(ang))
        rg = QRadialGradient(QPointF(hx, hy), 40)
        rg.setColorAt(0.0, self.alpha(CYAN, 140))
        rg.setColorAt(1.0, self.alpha(CYAN, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawEllipse(QPointF(hx, hy), 40, 40)
        p.setPen(QPen(CYAN, 2.5))
        p.drawLine(QPointF(cx, cy), QPointF(hx, hy))
        self._paint_center_glow(p, cx, cy, R, history.current(now))
        self._paint_timeaxis(p, rect)


class CrtStyle(ChartStyle):
    """CRT 屏幕风格基类：暗色屏幕 + 扫描线 + 辉光波形。"""

    screen_color = QColor(8, 26, 14, 215)
    glow_color = GREEN
    glow_width = 5
    line_color = QColor(60, 255, 120)
    line_width = 2

    def _scanlines(self, p, inner):
        p.setPen(QPen(QColor(0, 0, 0, 42), 1))
        y = inner.top()
        while y < inner.bottom():
            p.drawLine(inner.left(), y, inner.right(), y)
            y += 3

    def _series_poly(self, inner, series):
        """把采样值序列映射成折线 poly（旧 → 新）。少于 2 点时返回空 poly。"""
        n = len(series)
        if n < 2:
            return QPolygonF()
        poly = QPolygonF()
        for i, v in enumerate(series):
            x = inner.left() + inner.width() * i / (n - 1)
            y = inner.bottom() - self.clamp(v, 0, 100) / 100.0 * inner.height()
            poly.append(QPointF(x, y))
        return poly

    def paint(self, p, rect, history, now):
        scr = self._plot_area(rect)
        p.setBrush(self.screen_color)
        p.setPen(QPen(self.alpha(INK_SUB, 90), 1))
        p.drawRoundedRect(scr, 8, 8)
        inner = scr.adjusted(4, 4, -4, -4)
        series = history.series(now)
        if len(series) > 1:
            p.save()
            p.setClipRect(inner)
            self._scanlines(p, inner)
            n = len(series)
            for shift, w in [(0, self.glow_width), (2, 3), (5, 1.8), (9, 1.2)]:
                poly = QPolygonF()
                for i, v in enumerate(series):
                    x = inner.left() + inner.width() * i / n + shift * 0.4
                    y = inner.bottom() - self.clamp(v, 0, 100) / 100.0 * inner.height()
                    poly.append(QPointF(x, y))
                p.setPen(QPen(self.alpha(self.glow_color, int(50 - w * 5)), w))
                p.drawPolyline(poly)
            if self.line_width > 0:
                p.setPen(QPen(self.line_color, self.line_width))
                p.drawPolyline(self._series_poly(inner, series))
            p.restore()
        self._paint_timeaxis(p, rect)


class CrtGreenStyle(CrtStyle):
    """CRT 01 · 绿色示波器"""
    key = "crt_green"
    title = "绿色示波器"
    group = "CRT"


class CrtAmberStyle(CrtStyle):
    """CRT 02 · 琥珀终端"""
    key = "crt_amber"
    title = "琥珀终端"
    group = "CRT"
    screen_color = QColor(28, 18, 6, 215)
    glow_color = ORANGE
    line_color = QColor(255, 190, 70)
    line_width = 2


class CrtGlowStyle(CrtStyle):
    """CRT 06 · 辉光余晖"""
    key = "crt_glow"
    title = "辉光余晖"
    group = "CRT"
    screen_color = QColor(8, 20, 16, 215)
    glow_color = QColor(0, 255, 170)
    line_color = QColor(0, 255, 170)
    line_width = 0


# ================================================================
# 风格注册表（分组）
# ================================================================
STYLE_GROUPS = [
    ("常规", [NeonEmberStyle, LavaRiverStyle, EnergyCrystalStyle, DataPyreStyle, LavaTunnelStyle]),
    ("雷达", [RadarSpectrumStyle, RadarBioStyle, RadarRadialStyle, RadarDigitalStyle]),
    ("CRT", [CrtGreenStyle, CrtAmberStyle, CrtGlowStyle]),
]


class MachineLoadWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.collectMachineLoad)
        self.timer.setInterval(SAMPLE_INTERVAL)
        self.machineLoad = MachineLoad.getInstance()
        self.history = CpuHistory()
        self.styleGroups = STYLE_GROUPS
        self.styles = [cls for group in self.styleGroups for cls in group[1]]
        self.styleCache = {}
        self.currentStyle = None
        self.createStyleMenu()
        self.loadStyle()
        self.timer.start()

    def finalize(self):
        self.timer.stop()
        self.history.clear()

    def getStyle(self, key):
        style = self.styleCache.get(key)
        if style is None:
            cls = next((c for c in self.styles if c.key == key), self.styles[0])
            style = cls()
            self.styleCache[key] = style
        return style

    def createStyleMenu(self):
        self.menu = QMenu(self)
        self.styleActions = {}
        for gi, (groupTitle, classes) in enumerate(self.styleGroups):
            if gi > 0:
                self.menu.addSection(groupTitle)
            for cls in classes:
                action = self.menu.addAction(cls.title)
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, k=cls.key: self.setStyle(k))
                self.styleActions[cls.key] = action
        self.menuButton = QToolButton(self)
        self.menuButton.setArrowType(Qt.DownArrow)
        self.menuButton.setPopupMode(QToolButton.InstantPopup)
        self.menuButton.setMenu(self.menu)
        self.menuButton.setToolTip(self.tr("切换显示风格"))
        self.menuButton.setStyleSheet("""
            QToolButton { background: rgba(255,255,255,215); border: 1px solid rgba(130,142,160,130);
                border-radius: 4px; }
            QToolButton:hover { background: rgba(255,255,255,255); }
            QToolButton::menu-indicator { image: none; }
        """)
        self.menuButton.setFixedSize(24, 22)
        self.menuButton.move(4, 4)

    def resizeEvent(self, event):
        QWidget.resizeEvent(self, event)
        self.menuButton.move(self.width() - self.menuButton.width() - 4, 4)

    def loadStyle(self):
        key = None
        try:
            settings = self.window().platform.getSettings()
            key = settings.value("machineLoadStyle")
        except Exception:
            pass
        if not key:
            key = self.styles[0].key
        self.setStyle(key)

    def setStyle(self, key):
        self.currentStyle = self.getStyle(key)
        key = self.currentStyle.key
        for k, action in self.styleActions.items():
            action.setChecked(k == key)
        try:
            settings = self.window().platform.getSettings()
            settings.setValue("machineLoadStyle", key)
        except Exception:
            pass
        if self.isVisible():
            self.update()

    def collectMachineLoad(self):
        rate = self.machineLoad.getLoad()
        # getLoad 返回 0~1 的小数，绘制层按 0~100 百分比处理，需换算成百分数
        self.history.add(rate * 100, time.time())
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        if self.history.is_empty() or self.currentStyle is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        painter.setPen(QPen(CARD_BORDER, 1))
        painter.setBrush(CARD)
        painter.drawRoundedRect(rect, 12, 12)
        inner = rect.adjusted(9, 9, -9, -9)
        self.currentStyle.paint(painter, inner, self.history, time.time())
        painter.end()


# ================================================================
# 跨平台 CPU 占用率采集
# ================================================================
if os.name == "nt":
    import ctypes.wintypes
    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.wintypes.DWORD),
                    ("dwHighDateTime", ctypes.wintypes.DWORD)]

        def __int__(self):
            return self.dwHighDateTime * 0x100000000 + self.dwLowDateTime

    GetSystemTimes = ctypes.windll.kernel32.GetSystemTimes

    class MachineLoad:
        _instance = None

        @staticmethod
        def getInstance():
            if MachineLoad._instance is None:
                MachineLoad._instance = MachineLoad()
            return MachineLoad._instance

        def __init__(self):
            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
            self.idle0, self.kernel0, self.user0 = int(idle), int(kernel), int(user)

        def getLoad(self):
            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
            idle1, kernel1, user1 = int(idle), int(kernel), int(user)
            a, b, c = idle1 - self.idle0, kernel1 - self.kernel0, user1 - self.user0
            self.idle0, self.kernel0, self.user0 = idle1, kernel1, user1
            if (b + c) == 0:
                return 1
            return (b + c - a) / (b + c)

elif os.path.exists("/proc/stat"):
    class MachineLoad:
        _instance = None
        lastStatics = None

        @staticmethod
        def getInstance():
            if MachineLoad._instance is None:
                MachineLoad._instance = MachineLoad()
            return MachineLoad._instance

        def getLoad(self):
            try:
                with io.open("/proc/stat", encoding="ascii") as statfile:
                    firstline = statfile.readline()
                    if firstline.endswith("\n"):
                        firstline = firstline[:-1]
                    statics = list(map(int, firstline.split()[1:8]))
                    if self.lastStatics is None:
                        self.lastStatics = statics
                        return 0.0
                    delta = list(map(lambda new, old: new - old, statics, self.lastStatics))
                    self.lastStatics = statics
                    user, nice, system, idle, iowait, irq, softirq = delta
                    return (sum(delta) - idle) / sum(delta)
            except Exception:
                return 0

else:
    class MachineLoad:
        _instance = None

        @staticmethod
        def getInstance():
            if MachineLoad._instance is None:
                MachineLoad._instance = MachineLoad()
            return MachineLoad._instance

        def getLoad(self):
            return 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MachineLoadWidget()
    window.show()
    sys.exit(app.exec())