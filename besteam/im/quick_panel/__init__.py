import os
import functools
import logging
import ctypes
from PyQt5.QtCore import QAbstractListModel, QModelIndex, QRect, QTimer, Qt, QStandardPaths
from PyQt5.QtGui import  QBrush, QColor, QImage, QPainter, QPen, QIcon, QDesktopServices
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox,  \
        QSizePolicy, QToolBar, QWidget, QAction, QHBoxLayout, \
        QVBoxLayout, QLabel, QFileDialog

from .layout_editor import LayoutEditor
from .canvas import Canvas
from .services import WidgetConfigure, QuickPanelDatabase

__all__ = ["QuickPanel"]

logger = logging.getLogger(__name__)

def moveToCenter(window):
    r = window.geometry()
    r.moveCenter(QApplication.instance().desktop().screenGeometry().center())
    window.setGeometry(r)

class WidgetManager:
    """QuickPanel类的一部分，分出来方便阅读与理解。主要功能是管理快捷面板的部件"""

    def initWidgets(self):
        self.widgets = []

        from besteam.im.quick_panel.widgets.todo_list import TodoListWidget
        from besteam.im.quick_panel.widgets.quick_access import QuickAccessWidget
        from besteam.im.quick_panel.widgets.textpad import TextpadWidget
        from besteam.im.quick_panel.widgets.desktop_icon import DesktopIconWidget
        from besteam.im.quick_panel.widgets.machine_load import MachineLoadWidget
        from besteam.im.quick_panel.widgets.calendar import CalendarWidget
        self.registerWidget("bc8ada4f-50b8-49f7-917a-da163b6763e9", self.tr("待办事项列表"), \
                self.tr("用于纪录当前正在进行中的待办事项。"), \
                TodoListWidget)
        self.registerWidget("be6c197b-0181-47c0-a9fc-6a1fe5f1b3e6", self.tr("Besteam快捷方式"), \
                self.tr("快捷启动Besteam的附加工具。"), \
                QuickAccessWidget)
        self.registerWidget("45d1ee54-f9bd-435e-93cf-b46a05b56514", self.tr("文本框"), \
                self.tr("简单纪录文本。退出Besteam被丢弃。"), \
                TextpadWidget)
        self.registerWidget("dd6afcb0-e223-4156-988d-20f20266c6f0", self.tr("桌面快捷方式"), \
                self.tr("启动外部程序。"), \
                DesktopIconWidget)
        self.registerWidget("b0b6b9eb-aec0-4fe5-bfd0-d4d317fdd547", self.tr("CPU使用率"), \
                self.tr("以折线的形式显示一段时间内的CPU使用率。"), \
                MachineLoadWidget)
        self.registerWidget("d94db588-663b-4a6f-b935-4ca9ff283c75", self.tr("现在时间"),\
                self.tr("显示当前时间。"), \
                CalendarWidget)
        logger.debug("All builtin widgets have been registered.")

    def finalize(self):
        self.unregisterWidget("bc8ada4f-50b8-49f7-917a-da163b6763e9")
        self.unregisterWidget("be6c197b-0181-47c0-a9fc-6a1fe5f1b3e6")
        self.unregisterWidget("45d1ee54-f9bd-435e-93cf-b46a05b56514")
        self.unregisterWidget("dd6afcb0-e223-4156-988d-20f20266c6f0")
        self.unregisterWidget("35e3397b-500e-4bcc-97d9-4f84997e1e46")
        self.unregisterWidget("b0b6b9eb-aec0-4fe5-bfd0-d4d317fdd547")
        self.unregisterWidget("d94db588-663b-4a6f-b935-4ca9ff283c75")
        for widget in list(self.widgets):
            self.unregisterWidget(widget.id)
        logger.debug("All builtin widgets have been unregistered.")

    def getAllWidgets(self):
        return self.widgets

    def registerWidget(self, id, name, description, factory):
        widget = WidgetConfigure()
        config = self.db.getWidgetConfig(id)
        if config is None:
            config = {}
            config["id"] = id
            config["left"] = 15
            config["top"] = 10
            config["width"] = 10
            config["height"] = 10
            config["enabled"] = False
            self.db.saveWidgetConfig(config)
            widget.rect = QRect(15, 10, 10, 10)
            widget.enabled = False
        else:
            widget.rect = QRect(config["left"], config["top"], config["width"], config["height"])
            widget.enabled = config["enabled"]
        widget.id = id
        widget.name = name
        widget.description = description
        widget.factory = factory
        widget.widget = None
        self.widgets.append(widget)
        if widget.enabled:
            self._enableWidget(widget, False)

    def unregisterWidget(self, widgetId):
        i = 0
        for widget in self.widgets:
            if widget.id == widgetId:
                if widget.widget is not None:
                    assert widget.enabled
                    self._disableWidget(widget, False)
                self.widgets.pop(i)
                break
            i += 1

    def enableWidget(self, widgetId):
        "根据部件的ID启用部件。也是将它显示在快捷面板上面。"
        for widget in self.widgets:
            if widget.id == widgetId:
                self._enableWidget(widget, True)
                break

    def disableWidget(self, widgetId):
        "根据部件的ID禁用部件。让它从快捷面板中删除。"
        for widget in self.widgets:
            if widget.id == widgetId:
                self._disableWidget(widget, True)
                break

    def _enableWidget(self, widget, syncToDatabase = True):
        if widget.widget is not None:
            return
        try:
            widget.widget = widget.factory(self.canvas)
        except:
            logger.exception("error occured while call widget's factory function.")
            return
        widget.enabled = True
        self.canvas.showWidget(widget)
        if syncToDatabase:
            self.db.setWidgetEnabled(widget.id, True)

    def _disableWidget(self, widget, syncToDatabase = True):
        if widget.widget is None:
            return
        if hasattr(widget.widget, "finalize"):
            try:
                widget.widget.finalize()
            except:
                logger.exception("error occured while closing widget.")
        self.canvas.closeWidget(widget)
        widget.widget.hide()
        widget.widget.setParent(None)
        widget.widget = None
        widget.enabled = False
        if syncToDatabase:
            self.db.setWidgetEnabled(widget.id, False)

    def selectWidgets(self):
        self.layoutEditor.selectWidgets()

    def resetDefaultLayout(self):
        self.layoutEditor.resetLayout()


