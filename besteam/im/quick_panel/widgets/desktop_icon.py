import os
import logging
import uuid
from PyQt5.QtCore import QAbstractListModel, QFileInfo, QModelIndex, QProcess, QSize, QUrl, Qt, \
        QStandardPaths
from PyQt5.QtGui import QDesktopServices, QIcon, QImage, QPixmap, QCursor
from PyQt5.QtWidgets import QAbstractItemView, QListView, QMenu, QHBoxLayout, QFileDialog, \
        QMessageBox, QDialog, QFrame, QFileIconProvider, QAction
from besteam.utils.sql import Table, Database
from .Ui_shortcut import Ui_ShortcutDialog
from .Ui_bookmark import Ui_BookmarkDialog

__all__ = ["DesktopIconWidget"]

logger = logging.getLogger(__name__)

#定义几个特殊路径，分别是我的电脑，我的文档，我的音乐，我的图片
COMPUTER_PATH = "special://29307059-59dc-47e6-8c43-d77db6489d3a"
DOCUMENTS_PATH = "special://688910d6-de73-4426-b8a1-75dd03b91e3e"
MUSIC_PATH = "special://f1fd7171-fb82-47c4-9032-f7af3032e75e"
PICTURES_PATH = "special://a8350c8f-27db-4b82-add1-613351da2bd4"

