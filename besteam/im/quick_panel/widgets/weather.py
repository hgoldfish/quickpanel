# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import logging
from PyQt4.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal
from PyQt4.QtGui import QPainter, QPixmap, QWidget
from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager

__all__ = ["WeatherWidget"]

logger = logging.getLogger(__name__)

class WeatherWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        http = QNetworkAccessManager()
        self.weatherText = self.trUtf8("正在查询天气情况...")
        self.pixmap = QPixmap()
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
#        self.actionConfigure=QAction(QIcon(":/images/configure.png"), self.trUtf8("配置(&C)..."), None)
#        self.actionConfigure.triggered.connect(self.configure)
#        self.addAction(self.actionConfigure)
        self.provider = LiqweiProvider(http)
        self.provider.gotResult.connect(self.setResult)

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        painter = QPainter(self)
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, self.weatherText)
        if not self.pixmap.isNull():
            r = self.pixmap.rect()
            r.moveTop(5)
            r.moveRight(self.width() - 5)
            painter.drawPixmap(r, self.pixmap)

    def setResult(self, text, pixmapPath):
        self.weatherText = text
        self.pixmap = QPixmap(pixmapPath)
        self.update()

#    def configure(self):
#        d = ConfigureDialog(self)
#        if self.window().runDialog(d.exec_) == QDialog.Accepted:
#            pass
#        d.setParent(None)


#class WeatherConfigureDialog(QDialog, Ui_WeatherConfigureDialog):
#    def __init__(self, parent):
#        QDialog.__init__(self, parent)
#        self.setupUi(self)
#        self.makeConnections()
#
#    def makeConnections(self):
#        pass


class LiqweiProvider(QObject):
    gotResult = pyqtSignal(str, str)

    def __init__(self, http):
        QObject.__init__(self)
        self.http = http
        self.timer = QTimer()
        self.timer.timeout.connect(self.checkWeather)
        self.timer.start(30 * 60 * 1000)
        #self.timer.start(1000)
        self.reply = None
        self.checkWeather()

    def checkWeather(self):
        if self.reply is not None:
            return
        request = QNetworkRequest()
        request.setUrl(QUrl("http://api.liqwei.com/weather/"))
        self.reply = self.http.get(request)
        self.reply.finished.connect(self.onReplyFinished)
        self.reply.error.connect(self.onReplyError)

    def deleteReply(self):
        self.reply = None

    def onReplyError(self):
        weatherText = self.trUtf8("不能获取天气信息")
        self.gotResult.emit(weatherText, ":/images/weather/weather-none-available.png")
        QTimer.singleShot(0, self.deleteReply)

    def onReplyFinished(self):
        data = self.reply.readAll()
        weatherText = bytes(data).decode("gb2312")
        weatherText = weatherText.replace("<br/>", "\n")
        try:
            pixmapPath = self.guessWeather(weatherText)
        except:
            pixmapPath = ""
        self.gotResult.emit(weatherText, pixmapPath)
        QTimer.singleShot(0, self.deleteReply)

    def guessWeather(self, weatherText):
        line1 = weatherText.split()[0]
        t = line1.split(",")[2]
        logger.debug("今天天气: %s", t)
        if t in ("多云", "阴"):
            return ":/images/weather/weather-clouds.png"
        elif t in ("小到中雨", "中到大雨", "大到暴雨", "中雨", "阵雨", "小雨", "大雨"):
            return ":/images/weather/weather-showers.png"
        elif t == "晴":
            return ":/images/weather/weather-clear.png"
        elif t == "冰雹":
            return ":/images/weather/weather-freezing-rain.png"
        elif t == "雪":
            return ":/images/weather/weather-snow.png"
        elif t == "雨夹雪":
            return ":/images/weather/weather-snow-rain.png"
        elif t == "暴雨":
            return ":/images/weather/weather-storm.png"
        else:
            return ":/images/weather/weather-none-available.png"