class QuickPanel(QWidget, WidgetManager):
    """
    一个快捷面板。类似于KDE的桌面。只不过功能会简单些。主要的方法有：
    addQuickAccessShortcut() 供插件添加一个系统快捷方式。
    removeQuickAccessShortcut() 删除插件添加的系统快捷方式。
    toggle() 如果快捷面板已经显示就隐藏它。如果处于隐藏状态则显示它。
    showAndGetFocus() 显示快捷面板并且将焦点放置于常用的位置。
    registerWidget() 注册部件
    unregisterWidget() 反注册部件
    """

    def __init__(self, platform):
        QWidget.__init__(self, None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.platform = platform
        self.db = QuickPanelDatabase(platform.databaseFile)
        self.createActions()
        self.createControls()
        self.loadSettings()
        self.makeConnections()
        #Besteam系统快捷方式作为QuickPanel提供的一个服务，必须定义在这里
        #虽然部件可能没有运行。QuickPanel也应该记住其它插件添加的快捷方式，以便在
        #用户添加QuickAccessWidget之后，可以显示所有的系统快捷方式
        self.quickAccessModel = QuickAccessModel()

    def createActions(self):
        self.actionChangeBackground = QAction(self)
        self.actionChangeBackground.setIcon(QIcon(":/images/change_background.png"))
        self.actionChangeBackground.setText(self.tr("Change &Background"))
        self.actionChangeBackground.setIconText(self.tr("Background"))
        self.actionChangeBackground.setToolTip(self.tr("Change Background"))
        self.actionClose = QAction(self)
        self.actionClose.setIcon(QIcon(":/images/close.png"))
        self.actionClose.setText(self.tr("&Close"))
        self.actionClose.setIconText(self.tr("Close"))
        self.actionClose.setToolTip(self.tr("Close"))
        self.actionChangeLayout = QAction(self)
        self.actionChangeLayout.setIcon(QIcon(":/images/change_layout.png"))
        self.actionChangeLayout.setText(self.tr("Change &Layout"))
        self.actionChangeLayout.setIconText(self.tr("Layout"))
        self.actionChangeLayout.setToolTip(self.tr("Change Layout"))
        self.actionChangeLayout.setCheckable(True)
        self.actionSelectWidgets = QAction(self)
        self.actionSelectWidgets.setIcon(QIcon(":/images/select_widgets.png"))
        self.actionSelectWidgets.setText(self.tr("&Select Widgets"))
        self.actionSelectWidgets.setIconText(self.tr("Widgets"))
        self.actionSelectWidgets.setToolTip(self.tr("Select Widgets"))
        self.actionResetBackground = QAction(self)
        self.actionResetBackground.setIcon(QIcon(":/images/reset.png"))
        self.actionResetBackground.setText(self.tr("&Reset Background"))
        self.actionResetBackground.setIconText(self.tr("Reset"))
        self.actionResetBackground.setToolTip(self.tr("Reset Background"))
        self.actionResetDefaultLayout = QAction(self)
        self.actionResetDefaultLayout.setIcon(QIcon(":/images/reset.png"))
        self.actionResetDefaultLayout.setText(self.tr("Reset &Layout"))
        self.actionResetDefaultLayout.setIconText(self.tr("Reset"))
        self.actionResetDefaultLayout.setToolTip(self.tr("Reset Layout"))

    def createControls(self):
        self.toolBarMain = QToolBar(self)
        self.toolBarMain.addAction(self.actionChangeBackground)
        self.toolBarMain.addAction(self.actionResetBackground)
        self.toolBarMain.addAction(self.actionChangeLayout)
        self.toolBarMain.addAction(self.actionClose)
        self.toolBarMain.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.toolBarMain.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolBarLayout = QToolBar(self)
        self.toolBarLayout.addAction(self.actionSelectWidgets)
        self.toolBarLayout.addAction(self.actionResetDefaultLayout)
        self.toolBarLayout.addAction(self.actionChangeLayout)
        self.toolBarLayout.addAction(self.actionClose)
        self.toolBarLayout.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.toolBarLayout.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.canvas = Canvas(self)
        self.layoutEditor = LayoutEditor(self)

        self.lblTitle = QLabel(self)
        self.lblTitle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setLayout(QVBoxLayout())
        self.layoutTop = QHBoxLayout()
        self.layoutTop.addWidget(self.lblTitle)
        self.layoutTop.addWidget(self.toolBarMain)
        self.layoutTop.addWidget(self.toolBarLayout)
        self.toolBarLayout.hide()
        self.layout().addLayout(self.layoutTop)
        self.layout().addWidget(self.canvas)
        self.layout().addWidget(self.layoutEditor)
        self.layoutEditor.hide()

    def loadSettings(self):
        settings = self.platform.getSettings()
        filepath = settings.value("background", "background.png")
        if not os.path.exists(filepath):
            filepath = os.path.join(os.path.dirname(__file__), filepath)
        if not os.path.exists(filepath):
            return
        image = QImage(filepath)
        self._makeBackground(image)

    def makeConnections(self):
        self.actionClose.triggered.connect(self.close)
        self.actionChangeLayout.triggered.connect(self.toggleLayoutEditor)
        self.actionChangeBackground.triggered.connect(self.changeBackground)
        self.actionResetBackground.triggered.connect(self.useDefaultBackground)
        self.actionSelectWidgets.triggered.connect(self.selectWidgets)
        self.actionResetDefaultLayout.triggered.connect(self.resetDefaultLayout)
        QApplication.instance().focusChanged.connect(self.onWindowFocusChanged)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(event.rect(), self._background_image, event.rect())

    def keyPressEvent(self, event):
        QWidget.keyPressEvent(self, event)
        if not event.isAccepted() and event.key() == Qt.Key_Escape:
            if self.layoutEditor.isVisible():
                self.leaveLayoutEditor()
                self.actionChangeLayout.setChecked(False)
            else:
                self.close()

    def onWindowFocusChanged(self, old, new):
        "实现类似于Qt.Popup那样点击其它窗口就立即关闭本窗口的效果。"
        if self.isVisible() and not self.isActiveWindow():
            self.close()

    def showEvent(self, event):
        settings = self.platform.getSettings()
        key = settings.value("globalkey", "Alt+`")
        if key is not None:
            if os.name == "nt": #在Windows系统下，Meta键习惯叫Win键
                key = key.replace("Meta", "Win")
            title = self.tr("提示：在任何位置按<b>{0}</b>打开快捷面板。").format(key)
            self.lblTitle.setText('<span style=" font-size:14pt;font-style:italic;">{0}</span>'.format(title))
        else:
            title = self.tr("快捷面板")
            self.lblTitle.setText('<span style=" font-size:14pt;font-style:italic;">{0}</span>'.format(title))

        #如果有时候运行全屏程序，快捷面板的位置就会发生改变
        self._makeBackground(self._background_image)
        moveToCenter(self)
        self.canvas.positWidgets()
        QWidget.showEvent(self, event)

    def showAndGetFocus(self):
        if not self.isVisible():
            self.show()
        if self.windowState() & Qt.WindowMinimized:
            self.setWindowState(self.windowState() ^ Qt.WindowMinimized)
        self.raise_()
        if os.name == "nt":
            ctypes.windll.user32.BringWindowToTop(int(self.winId()))
            ctypes.windll.user32.SwitchToThisWindow(int(self.winId()), 1)
        self.activateWindow()

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.showAndGetFocus()

    def addQuickAccessShortcut(self, name, icon, callback):
        """
        添加一个快捷方式。有一个widget专门用于显示Besteam内部各种工具的快捷方式。
        name 快捷方式的名字
        icon 快捷方式的图标
        callback 当用户点击快捷方式的时候调用的回调函数。不会传入任何参数。
        """
        self.quickAccessModel.addShortcut(name, icon, callback)

    def removeQuickAccessShortcut(self, name):
        """删除一个系统快捷方式。参数name是快捷方式的名字。"""
        self.quickAccessModel.removeShortcut(name)

    def enterLayoutEditor(self):
        self.layoutEditor.show()
        self.canvas.hide()
        self.toolBarLayout.show()
        self.toolBarMain.hide()
        self.layoutEditor.beginEdit(self.widgets)

    def leaveLayoutEditor(self):
        self.layoutEditor.hide()
        self.canvas.show()
        self.toolBarLayout.hide()
        self.toolBarMain.show()
        changedWidgets = self.layoutEditor.saveLayout(self.widgets)
        for widget in changedWidgets:
            conf = {}
            conf["left"] = widget.rect.left()
            conf["top"] = widget.rect.top()
            conf["width"] = widget.rect.width()
            conf["height"] = widget.rect.height()
            conf["enabled"] = widget.enabled
            conf["id"] = widget.id
            self.db.saveWidgetConfig(conf)
            if widget.enabled:
                self._enableWidget(widget, False)
            else:
                self._disableWidget(widget, False)
        self.canvas.positWidgets(True)
        self.layoutEditor.endEdit()

    def toggleLayoutEditor(self, checked):
        if checked:
            self.enterLayoutEditor()
        else:
            self.leaveLayoutEditor()

    def changeBackground(self):
        filename, selectedFilter = QFileDialog.getOpenFileName(self, self.tr("Change Background"), \
            QStandardPaths.writableLocation(QStandardPaths.PicturesLocation), \
            self.tr("Image Files (*.png *.gif *.jpg *.jpeg *.bmp *.mng *ico)"))
        if not filename:
            return
        image = QImage(filename)
        if image.isNull():
            QMessageBox.information(self, self.tr("Change Background"), \
                    self.tr("不能读取图像文件，请检查文件格式是否正确，或者图片是否已经损坏。"))
            return
        if image.width() < 800 or image.height() < 600:
            answer = QMessageBox.information(self, self.tr("Change Background"), \
                    self.tr("不建议设置小于800x600的图片作为背景图案。如果继续，可能会使快捷面板显示错乱。是否继续？"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No)
            if answer == QMessageBox.No:
                return
        self._makeBackground(image)
        moveToCenter(self)
        self.canvas.positWidgets()
        self.update()
        with self.platform.getSettings() as settings:
            settings.setValue("background", filename)

    def useDefaultBackground(self):
        filename = "background.png"
        if not os.path.exists(filename):
            filename = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(filename):
            image = QImage(filename)
            if not image.isNull():
                self._makeBackground(image)
                moveToCenter(self)
                self.canvas.positWidgets()
                self.update()
        settings = self.platform.getSettings()
        settings.remove("background")

    def _makeBackground(self, image):
        desktopSize = QApplication.desktop().screenGeometry(self).size()
        if desktopSize.width() < image.width() or desktopSize.height() < image.height():
            self._background_image = image.scaled(desktopSize, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            self._background_image = image
        self.resize(self._background_image.size())

    def runDialog(self, *args, **kwargs):
        """
        在QuickPanel中显示一个对话框。主要是为了避免对话框显示的时候，快捷面板会隐藏。
        接受两种形式的参数，其中d是对话框:
            runDialog(d, d.exec_)
            runDialog(d.exec_, *args, **kwargs)
        建议使用第二种
        """
        if isinstance(args[0], QDialog):
            return self._runDialog2(args[0], args[1])
        else:
            callback, args = args[0], args[1:]
            return self._runDialog3(callback, args, kwargs)

    def _runDialog2(self, d, callback):
        return self._runDialog(d, self.canvas, callback)

    def _runDialog3(self, callback, args, kwargs):
        d = callback.__self__
        f = functools.partial(callback, *args, **kwargs)
        return self._runDialog(d, self.canvas, f)

    def _runDialog(self, d, container, callback):
        shutter = ShutterWidget(container)
        newPaintEvent = functools.partial(self._dialog_paintEvent, d)
        oldPaintEvent = d.paintEvent
        d.paintEvent = newPaintEvent
        r = d.geometry()
        r.moveCenter(container.rect().center())
        d.setGeometry(r)
        d.setWindowFlags(Qt.Widget)
        d.setParent(container)
        d.setFocus(Qt.OtherFocusReason)
        try:
            shutter.show()
            d.raise_()
            return callback()
        finally:
            d.paintEvent = oldPaintEvent
            shutter.close()
            shutter.setParent(None)

    def _dialog_paintEvent(self, d, event):
        QDialog.paintEvent(d, event)
        pen = QPen()
        pen.setWidth(2)
        pen.setColor(QColor(200, 200, 200))
        rect = d.rect()
        rect = rect.adjusted(0, 0, -1, -1)
        painter = QPainter(d)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(pen)
        painter.setOpacity(0.8)
        painter.setBrush(QBrush(QColor(Qt.white)))
        painter.drawRoundedRect(rect, 15, 15)


class QuickAccessModel(QAbstractListModel):
    def __init__(self):
        QAbstractListModel.__init__(self)
        self.shortcuts = []

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.shortcuts)
        return 0

    def data(self, index, role):
        if index.isValid() and role == Qt.DisplayRole  and index.column() == 0:
            return self.shortcuts[index.row()]["name"]
        elif index.isValid() and role == Qt.DecorationRole and index.column() == 0:
            return self.shortcuts[index.row()]["icon"]
        return None

    def addShortcut(self, name, icon, callback):
        self.beginInsertRows(QModelIndex(), len(self.shortcuts), len(self.shortcuts))
        self.shortcuts.append({"name":name, "icon":icon, "callback":callback})
        self.endInsertRows()

    def removeShortcut(self, name):
        for i, shortcut in enumerate(self.shortcuts):
            if shortcut["name"] != name:
                continue
            self.beginRemoveRows(QModelIndex(), i, i)
            self.shortcuts.pop(i)
            self.endRemoveRows()
            return

    def runShortcut(self, index):
        if not index.isValid():
            return
        self.shortcuts[index.row()]["callback"]()


class ShutterWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setGeometry(parent.rect())
        self.value = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.playNextFrame)
        self.timer.start(100)

    def playNextFrame(self):
        self.value += 0.05
        if self.value >= 0.2:
            self.timer.stop()
        self.update()

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        painter = QPainter(self)
        painter.setBrush(QBrush(QColor(Qt.black)))
        painter.setPen(QPen())
        painter.setOpacity(self.value)
        painter.drawRect(self.rect())