class DesktopIconWidget(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setStyleSheet("QListView{background:transparent;}")

        self.listView = QListView(self)
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.listView)

        self.listView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.listView.setMovement(QListView.Snap)
        self.listView.setFlow(QListView.LeftToRight)
        self.listView.setResizeMode(QListView.Adjust)
        self.listView.setGridSize(QSize(self.logicalDpiX() / 96 * 70,
                                        self.logicalDpiY() / 96 * 70))
        self.listView.setViewMode(QListView.IconMode)

        self.quickDesktopModel = QuickDesktopModel(self.window().platform.databaseFile)
        self.listView.setModel(self.quickDesktopModel)
        self.createActions()
        self.makeConnections()

    def createActions(self):
        self.actionCreateComputer = QAction(self.tr("我的电脑(&C)"), self)
        self.actionCreateDocuments = QAction(self.tr("我的文档(&D)"), self)
        self.actionCreateMusic = QAction(self.tr("我的音乐(&M)"), self)
        self.actionCreatePictures = QAction(self.tr("我的图片(&P)"), self)
        self.actionCreateShortcut = QAction(self.tr("创建快捷方式(&C)"), self)
        self.actionCreateShortcut.setIcon(QIcon(":/images/new.png"))
        self.actionCreateBookmark = QAction(self.tr("创建网络链接(&B)"), self)
        self.actionCreateBookmark.setIcon(QIcon(":/images/insert-link.png"))
        self.actionRemoveShortcut = QAction(self.tr("删除快捷方式(&R)"), self)
        self.actionRemoveShortcut.setIcon(QIcon(":/images/delete.png"))
        self.actionRenameShortcut = QAction(self.tr("重命名(&N)"), self)
        self.actionRenameShortcut.setIcon(QIcon(":/images/edit-rename.png"))
        self.actionEditShortcut = QAction(self.tr("编辑快捷方式(&E)"), self)
        self.actionEditShortcut.setIcon(QIcon(":/images/edit.png"))

    def makeConnections(self):
        self.listView.customContextMenuRequested.connect(self.onQuickDesktopContextMenuRequest)
        self.listView.activated.connect(self.runQuickDesktopShortcut)

        self.actionCreateComputer.triggered.connect(self.createComputerShortcut)
        self.actionCreateDocuments.triggered.connect(self.createDocumentsShortcut)
        self.actionCreateMusic.triggered.connect(self.createMusicShortcut)
        self.actionCreatePictures.triggered.connect(self.createPicturesShortcut)
        self.actionCreateShortcut.triggered.connect(self.createShortcut)
        self.actionCreateBookmark.triggered.connect(self.createBookmark)
        self.actionEditShortcut.triggered.connect(self.editShortcut)
        self.actionRemoveShortcut.triggered.connect(self.removeShortcut)
        self.actionRenameShortcut.triggered.connect(self.renameShortcut)

    def onQuickDesktopContextMenuRequest(self, pos):
        index = self.listView.indexAt(pos)
        self.listView.setCurrentIndex(index)
        menu = QMenu()
        menu.addAction(self.actionCreateShortcut)
        menu.addAction(self.actionCreateBookmark)
        menu2 = menu.addMenu(self.tr("创建特殊快捷方式(&S)"))
        if os.name == "nt":
            menu2.addAction(self.actionCreateComputer)
        menu2.addAction(self.actionCreateDocuments)
        menu2.addAction(self.actionCreatePictures)
        menu2.addAction(self.actionCreateMusic)
        if index.isValid():
            menu.addAction(self.actionRemoveShortcut)
            if not self.quickDesktopModel.isSpecialShortcut(index):
                menu.addAction(self.actionEditShortcut)
            menu.addAction(self.actionRenameShortcut)
        try:
            getattr(menu, "exec")(QCursor.pos())
        except AttributeError:
            getattr(menu, "exec_")(QCursor.pos())

    def createShortcut(self):
        d = ShortcutDialog(self)
        if self.window().runDialog(d.create) == QDialog.Accepted:
            shortcut = d.getResult()
            shortcut["id"] = str(uuid.uuid4())
            self.quickDesktopModel.addShortcut(shortcut)
        d.deleteLater()

    def createBookmark(self):
        d = BookmarkDialog(self)
        if self.window().runDialog(d.create) == QDialog.Accepted:
            shortcut = {
                    "id": str(uuid.uuid4()),
                    "icon": "",
                    "openwith": "",
                    "dir": "",
            }
            shortcut.update(d.getResult())
            self.quickDesktopModel.addShortcut(shortcut)
        d.deleteLater()

    def createComputerShortcut(self):
        shortcut = {
                "id": str(uuid.uuid4()),
                "name": self.tr("我的电脑"),
                "path": COMPUTER_PATH,
                "icon": "",
                "dir": "",
                "openwith": "",
        }
        self.quickDesktopModel.addShortcut(shortcut)

    def createDocumentsShortcut(self):
        shortcut = {
                "id": str(uuid.uuid4()),
                "name": self.tr("我的文档"),
                "path": DOCUMENTS_PATH,
                "icon": "",
                "dir": "",
                "openwith": "",
        }
        self.quickDesktopModel.addShortcut(shortcut)

    def createPicturesShortcut(self):
        shortcut = {
                "id": str(uuid.uuid4()),
                "name": self.tr("图片收藏"),
                "path": PICTURES_PATH,
                "icon": "",
                "dir": "",
                "openwith": "",
        }
        self.quickDesktopModel.addShortcut(shortcut)

    def createMusicShortcut(self):
        shortcut = {
                "id": str(uuid.uuid4()),
                "name": self.tr("我的音乐"),
                "path": MUSIC_PATH,
                "icon": "",
                "dir": "",
                "openwith": "",
        }
        self.quickDesktopModel.addShortcut(shortcut)

    def renameShortcut(self):
        self.listView.edit(self.listView.currentIndex())

    def removeShortcut(self):
        self.quickDesktopModel.removeShortcut(self.listView.currentIndex())

    def editShortcut(self):
        index = self.listView.currentIndex()
        if not index.isValid():
            return
        shortcut = self.quickDesktopModel.shortcutAt(index)
        url = QUrl.fromUserInput(shortcut["path"])
        if not url.isValid():
            return
        if url.scheme() == "special":
            QMessageBox.information(self, self.tr("编辑快捷方式"), self.tr("不能编辑特殊图标。"))
            return
        elif url.scheme() == "file":
            d = ShortcutDialog(self)
        else:
            d = BookmarkDialog(self)
        if self.window().runDialog(d.edit, shortcut) == QDialog.Accepted:
            shortcut.update(d.getResult())
            self.quickDesktopModel.updateShortcut(shortcut, index)
        d.deleteLater()

    def runQuickDesktopShortcut(self):
        index = self.listView.currentIndex()
        if not index.isValid():
            return
        if not self.quickDesktopModel.runShortcut(index):
            QMessageBox.information(self, self.tr("快捷面板"), \
                    self.tr("不能运行快捷方式。请检查文件是否存在或者程序是否正确。"))
        else:
            self.window().close()

