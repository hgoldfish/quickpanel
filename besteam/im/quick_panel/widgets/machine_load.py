import os
import ctypes
import io
from PyQt5.QtCore import QPoint, QRect, QTimer, Qt
from PyQt5.QtGui import QPainter, QPen, QPolygon
from PyQt5.QtWidgets import QWidget

__all__ = ["MachineLoadWidget"]

class MachineLoadWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        #self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.timer = QTimer()
        self.timer.timeout.connect(self.collectMachineLoad)
        self.loads = []
        self.maxLength = 400
        self.pointDistance = 5 #每点之间的间隔
        self.updateInterval = 500 #更新的时间间隔
        self.timer.setInterval(self.updateInterval)
        self.timer.start()
        self.machineLoad = MachineLoad.getInstance()
        self.boxWidth = 60

    def finalize(self):
        self.timer.stop()
        self.loads = []

    def collectMachineLoad(self):
        rate = self.machineLoad.getLoad()
        self.loads.insert(0, rate)
        if len(self.loads) > self.maxLength:
            self.loads.pop( - 1)
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        width, height = self.width(), self.height()
        polygon = QPolygon()
        for i, rate in enumerate(self.loads):
            x = width - i * self.pointDistance
            y = height - rate * height
            if x < self.boxWidth:
                break
            polygon.append(QPoint(x, y))
        painter = QPainter(self)
        pen = QPen()
        pen.setColor(Qt.darkGreen)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing, True)
        #画网格
        painter.setOpacity(0.5)
        gridSize = self.pointDistance * 4
        deltaX = (width - self.boxWidth) % gridSize + self.boxWidth
        deltaY = height % gridSize
        for i in range(int(width / gridSize)):
            x = deltaX + gridSize * i
            painter.drawLine(x, 0, x, height)
        for j in range(int(height / gridSize)):
            y = j * gridSize + deltaY
            painter.drawLine(self.boxWidth, y, width, y)
        #画折线
        pen.setColor(Qt.darkCyan)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setOpacity(1)
        painter.drawPolyline(polygon)
        #画展示框
        if len(self.loads) > 0:
            rate = self.loads[0]
        else:
            rate = 1.0
        rect1 = QRect(4, height * 0.05, self.boxWidth - 9, height * 0.7)
        rect2 = QRect(4, height * 0.8, self.boxWidth - 9, height * 0.2)
        centerX = int(rect1.width() / 2) + 1
        pen.setWidth(1)
        for i in range(rect1.height()):
            if i % 4 == 0:
                continue
            if (rect1.height() - i) / rect1.height() > rate:
                pen.setColor(Qt.darkGreen)
            else:
                pen.setColor(Qt.green)
            painter.setPen(pen)
            for j in range(rect1.width()):
                if centerX - 1 <= j <= centerX + 1:
                    continue
                painter.drawPoint(rect1.x() + j, rect1.y() + i)
        pen.setColor(Qt.black)
        painter.setPen(pen)
        painter.drawText(rect2, Qt.AlignHCenter | Qt.AlignVCenter, str(int(rate * 100)) + "%")
#
#        points=int(self.width()/self.pointDistance)
#        if points>len(self.loads):
#            beginIndex=0
#            beginPoint=points-len(self.loads)
#        else:
#            beginIndex=len(self.loads)-points
#            beginPoint=0
#        j=0
#        height=self.height()
#        polygonGreen=QPolygon()
#        for i in range(beginIndex, len(self.loads)):
#            rate=self.loads[i]
#            x=(beginPoint+j)*self.pointDistance
#            y=height-rate*height
#            polygonGreen.append(QPoint(x, y))
#            j+=1
#        painter=QPainter(self)
#        pen=QPen()
#        pen.setColor(Qt.green)
#        pen.setWidth(2)
#        painter.setPen(pen)
#        painter.setRenderHint(QPainter.Antialiasing, True)
#        painter.drawPolyline(polygonGreen)


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
                with io.open("/proc/stat", encoding = "ascii") as statfile:
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
            except:
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
