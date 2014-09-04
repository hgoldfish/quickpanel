#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import sys, logging, os, sip
sip.setapi("QString", 2)
sip.setapi("QVariant", 2)
sip.setapi("QTextStream", 2)
sip.setapi("QUrl", 2)
sip.setapi("QDateTime", 2)
sip.setapi("QDate", 2)

from PyQt4.QtCore import QObject, pyqtSignal
from PyQt4.QtGui import QApplication, QFont,  QIcon, QSystemTrayIcon, \
        QAction, QMenu, QPushButton, QLabel, QDialog, QSizePolicy, \
        QKeySequence, QDialogButtonBox, QVBoxLayout, QHBoxLayout, \
        QMessageBox, QDesktopServices
import quickpanel_rc; quickpanel_rc
from besteam.utils.settings import Settings, _Settings
from besteam.utils.globalkey import GlobalKey
from besteam.im.quick_panel import QuickPanel
from tetrix import TetrixWindow

logger = logging.getLogger("quickpanel")

class SetKeyWidget(QPushButton):
    editingFinished = pyqtSignal()

    def __init__(self, parent = None):
        QPushButton.__init__(self, parent)
        self.setCheckable(True)

    def keyPressEvent(self, event):
        if self.isChecked() and event.text() != "":
            self.setText(QKeySequence(event.key() | int(event.modifiers())).toString(QKeySequence.NativeText))
            self.setChecked(False)
            self.editingFinished.emit()
        else:
            QPushButton.keyPressEvent(self, event)

class ConfigureDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.lblKey = QLabel("Global Key:")
        self.btnKey = SetKeyWidget(self)
        self.btnKey.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.setLayout(QVBoxLayout())
        layout1 = QHBoxLayout()
        layout1.addWidget(self.lblKey)
        layout1.addWidget(self.btnKey)
        self.layout().addLayout(layout1)
        self.layout().addStretch()
        self.layout().addWidget(buttonBox)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

    def setGlobalKey(self, globalKeyName):
        self.btnKey.setText(globalKeyName)

    def getGlobalKey(self):
        return self.btnKey.text()


class Platform(QObject):
    def __init__(self):
        QObject.__init__(self)
        documentsLocation = QDesktopServices.storageLocation(QDesktopServices.DocumentsLocation)
        self.databaseFile = os.path.join(documentsLocation, "quickpanel.db")
        self._settings = _Settings(self.databaseFile)
        self.globalKey = GlobalKey()
        self.quickPanel = QuickPanel(self)
        self.actionConfigure = QAction(QIcon(":/images/configure.png"), \
                self.trUtf8("&Configure"), self)
        self.actionExit = QAction(QIcon(":/images/close.png"), \
                self.trUtf8("&Exit"), self)
        self.trayIcon = QSystemTrayIcon(QIcon(":/images/angelfish.png"))
        self.contextMenu = QMenu()
        self.contextMenu.addAction(self.actionConfigure)
        self.contextMenu.addAction(self.actionExit)
        self.trayIcon.setContextMenu(self.contextMenu)
        self.actionConfigure.triggered.connect(self.configure)
        self.actionExit.triggered.connect(self.exit)
        self.trayIcon.activated.connect(self.onTrayIconActivated)

    def start(self):
        self.loadSettings()
        self.trayIcon.show()
        self.quickPanel.initWidgets()
        logger.info("QuickPanel is launched.")
        self.quickPanel.addQuickAccessShortcut(self.trUtf8("Tetrix"), \
                QIcon(":/images/tetrix.png"), self.startTetrix)
        self.quickPanel.addQuickAccessShortcut(self.trUtf8("Hello"), \
                QIcon(":/images/hello.png"), self.sayHello)

    def startTetrix(self):
        if getattr(self, "tetrixWindow", None) is None:
            self.tetrixWindow = TetrixWindow()
        self.tetrixWindow.show()
        self.tetrixWindow.activateWindow()

    def sayHello(self):
        QMessageBox.information(None, self.trUtf8("Say Hello."), \
                self.trUtf8("Hello, world!"))

    def loadSettings(self):
        settings = self.getSettings()
        keyname = settings.value("globalkey", "Alt+`")
        self.keyId = self.globalKey.addHotKey("actionToggleQuickPanel", keyname)
        self.globalKey.catched.connect(self.quickPanel.toggle)

    def saveSettings(self):
        pass

    def configure(self):
        d = ConfigureDialog()
        settings = self.getSettings()
        keyname = settings.value("globalkey", "Alt+`")
        d.setGlobalKey(keyname)
        self.globalKey.removeHotKey(self.keyId)
        try:
            result = getattr(d, "exec")()
        except AttributeError:
            result = getattr(d, "exec_")()
        if result == QDialog.Accepted:
            keyname = d.getGlobalKey()
            settings.setValue("globalkey", keyname)
        self.keyId = self.globalKey.addHotKey("actionToggleQuickPanel", keyname)

    def exit(self):
        self.quickPanel.finalize()
        self.saveSettings()
        self.globalKey.close()
        logger.info("QuickPanel is shutting down.")
        QApplication.instance().quit()

    def onTrayIconActivated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.quickPanel.toggle()

    def getSettings(self):
        return Settings(self._settings)

def main():
    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setFont(QFont("Tahoma", 9))
    app.setOrganizationName("Besteam")
    app.setOrganizationDomain("besteam.im")
    app.setApplicationName("QuickPanel")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(":/images/angelfish.png"))
    #app.setStyle(QStyleFactory.create("qtcurve"))
    platform = Platform()
    platform.start()
    try:
        getattr(app, "exec")()
    except AttributeError:
        getattr(app, "exec_")()

if __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)
    main()