def getShortcutIcon(shortcut):
    if shortcut["icon"]:
        icon = QIcon(shortcut["icon"])
        if not icon.isNull():
            return icon
    iconProvider = QFileIconProvider()
    if shortcut["path"] == COMPUTER_PATH:
        return QIcon(":/images/user-home.png")
    elif shortcut["path"] == DOCUMENTS_PATH:
        documentsIcon = iconProvider.icon(QFileInfo(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)))
        if documentsIcon.isNull():
            return QIcon(":/images/folder-documents.png")
        else:
            return documentsIcon
    elif shortcut["path"] == MUSIC_PATH:
        musicIcon = iconProvider.icon(QFileInfo(QStandardPaths.writableLocation(QStandardPaths.MusicLocation)))
        if musicIcon.isNull():
            return QIcon(":/images/folder-sound.png")
        else:
            return musicIcon
    elif shortcut["path"] == PICTURES_PATH:
        picturesIcon = iconProvider.icon(QFileInfo(QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)))
        if picturesIcon.isNull():
            return QIcon(":/images/folder-image.png")
        else:
            return picturesIcon
    else:
        url = QUrl.fromUserInput(shortcut["path"])
        if url.scheme() == "file":
            if os.path.exists(shortcut["path"]):
                icon = iconProvider.icon(QFileInfo(url.toLocalFile()))
                if not icon.isNull():
                    return icon
            return QIcon(":/images/unknown.png")
        else:
            return QIcon(":/images/httpurl.png")
    return QIcon(":/images/unknown.png")

class QuickDesktopModel(QAbstractListModel):
    def __init__(self, databaseFile):
        QAbstractListModel.__init__(self)
        self.db = ShortcutDatabase(databaseFile)
        self.shortcuts = self.db.selectShortcut("")

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.shortcuts)
        return 0

    def data(self, index, role):
        if index.isValid() and index.column() == 0 and role in (Qt.DisplayRole, Qt.EditRole):
            return self.shortcuts[index.row()]["name"]
        elif index.isValid() and index.column() == 0 and role == Qt.DecorationRole:
            shortcut = self.shortcuts[index.row()]
            if "_icon" not in shortcut:
                shortcut["_icon"] = getShortcutIcon(shortcut)
            return shortcut["_icon"]
        return None

    def setData(self, index, value, role):
        if not index.isValid() or role != Qt.EditRole:
            return False
        shortcut = self.shortcuts[index.row()]
        shortcut["name"] = value
        shortcut.save()
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        if index.column() == 0:
            return QAbstractListModel.flags(self, index) | Qt.ItemIsEditable
        return QAbstractListModel.flags(self, index)

    def addShortcut(self, shortcut):
        self.beginInsertRows(QModelIndex(), len(self.shortcuts), len(self.shortcuts))
        shortcut = self.db.insertShortcut(shortcut)
        self.shortcuts.append(shortcut)
        self.endInsertRows()

    def removeShortcut(self, index):
        if not index.isValid():
            return
        self.beginRemoveRows(QModelIndex(), index.row(), index.row())
        shortcut = self.shortcuts.pop(index.row())
        shortcut.deleteFromDatabase()
        self.endRemoveRows()

    def isSpecialShortcut(self, index):
        if not index.isValid():
            return False
        return self.shortcuts[index.row()]["path"].startswith("special://")

    def runShortcut(self, index):
        if not index.isValid():
            return False
        shortcut = self.shortcuts[index.row()]
        if shortcut["path"].startswith("special://"):
            if shortcut["path"] == COMPUTER_PATH:
                if os.name == "nt":
                    explorer = os.path.join(os.environ["SystemRoot"], "explorer.exe")
                    return QProcess.startDetached(explorer, ["::{20D04FE0-3AEA-1069-A2D8-08002B30309D}"])
                else:
                    path = "/"
            elif shortcut["path"] == DOCUMENTS_PATH:
                path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            elif shortcut["path"] == MUSIC_PATH:
                path = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
            elif shortcut["path"] == PICTURES_PATH:
                path = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
            else:
                return False
            if os.name == "nt": #针对windows进行优化
                explorer = os.path.join(os.environ["SystemRoot"], "explorer.exe")
                return QProcess.startDetached(explorer, [path])
            else:
                return QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            currentDirectory = os.getcwd()
            try:
                if shortcut["dir"] is not None and shortcut["dir"] != "":
                    os.chdir(shortcut["dir"])
                if shortcut["openwith"] is not None and shortcut["openwith"] != "":
                    if not os.path.exists(shortcut["openwith"]):
                        return False
                    return QProcess.startDetached(shortcut["openwith"], [shortcut["path"]])
                else:
                    url = QUrl.fromUserInput(shortcut["path"])
                    if not url.isValid():
                        return False
                    if url.scheme() == "file" and not os.path.exists(url.toLocalFile()):
                        return False
                    return QDesktopServices.openUrl(url)
            except OSError: #raised by chdir()
                pass
            finally:
                os.chdir(currentDirectory)
        return False

    def shortcutAt(self, index):
        if index.isValid():
            return self.shortcuts[index.row()]
        return None

    def updateShortcut(self, shortcut, index):
        self.dataChanged.emit(index, index)
        oldone = self.shortcuts[index.row()]
        for field in shortcut:
            oldone[field] = shortcut[field]
        oldone.save()
        del self.shortcuts[index.row()]["_icon"]


