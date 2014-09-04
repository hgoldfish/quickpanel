# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import copy, functools
from PyQt4.QtCore import QAbstractListModel, QModelIndex, QPoint, QRect, Qt, pyqtSignal
from PyQt4.QtGui import QBrush, QColor, QDialog, QFrame, QIcon, QMenu, QPainter, \
        QPen, QSizePolicy, QWidget
from .Ui_selectwidgets import Ui_SelectWidgetsDialog

__all__ = ["LayoutEditor"]

class LayoutEditor(QFrame):
    """显示一个类似于KDE桌面的编辑界面，可以让用户添加、删除、移动部件。还可以改变部件的大小。"""

    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, event):
        QFrame.paintEvent(self, event)
        factorForWidth = self.width() / 40
        factorForHeight = self.height() / 30
        row = 1
        column = 1

        painter = QPainter(self)
        painter.setOpacity(0.9)
        pen = QPen()
        pen.setColor(Qt.white)
        painter.setPen(pen)
        while factorForWidth * column < self.width():
            painter.drawLine(factorForWidth * column, 0, factorForWidth * column, self.height())
            column += 1
        while factorForHeight * row < self.height():
            painter.drawLine(0, factorForHeight * row, self.width(), factorForHeight * row)
            row += 1

    def beginEdit(self, widgets):
        self.widgets = []
        for widget in widgets:
            w = {}
            w["id"] = widget.id
            w["name"] = widget.name
            w["description"] = widget.description
            w["enabled"] = widget.enabled
            w["widget"] = None
            w["rect"] = widget.rect
            self.widgets.append(w)
        self.originalWidgets = copy.deepcopy(self.widgets)
        self.posistWidgets()

    def saveLayout(self, widgets):
        changedWidgets = []
        for widget in widgets:
            for w in self.widgets:
                if w["id"] == widget.id:
                    break
            else:
                continue
            changed = False
            if w["enabled"] != widget.enabled:
                widget.enabled = w["enabled"]
                changed = True
            if w["rect"] != widget.rect:
                widget.rect = w["rect"]
                changed = True
            if changed:
                changedWidgets.append(widget)
        return changedWidgets

    def endEdit(self):
        for widget in self.widgets:
            if widget["widget"] is not None:
                widget["widget"].close()
                widget["widget"].setParent(None)
                widget["widget"] = None

    def posistWidgets(self):
        factorForWidth = self.width() / 40
        factorForHeight = self.height() / 30
        for widget in self.widgets:
            if widget["enabled"]:
                if widget["widget"] is None:
                    widget["widget"] = Widget(self)
                    widget["widget"].geometryChanged.connect(self.onWidgetGeometryChanged)
                    widget["widget"].deleteMe.connect(self.deleteWidget)
                    widget["widget"].show()
                widget["widget"].setName(widget["name"])
                widget["widget"].setDescription(widget["description"])
                vrect = widget["rect"]
                trect = QRect(vrect.left() * factorForWidth + 3, vrect.top() * factorForHeight + 3,
                        vrect.width() * factorForWidth - 6, vrect.height() * factorForHeight - 6)
                widget["widget"].setGeometry(trect)
            else:
                if widget["widget"] is not None:
                    widget["widget"].setParent(None)
                    widget["widget"] = None

    def resetLayout(self):
        self.endEdit()
        self.widgets = copy.deepcopy(self.originalWidgets)
        self.posistWidgets()

    def selectWidgets(self):
        d = SelectWidgetsDialog(self)
        callback = functools.partial(d.selectWidgets, self.widgets)
        if self.parent()._runDialog(d, self, callback) == QDialog.Accepted:
            result = d.getResult()
            for widget in self.widgets:
                for row in result:
                    if widget["id"] == row["id"]:
                        widget["enabled"] = row["enabled"]
                        break
            self.posistWidgets()
        d.deleteLater()

    def onWidgetGeometryChanged(self, newRect):
        w = self.sender()
        for widget in self.widgets:
            if widget["widget"] is w:
                widget["rect"] = newRect
                return

    def deleteWidget(self):
        w = self.sender()
        for widget in self.widgets:
            if widget["widget"] is w:
                self.parent().disableWidget(widget["id"])
                widget["widget"].setParent(None)
                widget["widget"] = None
                widget["enabled"] = False
                return


