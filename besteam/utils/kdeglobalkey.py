# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass


from PyQt4.QtCore import pyqtSignal, QObject
from PyKDE4.kdeui import KAction, KGlobalAccel, KShortcut

class GlobalKey(QObject):
    catched = pyqtSignal(int)

    def __init__(self):
        super(QObject, self).__init__()
        self.nextId = 0
        self.actions = {}

    def close(self):
        for action in self.actions.values():
            action.setGlobalShortcutAllowed(False, KAction.NoAutoloading)
            #action.forgetGlobalShortcut()
        self.actions.clear()

    def addHotKey(self, name, key):
        if not KGlobalAccel.isGlobalShortcutAvailable(key):
            actions = KGlobalAccel.getGlobalShortcutsByKey(key)
            if KGlobalAccel.promptStealShortcutSystemwide(None, actions, key):
                KGlobalAccel.stealShortcutSystemwide(key)
        action = KAction(None)
        action.setObjectName(name)
        action.setText(name)
        action.setGlobalShortcut(KShortcut(key), \
                KAction.ShortcutType(KAction.ActiveShortcut | KAction.DefaultShortcut),
                KAction.NoAutoloading)
        action.triggered.connect(self.catchGlobalKey)
        self.actions[self.nextId] = action
        self.nextId += 1
        return self.nextId - 1

    def removeHotKey(self, keyId):
        if keyId not in self.actions:
            return
        action = self.actions.pop(keyId)
        action.setGlobalShortcutAllowed(False, KAction.NoAutoloading)
        #action.forgetGlobalShortcut()

    def catchGlobalKey(self, *args):
        sender = self.sender()
        for keyId, action in self.actions.items():
            if action is sender:
                self.catched.emit(keyId)
                return