class ShortcutDialog(QDialog, Ui_ShortcutDialog):
    "快捷方式编辑器。可以用于创建和编辑桌面快捷方式。"
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.makeConnections()

    def makeConnections(self):
        self.btnBrowsePath.clicked.connect(self.browsePath)
        self.btnBrowseOpenwith.clicked.connect(self.browseOpenwith)
        self.btnBrowseDir.clicked.connect(self.browseDir)
        self.btnChangeIcon.clicked.connect(self.changeFileIcon)
        self.btnRestoreDir.clicked.connect(self.restoreDir)
        self.btnRestoreIcon.clicked.connect(self.restoreIcon)
        self.txtPath.textEdited.connect(self.setFileIcon)

    def create(self):
        self.mode = "create"
        self.setWindowTitle(self.tr("创建快捷方式"))
        self.btnOkay.setText(self.tr("创建(&O)"))
        self.iconPath = ""
        self.shortcutIcon = QIcon(":/images/unknown.png")
        self.btnFace.setIcon(self.shortcutIcon)
        try:
            return getattr(self, "exec")()
        except AttributeError:
            return getattr(self, "exec_")()

    def showEvent(self, event):
        if self.mode == "create":
            self.browsePath()
        return QDialog.showEvent(self, event)

    def edit(self, shortcut):
        self.mode = "edit"
        self.setWindowTitle(self.tr("编辑快捷方式"))
        icon = getShortcutIcon(shortcut)
        self.btnFace.setIcon(icon)
        self.shortcutIcon = icon
        self.iconPath = shortcut["icon"]
        self.txtPath.setText(shortcut["path"])
        self.txtName.setText(shortcut["name"])
        self.txtOpenwith.setText(shortcut["openwith"])
        self.txtDir.setText(shortcut["dir"])
        try:
            return getattr(self, "exec_")()
        except AttributeError:
            return getattr(self, "exec")()

    def accept(self):
        if self.txtName.text().strip() == "":
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("请填写快捷方式的名称。"))
            self.txtName.setFocus(Qt.OtherFocusReason)
            return
        path = self.txtPath.text().strip()
        if path == "":
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("请填写目标文件/程序。"))
            self.txtPath.setFocus(Qt.OtherFocusReason)
            self.txtPath.selectAll()
            return
        if not os.path.exists(path):
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("目标文件/程序不存在。"))
            self.txtPath.setFocus(Qt.OtherFocusReason)
            self.txtPath.selectAll()
            return
        openwith = self.txtOpenwith.text().strip()
        if openwith != "":
            if not os.path.exists(openwith):
                QMessageBox.information(self, self.windowTitle(),
                        self.tr("编辑程序不存在。请重新选择。该选项是选填项，并不一定要填写。"))
                self.txtOpenwith.setFocus(Qt.OtherFocusReason)
                self.txtOpenwith.selectAll()
                return
            fi = QFileInfo(openwith)
            if not fi.isExecutable():
                QMessageBox.information(self, self.windowTitle(),
                        self.tr("编辑程序必须是一个可执行文件。请重新选择。该选项是选填项，并不一定要填写。"))
                self.txtOpenwith.setFocus(Qt.OtherFocusReason)
                self.txtOpenwith.selectAll()
                return
        dir = self.txtDir.text().strip()
        if dir == "":
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("请填写运行目录。可以使用“默认运行目录”按钮恢复默认的运行目录。"))
            self.txtDir.setFocus(Qt.OtherFocusReason)
            self.txtDir.selectAll()
            return
        if not os.path.exists(dir):
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("运行目录不存在。请重新选择。可以使用“默认运行目录”按钮恢复默认的运行目录。"))
            self.txtDir.setFocus(Qt.OtherFocusReason)
            self.txtDir.selectAll()
            return
        if not os.path.isdir(dir):
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("运行目录必须是一个目录，而非文件。请重新选择。可以使用“默认运行目录”按钮恢复默认的运行目录。"))
            self.txtDir.setFocus(Qt.OtherFocusReason)
            self.txtDir.selectAll()
            return
        QDialog.accept(self)

    def changeFileIcon(self):
        "用户点击了更换图标按钮。"
        filename, selectedFilter = QFileDialog.getOpenFileName(self, self.windowTitle())
        if not filename:
            return
        image = QImage(filename)
        if not image.isNull():
            self.shortcutIcon = QIcon(QPixmap.fromImage(image))
        else:
            ip = QFileIconProvider()
            shortcutIcon = ip.icon(QFileInfo(filename))
            if shortcutIcon.isNull():
                QMessageBox.information(self, self.tr("更换图标"),
                        self.tr("您选择的文件不包含任何可以使用的图标。"))
                return
            self.shortcutIcon = shortcutIcon
        self.iconPath = filename
        self.btnFace.setIcon(self.shortcutIcon)

    def restoreIcon(self):
        self.iconPath = ""
        self.shortcutIcon = getShortcutIcon(self.getResult())
        self.btnFace.setIcon(self.shortcutIcon)

    def restoreDir(self):
        "用户点击了“默认运行目录”按钮。"
        path = self.txtPath.text().strip()
        fi = QFileInfo(path)
        if path == "" or not fi.exists():
            return
        self.txtDir.setText(fi.dir().absolutePath())

    def browseDir(self):
        "用户点击了浏览运行目录按钮。"
        dirName = QFileDialog.getExistingDirectory(self, self.windowTitle(), self.txtDir.text())
        if dirName == "":
            return
        self.txtDir.setText(dirName)

    def browsePath(self):
        """用户点击了浏览路径的按钮。如果成功设置了路径，就返回True，如果用户取消了操作或者出错，就返回False
        返回的用途参见showEvent()"""
        filename, selectedFilter = QFileDialog.getOpenFileName(self, self.windowTitle())
        if not filename:
            return False
        fi = QFileInfo(filename)
        if fi.isSymLink():
            filename = fi.symLinkTarget()
            if not os.path.exists(filename):
                QMessageBox.information(self, self.windowTitle(), self.tr("快捷方式所指向的程序不正确。"))
                return False
        fi = QFileInfo(filename)
        self.txtName.setText(fi.baseName())
        self.txtPath.setText(fi.absoluteFilePath())
        self.setFileIcon(fi.absoluteFilePath())
        self.txtDir.setText(fi.dir().absolutePath())
        return True

    def setFileIcon(self, path):
        "每当txtPath的值改变时，就设置快捷方式的图标"
        fi = QFileInfo(path)
        if not fi.exists():
            self.shortcutIcon = QIcon(":/images/unknown.png")
        else:
            ip = QFileIconProvider()
            self.shortcutIcon = ip.icon(fi)
        self.btnFace.setIcon(self.shortcutIcon)

    def browseOpenwith(self):
        filename, selectedFilter = QFileDialog.getOpenFileName(self, self.windowTitle())
        if not filename:
            return
        fi = QFileInfo(filename)
        if fi.isSymLink():
            filename = fi.symLinkTarget()
            if not os.path.exists(filename):
                QMessageBox.information(self, self.windowTitle(),
                        self.tr("快捷方式所指向的程序不正确。"))
                return
        fi = QFileInfo(filename)
        if not fi.isExecutable():
            QMessageBox.information(self, self.windowTitle(),
                    self.tr("编辑程序必须是一个可执行文件。请重新选择。该选项是选填项，并不一定要填写。"))
        self.txtOpenwith.setText(fi.absoluteFilePath())

    def getResult(self):
        shortcut = {}
        shortcut["name"] = self.txtName.text().strip()
        shortcut["icon"] = self.iconPath
        shortcut["path"] = self.txtPath.text().strip()
        shortcut["openwith"] = self.txtOpenwith.text().strip()
        shortcut["dir"] = self.txtDir.text().strip()
        return shortcut


