# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import sys


__all__ = ["GlobalKey"]

if sys.platform == "win32":
    from .winglobalkey import GlobalKey
else:
    try:
        from PyKDE4.kdeui import KAction; KAction
        from .kdeglobalkey import GlobalKey
    except ImportError:
        from PyQt4.QtCore import pyqtSignal, QObject

        class GlobalKey(QObject):
            catched = pyqtSignal(int)

            def __init__(self):
                super(GlobalKey, self).__init__()
                self.nextId = 0

            def close(self):
                pass

            def addHotKey(self, name, key):
                self.nextId += 1
                return self.nextId

            def removeHotKey(self, keyId):
                pass