class Widget(QWidget):
    geometryChanged = pyqtSignal("QRect")
    deleteMe = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.name = self.description = ""
        self.setMouseTracking(True)
        self.moving = False
        self.edge = 8

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        pen = QPen()
        pen.setWidth(2)
        pen.setColor(QColor(200, 200, 200))
        rect = self.rect()
        rect = rect.adjusted(0, 0, -1, -1)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(pen)
        painter.setOpacity(0.5)
        painter.setBrush(QBrush(QColor(Qt.white)))
        painter.drawRoundedRect(rect, 15, 15)
        painter.setOpacity(1)
        pen.setColor(Qt.black)
        painter.setPen(pen)
        text = self.name + "\n" + self.description
        painter.drawText(self.rect(), Qt.AlignHCenter | Qt.AlignVCenter, text)

    def mouseMoveEvent(self, event):
        width = self.width()
        height = self.height()
        if self.moving:
            oldRect = self.geometry()
            oldRect.adjust( - 3, -3, 3, 3)
            p = event.pos()
            p = self.mapToParent(p)
            if self.orientation == "leftTop":
                p = self.tryMove(oldRect.topLeft(), p, 3)
                oldRect.setTopLeft(p)
            elif self.orientation == "leftBottom":
                p = self.tryMove(oldRect.bottomLeft(), p, 3)
                oldRect.setBottomLeft(p)
            elif self.orientation == "left":
                p = self.tryMove(oldRect.topLeft(), p, 1)
                oldRect.setLeft(p.x())
            elif self.orientation == "rightTop":
                p = self.tryMove(oldRect.topRight(), p, 3)
                oldRect.setTopRight(p)
            elif self.orientation == "rightBottom":
                p = self.tryMove(oldRect.bottomRight(), p, 3)
                oldRect.setBottomRight(p)
            elif self.orientation == "right":
                p = self.tryMove(oldRect.topRight(), p, 1)
                oldRect.setRight(p.x())
            elif self.orientation == "top":
                p = self.tryMove(oldRect.topRight(), p, 2)
                oldRect.setTop(p.y())
            elif self.orientation == "bottom":
                p = self.tryMove(oldRect.bottomRight(), p, 2)
                oldRect.setBottom(p.y())
            else:
                p = event.globalPos() - self.originalPos + self.originalTopLeft
                p = self.tryMove(self.originalTopLeft, p, 3)
                if oldRect.topLeft() != p:
                    oldRect.moveTopLeft(p)
                    #self.originalPos=event.globalPos()
            self.geometryChanged.emit(self.calculateLogicalRect(oldRect))
            oldRect.adjust(3, 3, -3, -3)
            self.setGeometry(oldRect)
        else:
            if 0 < event.x() < self.edge:
                if 0 < event.y() < self.edge:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif height - self.edge < event.y() < height:
                    self.setCursor(Qt.SizeBDiagCursor)
                else:
                    self.setCursor(Qt.SizeHorCursor)
            elif width - self.edge < event.x() < width:
                if 0 < event.y() < self.edge:
                    self.setCursor(Qt.SizeBDiagCursor)
                elif height - self.edge < event.y() < height:
                    self.setCursor(Qt.SizeFDiagCursor)
                else:
                    self.setCursor(Qt.SizeHorCursor)
            elif 0 < event.y() < self.edge or height - self.edge < event.y() < height:
                self.setCursor(Qt.SizeVerCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        self.raise_()
        if event.button() == Qt.LeftButton:
            self.moving = True
            width = self.width()
            height = self.height()
            if 0 < event.x() < self.edge:
                if 0 < event.y() < self.edge:
                    self.orientation = "leftTop"
                elif height - self.edge < event.y() < height:
                    self.orientation = "leftBottom"
                else:
                    self.orientation = "left"
            elif width - self.edge < event.x() < width:
                if 0 < event.y() < self.edge:
                    self.orientation = "rightTop"
                elif height - self.edge < event.y() < height:
                    self.orientation = "rightBottom"
                else:
                    self.orientation = "right"
            elif 0 < event.y() < self.edge:
                self.orientation = "top"
            elif height - self.edge < event.y() < height:
                self.orientation = "bottom"
            else:
                self.orientation = "center"
                self.originalPos = event.globalPos()
                self.originalTopLeft = self.geometry().topLeft()
                self.originalTopLeft += QPoint( - 3, -3)
        elif event.button() == Qt.RightButton:
            menu = QMenu()
            actionDelete = menu.addAction(QIcon(":/images/remove.png"), self.trUtf8("删除(&R)"))
            try:
                result = getattr(menu, "exec_")(event.globalPos())
            except AttributeError:
                result = getattr(menu, "exec")(event.globalPos())
            if result is actionDelete:
                self.deleteMe.emit()

    def mouseReleaseEvent(self, event):
        self.moving = False
        try:
            del self.originalPos
            del self.originalTopLeft
        except AttributeError:
            pass

    def setName(self, name):
        self.name = name

    def setDescription(self, description):
        self.description = description

    def tryMove(self, oldPos, newPos, directions):
        p = QPoint(oldPos)
        if directions & 1: #X轴方向
            gridX = self.parent().width() / 40
            delta = newPos.x() - oldPos.x()
            if abs(delta) / gridX > 0.5:
                newX = oldPos.x() + delta / abs(delta) * gridX * round(abs(delta) / gridX)
                newX = gridX * round(newX / gridX)
                p.setX(newX)
        if directions & 2:
            gridY = self.parent().height() / 30
            delta = newPos.y() - oldPos.y()
            if abs(delta) / gridY > 0.5:
                newY = oldPos.y() + delta / abs(delta) * gridY * round(abs(delta) / gridY)
                newY = gridY * round(newY / gridY)
                p.setY(newY)
        return p

    def calculateLogicalRect(self, physicalRect):
        gridX = self.parent().width() / 40
        gridY = self.parent().height() / 30
        logicalRect = QRect()
        logicalRect.setTop(round(physicalRect.top() / gridY))
        logicalRect.setLeft(round(physicalRect.left() / gridX))
        logicalRect.setWidth(round(physicalRect.width() / gridX))
        logicalRect.setHeight(round(physicalRect.height() / gridY))
        return logicalRect

class SelectWidgetsDialog(QDialog, Ui_SelectWidgetsDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.widgetsModel = WidgetsModel()
        self.lstWidgets.setModel(self.widgetsModel)
        self.lstWidgets.selectionModel().currentChanged.connect(self.onCurrentWidgetChanged)

    def selectWidgets(self, widgets):
        self.widgetsModel.setWidgets(widgets)
        self.lstWidgets.setCurrentIndex(self.widgetsModel.firstIndex())
        try:
            return getattr(self, "exec_")()
        except AttributeError:
            return getattr(self, "exec")()

    def getResult(self):
        return self.widgetsModel.getResult()

    def onCurrentWidgetChanged(self, current, previous):
        description = self.widgetsModel.descriptionFor(current)
        self.lblDescription.setText(description)


class WidgetsModel(QAbstractListModel):
    def __init__(self):
        QAbstractListModel.__init__(self)
        self.widgets = []

    def setWidgets(self, widgets):
        self.widgets = []
        for widget in widgets:
            w = {}
            w["id"] = widget["id"]
            w["name"] = widget["name"]
            w["description"] = widget["description"]
            w["enabled"] = widget["enabled"]
            self.widgets.append(w)
        self.reset()

    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.widgets)

    def data(self, index, role):
        if index.isValid():
            widget = self.widgets[index.row()]
            if role == Qt.DisplayRole:
                return widget["name"]
            elif role == Qt.CheckStateRole:
                return Qt.Checked if widget["enabled"] else Qt.Unchecked
        return None

    def setData(self, index, value, role):
        if index.isValid() and role == Qt.CheckStateRole:
            widget = self.widgets[index.row()]
            state = value
            widget["enabled"] = (state == Qt.Checked)
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index):
        if index.isValid():
            return QAbstractListModel.flags(self, index) | Qt.ItemIsUserCheckable
        return QAbstractListModel.flags(self, index)

    def getResult(self):
        return self.widgets

    def descriptionFor(self, index):
        if index.isValid():
            widget = self.widgets[index.row()]
            return widget["description"]
        return ""

    def firstIndex(self):
        if len(self.widgets) == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