class BookmarkDialog(QDialog, Ui_BookmarkDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.txtLink.setFocus(Qt.OtherFocusReason)

    def create(self):
        try:
            return getattr(self, "exec_")()
        except AttributeError:
            return getattr(self, "exec")()

    def edit(self, bookmark):
        self.txtName.setText(bookmark["name"])
        self.txtLink.setText(bookmark["path"])
        try:
            return getattr(self, "exec_")()
        except AttributeError:
            return getattr(self, "exec")()

    def getResult(self):
        bookmark = {}
        bookmark["name"] = self.txtName.text()
        bookmark["path"] = self.txtLink.text()
        bookmark["dir"] = ""
        bookmark["icon"] = ""
        bookmark["openwith"] = ""
        return bookmark

    def accept(self):
        if self.txtName.text().strip() == "":
            QMessageBox.information(self, self.windowTitle(), self.tr("请填写网络链接的名称。"))
            self.txtName.setFocus(Qt.OtherFocusReason)
            return
        if self.txtLink.text().strip() == "":
            QMessageBox.information(self, self.windowTitle(), self.tr("请填写网络链接的地址。"))
            self.txtLink.setFocus(Qt.OtherFocusReason)
            return
        url = QUrl.fromUserInput(self.txtLink.text().strip())
        if not url.isValid():
            QMessageBox.information(self, self.windowTitle(), self.tr("您填写的似乎不是正确的网络链接地址。"))
            self.txtLink.setFocus(Qt.OtherFocusReason)
            self.txtLink.selectAll()
            return
        QDialog.accept(self)

class Shortcut(Table):
    "快捷面板上的用户自定义图标"
    columns = {"id":"text",
             "name":"text",
             "path":"text",
             "openwith":"text",
             "dir":"text",
             "icon":"blob"}

class ShortcutDatabase(Database):
    tables = (Shortcut, )

    def createInitialData(self, table):
        if table is Shortcut:
            if os.name == "nt":
                self.insertShortcut({
                        "id": str(uuid.uuid4()),
                        "name": self.tr("我的电脑"),
                        "path": COMPUTER_PATH,
                        "openwith": "",
                        "icon": "",
                        "dir": "",
                })
            self.insertShortcut({
                    "id": str(uuid.uuid4()),
                    "name": self.tr("我的文档"),
                    "path": DOCUMENTS_PATH,
                    "openwith": "",
                    "icon": "",
                    "dir": "",
            })
            self.insertShortcut({
                    "id": str(uuid.uuid4()),
                    "name": self.tr("我的音乐"),
                    "path": MUSIC_PATH,
                    "openwith": "",
                    "icon": "",
                    "dir": "",
            })
            self.insertShortcut({
                    "id": str(uuid.uuid4()),
                    "name": self.tr("图片收藏"),
                    "path": PICTURES_PATH,
                    "openwith": "",
                    "icon": "",
                    "dir": "",
            })
