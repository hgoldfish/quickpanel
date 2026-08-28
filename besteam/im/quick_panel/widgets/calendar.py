# -*- coding: utf-8 -*-
"""综合时间控件：左侧时间 + 农历 + 节气，右侧番茄钟。

以面向对象方式组织：
- LunarCalendar / LunarDate：农历转换与日期值对象
- SolarTerms / TermContext：节气计算与上下文值对象
- Pomodoro / PomodoroPhase：番茄钟状态机
- CalendarWidget：控件，组合上述对象。

数据表（农历 1900-2100、二十四节气）为天文历法事实数据；
番茄钟按 25 分钟专注 / 5 分钟短休 / 15 分钟长休（每 4 个番茄）流转。
"""
import time
from datetime import date, datetime
from enum import Enum

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import QFrame, QMenu, QMessageBox

__all__ = ["CalendarWidget"]


# ================================================================
# 农历
# ================================================================
class LunarDate:
    """农历日期值对象，负责中文格式化。"""

    MONTH_CN = ["", "正月", "二月", "三月", "四月", "五月", "六月",
                "七月", "八月", "九月", "十月", "冬月", "腊月"]
    DAY_PREFIX = ["初", "十", "廿", "卅"]
    # 索引 0 为空占位，使 day%10 可直接作为下标（1→一 … 9→九）
    DAY_DIGIT = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

    def __init__(self, month, day, is_leap=False):
        self.month = month
        self.day = day
        self.is_leap = is_leap

    @property
    def month_cn(self):
        return self.MONTH_CN[self.month]

    @property
    def day_cn(self):
        if self.day == 10:
            return "初十"
        if self.day == 20:
            return "二十"
        if self.day == 30:
            return "三十"
        return self.DAY_PREFIX[self.day // 10] + self.DAY_DIGIT[self.day % 10]

    def __str__(self):
        prefix = "闰" if self.is_leap else ""
        return prefix + self.month_cn + self.day_cn


class LunarCalendar:
    """公历到农历的转换（1900-2100）。

    INFO 为公开历法数据，采用通行 lunarInfo 编码：每年一个整数，低 4 位 =
    闰月月份（0 表示无闰月），bit4..15 = 十二个普通月大小（1 表示大月 30 天，
    0 表示小月 29 天），bit16 = 闰月大小（1 表示大月）。
    """

    BASE_YEAR = 1900
    MAX_YEAR = 2100
    EPOCH = date(1900, 1, 31)

    INFO = [
        0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,
        0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,
        0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,
        0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,
        0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,
        0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,
        0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,
        0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b6a0, 0x195a6,
        0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,
        0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,
        0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,
        0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,
        0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,
        0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,
        0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,
        0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,
        0x0a2e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,
        0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,
        0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,
        0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,
        0x0d520,
    ]

    def _leap_month(self, year):
        return self.INFO[year - self.BASE_YEAR] & 0xf

    def _leap_days(self, year):
        if not self._leap_month(year):
            return 0
        return 30 if self.INFO[year - self.BASE_YEAR] & 0x10000 else 29

    def _month_days(self, year, month):
        return 30 if self.INFO[year - self.BASE_YEAR] & (0x10000 >> month) else 29

    def _year_days(self, year):
        total = 348
        i = 0x8000
        while i > 0x8:
            if self.INFO[year - self.BASE_YEAR] & i:
                total += 1
            i >>= 1
        return total + self._leap_days(year)

    def from_solar(self, year, month, day):
        """公历转农历；超出 1900-01-31 至 2100-12-31 返回 None。"""
        if year < self.BASE_YEAR or year > self.MAX_YEAR:
            return None
        solar = date(year, month, day)
        if solar < self.EPOCH:
            return None
        offset = (solar - self.EPOCH).days
        lunar_year = self.BASE_YEAR
        while lunar_year <= self.MAX_YEAR and offset >= self._year_days(lunar_year):
            offset -= self._year_days(lunar_year)
            lunar_year += 1
        leap = self._leap_month(lunar_year)
        for m in range(1, 13):
            if leap > 0 and m == leap + 1:
                if offset < self._leap_days(lunar_year):
                    return LunarDate(leap, offset + 1, True)
                offset -= self._leap_days(lunar_year)
            if offset < self._month_days(lunar_year, m):
                return LunarDate(m, offset + 1, False)
            offset -= self._month_days(lunar_year, m)
        return LunarDate(12, offset + 1, False)


# ================================================================
# 二十四节气
# ================================================================
class TermContext:
    """节气上下文：当前节气、下一节气、距下一节气天数。"""

    def __init__(self, current="", next_term="", days=0):
        self.current = current
        self.next_term = next_term
        self.days = days

    def __bool__(self):
        return bool(self.current)


class SolarTerms:
    """二十四节气计算（1900-2100）。"""

    BASE_YEAR = 1900
    MAX_YEAR = 2100

    NAMES = [
        "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
        "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑",
        "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
    ]

    # 公开历法数据，通行 sTermInfo 编码。每 30 个 hex 字符编码一年：每 5 字符
    # 转成一个十进制数，再按「1位+2位+1位+2位」拆成相邻两月共 4 个节气的日。
    INFO = [
        '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e', '97bcf97c3598082c95f8c965cc920f',
        '97bd0b06bdb0722c965ce1cfcc920f', 'b027097bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e',
        '97bcf97c359801ec95f8c965cc920f', '97bd0b06bdb0722c965ce1cfcc920f', 'b027097bd097c36b0b6fc9274c91aa',
        '97b6b97bd19801ec9210c965cc920e', '97bcf97c359801ec95f8c965cc920f', '97bd0b06bdb0722c965ce1cfcc920f',
        'b027097bd097c36b0b6fc9274c91aa', '9778397bd19801ec9210c965cc920e', '97b6b97bd19801ec95f8c965cc920f',
        '97bd09801d98082c95f8e1cfcc920f', '97bd097bd097c36b0b6fc9210c8dc2', '9778397bd197c36c9210c9274c91aa',
        '97b6b97bd19801ec95f8c965cc920e', '97bd09801d98082c95f8e1cfcc920f', '97bd097bd097c36b0b6fc9210c8dc2',
        '9778397bd097c36c9210c9274c91aa', '97b6b97bd19801ec9210c965cc920e', '97bcf97c3598082c95f8e1cfcc920f',
        '97bd097bd097c36b0b6fc9210c8dc2', '9778397bd097c36c9210c9274c91aa', '97b6b97bd19801ec9210c965cc920e',
        '97bcf97c3598082c95f8c965cc920f', '97bd097bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b97bd19801ec9210c965cc920e', '97bcf97c3598082c95f8c965cc920f', '97bd097bd097c35b0b6fc920fb0722',
        '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e', '97bcf97c359801ec95f8c965cc920f',
        '97bd097bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e',
        '97bcf97c359801ec95f8c965cc920f', '97bd097bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b97bd19801ec9210c965cc920e', '97bcf97c359801ec95f8c965cc920f', '97bd097bd07f595b0b6fc920fb0722',
        '9778397bd097c36b0b6fc9210c8dc2', '9778397bd19801ec9210c9274c920e', '97b6b97bd19801ec95f8c965cc920f',
        '97bd07f5307f595b0b0bc920fb0722', '7f0e397bd097c36b0b6fc9210c8dc2', '9778397bd097c36c9210c9274c920e',
        '97b6b97bd19801ec95f8c965cc920f', '97bd07f5307f595b0b0bc920fb0722', '7f0e397bd097c36b0b6fc9210c8dc2',
        '9778397bd097c36c9210c9274c91aa', '97b6b97bd19801ec9210c965cc920e', '97bd07f1487f595b0b0bc920fb0722',
        '7f0e397bd097c36b0b6fc9210c8dc2', '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e',
        '97bcf7f1487f595b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b97bd19801ec9210c965cc920e', '97bcf7f1487f595b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722',
        '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e', '97bcf7f1487f531b0b0bb0b6fb0722',
        '7f0e397bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa', '97b6b97bd19801ec9210c965cc920e',
        '97bcf7f1487f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b97bd19801ec9210c9274c920e', '97bcf7f0e47f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b0bc920fb0722',
        '9778397bd097c36b0b6fc9210c91aa', '97b6b97bd197c36c9210c9274c920e', '97bcf7f0e47f531b0b0bb0b6fb0722',
        '7f0e397bd07f595b0b0bc920fb0722', '9778397bd097c36b0b6fc9210c8dc2', '9778397bd097c36c9210c9274c920e',
        '97b6b7f0e47f531b0723b0b6fb0722', '7f0e37f5307f595b0b0bc920fb0722', '7f0e397bd097c36b0b6fc9210c8dc2',
        '9778397bd097c36b0b70c9274c91aa', '97b6b7f0e47f531b0723b0b6fb0721', '7f0e37f1487f595b0b0bb0b6fb0722',
        '7f0e397bd097c35b0b6fc9210c8dc2', '9778397bd097c36b0b6fc9274c91aa', '97b6b7f0e47f531b0723b0b6fb0721',
        '7f0e27f1487f595b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722',
        '9778397bd097c36b0b6fc9274c91aa', '97b6b7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722',
        '7f0e397bd097c35b0b6fc920fb0722', '9778397bd097c36b0b6fc9274c91aa', '97b6b7f0e47f531b0723b0b6fb0721',
        '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b0bc920fb0722', '9778397bd097c36b0b6fc9274c91aa',
        '97b6b7f0e47f531b0723b0787b0721', '7f0e27f0e47f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b0bc920fb0722',
        '9778397bd097c36b0b6fc9210c91aa', '97b6b7f0e47f149b0723b0787b0721', '7f0e27f0e47f531b0723b0b6fb0722',
        '7f0e397bd07f595b0b0bc920fb0722', '9778397bd097c36b0b6fc9210c8dc2', '977837f0e37f149b0723b0787b0721',
        '7f07e7f0e47f531b0723b0b6fb0722', '7f0e37f5307f595b0b0bc920fb0722', '7f0e397bd097c35b0b6fc9210c8dc2',
        '977837f0e37f14998082b0787b0721', '7f07e7f0e47f531b0723b0b6fb0721', '7f0e37f1487f595b0b0bb0b6fb0722',
        '7f0e397bd097c35b0b6fc9210c8dc2', '977837f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721',
        '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722', '977837f0e37f14998082b0787b06bd',
        '7f07e7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e397bd097c35b0b6fc920fb0722',
        '977837f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722',
        '7f0e397bd07f595b0b0bc920fb0722', '977837f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721',
        '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b0bc920fb0722', '977837f0e37f14998082b0787b06bd',
        '7f07e7f0e47f149b0723b0787b0721', '7f0e27f0e47f531b0b0bb0b6fb0722', '7f0e397bd07f595b0b0bc920fb0722',
        '977837f0e37f14998082b0723b06bd', '7f07e7f0e37f149b0723b0787b0721', '7f0e27f0e47f531b0723b0b6fb0722',
        '7f0e397bd07f595b0b0bc920fb0722', '977837f0e37f14898082b0723b02d5', '7ec967f0e37f14998082b0787b0721',
        '7f07e7f0e47f531b0723b0b6fb0722', '7f0e37f1487f595b0b0bb0b6fb0722', '7f0e37f0e37f14898082b0723b02d5',
        '7ec967f0e37f14998082b0787b0721', '7f07e7f0e47f531b0723b0b6fb0722', '7f0e37f1487f531b0b0bb0b6fb0722',
        '7f0e37f0e37f14898082b0723b02d5', '7ec967f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721',
        '7f0e37f1487f531b0b0bb0b6fb0722', '7f0e37f0e37f14898082b072297c35', '7ec967f0e37f14998082b0787b06bd',
        '7f07e7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e37f0e37f14898082b072297c35',
        '7ec967f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722',
        '7f0e37f0e366aa89801eb072297c35', '7ec967f0e37f14998082b0787b06bd', '7f07e7f0e47f149b0723b0787b0721',
        '7f0e27f1487f531b0b0bb0b6fb0722', '7f0e37f0e366aa89801eb072297c35', '7ec967f0e37f14998082b0723b06bd',
        '7f07e7f0e47f149b0723b0787b0721', '7f0e27f0e47f531b0723b0b6fb0722', '7f0e37f0e366aa89801eb072297c35',
        '7ec967f0e37f14998082b0723b06bd', '7f07e7f0e37f14998083b0787b0721', '7f0e27f0e47f531b0723b0b6fb0722',
        '7f0e37f0e366aa89801eb072297c35', '7ec967f0e37f14898082b0723b02d5', '7f07e7f0e37f14998082b0787b0721',
        '7f07e7f0e47f531b0723b0b6fb0722', '7f0e36665b66aa89801e9808297c35', '665f67f0e37f14898082b0723b02d5',
        '7ec967f0e37f14998082b0787b0721', '7f07e7f0e47f531b0723b0b6fb0722', '7f0e36665b66a449801e9808297c35',
        '665f67f0e37f14898082b0723b02d5', '7ec967f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721',
        '7f0e36665b66a449801e9808297c35', '665f67f0e37f14898082b072297c35', '7ec967f0e37f14998082b0787b06bd',
        '7f07e7f0e47f531b0723b0b6fb0721', '7f0e26665b66a449801e9808297c35', '665f67f0e37f1489801eb072297c35',
        '7ec967f0e37f14998082b0787b06bd', '7f07e7f0e47f531b0723b0b6fb0721', '7f0e27f1487f531b0b0bb0b6fb0722',
    ]

    def _day_of_term(self, year, n):
        """第 n 个节气（1-24，自小寒起）在公历 (n+1)//2 月的日。"""
        table = self.INFO[year - self.BASE_YEAR]
        info = [int(table[0:5], 16), int(table[5:10], 16), int(table[10:15], 16),
                int(table[15:20], 16), int(table[20:25], 16), int(table[25:30], 16)]
        days = []
        for num in info:
            s = str(num)
            days += [int(s[0]), int(s[1:3]), int(s[3]), int(s[4:6])]
        return days[n - 1]

    def context(self, when):
        """返回 when 所处的节气上下文。"""
        today = when.date()
        terms = []
        for y in range(when.year - 1, when.year + 2):
            if y < self.BASE_YEAR or y > self.MAX_YEAR:
                continue
            for n in range(1, 25):
                terms.append((datetime(y, (n + 1) // 2, self._day_of_term(y, n)),
                              self.NAMES[n - 1]))
        terms.sort()
        current = ""
        for moment, name in terms:
            if moment.date() > today:
                return TermContext(current, name, (moment.date() - today).days)
            current = name
        return TermContext()


# ================================================================
# 番茄钟
# ================================================================
class PomodoroPhase(Enum):
    """番茄钟阶段，枚举值 = 中文标签。"""

    FOCUS = "专注中"
    SHORT = "短休息"
    LONG = "长休息"

    @property
    def label(self):
        return self.value


class Pomodoro:
    """番茄钟状态机：专注可设置时长，短休 5 分钟，每 4 个番茄长休 15 分钟。

    tick() 返回事件字符串（"focus_done" / "break_done"）或 None，供上层在
    计时结束时弹出提醒。
    """

    FOCUS_OPTIONS = (25, 45, 60)  # 可选专注时长（分钟）
    SHORT_BREAK = 5 * 60
    LONG_BREAK = 15 * 60
    EVERY = 4

    def __init__(self):
        self.focus_minutes = self.FOCUS_OPTIONS[0]
        self.reset()

    def reset(self):
        self.phase = PomodoroPhase.FOCUS
        self.running = False
        self.completed = 0
        self.remaining = self.total
        self.deadline = 0.0

    @property
    def total(self):
        """当前阶段的时长（秒）。"""
        if self.phase is PomodoroPhase.FOCUS:
            return self.focus_minutes * 60
        if self.phase is PomodoroPhase.SHORT:
            return self.SHORT_BREAK
        return self.LONG_BREAK

    def set_focus_minutes(self, minutes):
        """设置专注时长（分钟）；仅在未运行时生效，运行中返回 False。"""
        if self.running:
            return False
        self.focus_minutes = minutes
        if self.phase is PomodoroPhase.FOCUS:
            self.remaining = self.total
        return True

    def time_left(self):
        if self.running:
            return max(0, int(self.deadline - time.monotonic()))
        return self.remaining

    def toggle(self):
        if self.running:
            self.remaining = self.time_left()
            self.running = False
        else:
            self.deadline = time.monotonic() + self.remaining
            self.running = True

    def tick(self):
        """每秒调用；阶段结束时切换并返回事件，其余返回 None。"""
        if not self.running or self.time_left() > 0:
            return None
        if self.phase is PomodoroPhase.FOCUS:
            self.completed += 1
            self.phase = (PomodoroPhase.LONG
                          if self.completed % self.EVERY == 0
                          else PomodoroPhase.SHORT)
            self.remaining = self.total
            self.deadline = time.monotonic() + self.remaining
            return "focus_done"
        self.phase = PomodoroPhase.FOCUS
        self.remaining = self.total
        self.running = False
        return "break_done"


# ================================================================
# 控件
# ================================================================
class CalendarWidget(QFrame):
    """显示当前时间、农历、节气，以及一个可交互的番茄钟。"""

    _WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # 配色（延续 machine_load 的明亮风格）
    INK_MAIN = QColor(38, 48, 66)
    INK_SUB = QColor(110, 122, 144)
    INK_FAINT = QColor(150, 160, 178)
    DIVIDER = QColor(150, 160, 178, 60)
    VIOLET = QColor(124, 92, 255)
    ORANGE = QColor(255, 140, 30)
    TOMATO = QColor(255, 82, 82)
    TOMATO_SOFT = QColor(255, 82, 82, 40)

    def __init__(self, parent=None):
        QFrame.__init__(self, parent)
        self.lunar = LunarCalendar()
        self.terms = SolarTerms()
        self.pomodoro = Pomodoro()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_timeout)
        self.timer.start()

    def finalize(self):
        self.timer.stop()

    def _on_timeout(self):
        event = self.pomodoro.tick()
        if event == "focus_done":
            self._notify(self.tr("专注完成"), self.tr("专注时间结束，休息一下吧！"))
        elif event == "break_done":
            self._notify(self.tr("休息结束"), self.tr("休息结束，开始下一个番茄吧！"))
        if self.isVisible():
            self.update()

    def _notify(self, title, text):
        # 延迟到事件循环弹出，避免在 timer slot 内同步 exec 阻塞。
        QTimer.singleShot(0, lambda: QMessageBox.information(self.window(), title, text))

    # ---- 固定字号（像素，不随画布缩放）----
    FONT_TIME = 32
    FONT_DATE = 11
    FONT_LUNAR = 10
    FONT_TERM = 10
    FONT_POMO_TIME = 11
    FONT_POMO_SUB = 8
    FONT_POMO_STATE = 10

    # ---- 番茄钟几何（像素，布局与绘制共用，避免两处魔法数失步）----
    RING_RADIUS = 22
    RING_WIDTH = 5
    POMO_GAP = 4
    POMO_STATE_H = 14
    POMO_DOTS_H = 8

    def _font(self, pt, bold=False):
        font = QFont()
        font.setPointSizeF(pt)
        font.setBold(bold)
        return font

    def _text_width(self, pt, bold, text):
        return QFontMetrics(self._font(pt, bold)).horizontalAdvance(text)

    # ---- 自适应布局：时间(左) / 日期(中，窄时省略) / 番茄钟(右) ----
    def _layout(self):
        """返回 (time_rect, date_rect, pomo_rect)；窄时 date_rect 为 None。"""
        w = self.width()
        h = self.height()
        margin = 10
        inner = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)

        # 块宽用实测文字宽度 / 固定像素，不随画布缩放
        time_w = self._text_width(self.FONT_TIME, True, "00:00") + 8
        pomo_w = max(2 * self.RING_RADIUS + 8, 52)

        gap = 12
        min_date_w = 120

        date_w = inner.width() - time_w - pomo_w - 2 * gap
        time_rect = QRectF(inner.x(), inner.y(), time_w, inner.height())
        pomo_rect = QRectF(inner.right() - pomo_w, inner.y(), pomo_w, inner.height())

        if date_w >= min_date_w:
            date_rect = QRectF(inner.x() + time_w + gap, inner.y(), date_w, inner.height())
        else:
            date_rect = None
        return time_rect, date_rect, pomo_rect

    def _pomodoro_rect(self):
        return self._layout()[2]

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
        time_rect, date_rect, pomo_rect = self._layout()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        now = datetime.now()

        # 分隔线：三栏两条，两栏一条
        painter.setPen(QPen(self.DIVIDER, 1))
        painter.drawLine(QPointF(time_rect.right() + 6, time_rect.top() + 2),
                         QPointF(time_rect.right() + 6, time_rect.bottom() - 2))
        if date_rect is not None:
            painter.drawLine(QPointF(date_rect.right() + 6, date_rect.top() + 2),
                             QPointF(date_rect.right() + 6, date_rect.bottom() - 2))

        # 时间块
        self._draw_text(painter, time_rect, now.strftime("%H:%M"),
                        self.INK_MAIN, self.FONT_TIME, True, Qt.AlignCenter)

        # 日期块（居中）
        if date_rect is not None:
            self._draw_date_block(painter, date_rect, now)

        # 番茄钟块
        self._draw_pomodoro(painter, pomo_rect)

        painter.end()

    def _draw_date_block(self, painter, rect, now):
        lunar = self.lunar.from_solar(now.year, now.month, now.day)
        context = self.terms.context(now)

        rows = [("%d月%d日 %s" % (now.month, now.day, self._WEEK_CN[now.weekday()]),
                 self.INK_SUB, self.FONT_DATE, False)]
        if lunar:
            rows.append(("农历" + str(lunar), self.VIOLET, self.FONT_LUNAR, True))
        if context:
            rows.append(("%s · 距%s%d天" % (context.current, context.next_term, context.days),
                         self.ORANGE, self.FONT_TERM, False))

        # 三行靠拢，整体垂直居中
        line_h = 15
        total_h = line_h * len(rows)
        y = rect.center().y() - total_h / 2.0
        for text, color, pt, bold in rows:
            self._draw_text(painter, QRectF(rect.x(), y, rect.width(), line_h),
                            text, color, pt, bold, Qt.AlignCenter)
            y += line_h

    def _draw_pomodoro(self, painter, rect):
        ring_r = self.RING_RADIUS
        ring_h = 2 * ring_r
        gap = self.POMO_GAP
        state_h = self.POMO_STATE_H
        dots_h = self.POMO_DOTS_H
        total_h = ring_h + gap + state_h + gap + dots_h

        # 整体垂直居中、水平靠右（rect 已位于最右）
        top = rect.center().y() - total_h / 2.0
        cx = rect.center().x()
        cy = top + ring_r
        ring_rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)

        total = self.pomodoro.total
        remaining = self.pomodoro.time_left()
        progress = remaining / float(total) if total else 0.0
        ring_w = self.RING_WIDTH

        painter.setPen(QPen(self.TOMATO_SOFT, ring_w, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)
        if progress > 0:
            painter.setPen(QPen(self.TOMATO, ring_w, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(ring_rect, 90 * 16, -int(progress * 360 * 16))

        self._draw_text(painter,
                        QRectF(cx - ring_r, cy - 10, ring_r * 2, 16),
                        "%02d:%02d" % (remaining // 60, remaining % 60),
                        self.INK_MAIN, self.FONT_POMO_TIME, True, Qt.AlignCenter)
        self._draw_text(painter,
                        QRectF(cx - ring_r, cy + 4, ring_r * 2, 12),
                        "剩余", self.INK_FAINT, self.FONT_POMO_SUB, False, Qt.AlignCenter)

        state_y = top + ring_h + gap
        self._draw_text(painter,
                        QRectF(rect.x(), state_y, rect.width(), state_h),
                        self._state_text(), self.INK_MAIN, self.FONT_POMO_STATE, True,
                        Qt.AlignCenter)

        dots_y = state_y + state_h + gap
        for i in range(4):
            dx = rect.center().x() + (i - 1.5) * 12
            center = QPointF(dx, dots_y)
            if i < self.pomodoro.completed % 4:
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.TOMATO)
            else:
                painter.setPen(QPen(self.TOMATO, 1.2))
                painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, 3.5, 3.5)

    def _state_text(self):
        if (not self.pomodoro.running
                and self.pomodoro.completed == 0
                and self.pomodoro.remaining == self.pomodoro.total):
            return "点击开始"
        return self.pomodoro.phase.label

    def _draw_text(self, painter, rect, text, color, pt, bold, align):
        painter.setFont(self._font(pt, bold))
        painter.setPen(color)
        painter.drawText(rect, align, text)

    # ---- 番茄钟交互 ----
    def mousePressEvent(self, event):
        if not self._pomodoro_rect().contains(event.pos()):
            QFrame.mousePressEvent(self, event)
            return
        if event.button() == Qt.LeftButton:
            self.pomodoro.toggle()
            self.update()
        elif event.button() == Qt.RightButton:
            self._show_pomodoro_menu(event.pos())

    def _show_pomodoro_menu(self, pos):
        menu = QMenu(self)
        duration_menu = menu.addMenu(self.tr("专注时长"))
        for minutes in Pomodoro.FOCUS_OPTIONS:
            action = duration_menu.addAction(self.tr("%1 分钟").arg(minutes))
            action.setCheckable(True)
            action.setChecked(minutes == self.pomodoro.focus_minutes)
            action.triggered.connect(
                lambda checked=False, m=minutes: self._set_focus_minutes(m))
        menu.addSeparator()
        reset_action = menu.addAction(self.tr("重置"))
        reset_action.triggered.connect(self._reset_pomodoro)
        menu.exec_(self.mapToGlobal(pos))

    def _set_focus_minutes(self, minutes):
        if self.pomodoro.set_focus_minutes(minutes):
            self.update()

    def _reset_pomodoro(self):
        self.pomodoro.reset()
        self.update()
