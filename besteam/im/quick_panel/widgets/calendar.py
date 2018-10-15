from PyQt5.QtCore import QDateTime, Qt, QRectF, QPointF, QSizeF, QTimer
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QFrame, QStylePainter

class CalendarWidget(QFrame):
    def __init__(self, parent = None):
        QFrame.__init__(self, parent)
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.updateCurrentDateTime)
        self.timer.start()

    def paintEvent(self, event):
        QFrame.paintEvent(self, event)
        text = QDateTime.currentDateTime().toString(Qt.SystemLocaleLongDate)
        logicalRect = QRectF(QPointF(0, 0), QSizeF(QFontMetrics(self.font()).size(Qt.TextSingleLine, text)))
        physicalRect, frameWidth = QRectF(self.rect()), self.frameWidth()
        physicalRect.adjust(frameWidth, frameWidth, -frameWidth, -frameWidth)
        scaleForWidth = physicalRect.width() / logicalRect.width()
        scaleForHeight = physicalRect.height() / logicalRect.height()
        logicalRect.moveTo(frameWidth / scaleForWidth , frameWidth / scaleForHeight)

        painter = QStylePainter(self)
        painter.scale(scaleForWidth, scaleForHeight)
        painter.drawText(logicalRect, Qt.AlignCenter, text)

    def updateCurrentDateTime(self):
        if self.isVisible():
            self.update()
