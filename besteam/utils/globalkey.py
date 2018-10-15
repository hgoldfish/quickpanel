import sys


__all__ = ["GlobalKey"]

if sys.platform == "win32":
    from .winglobalkey import GlobalKey
else:
    try:
        from PyKDE5.kdeui import KAction; KAction
        from .kdeglobalkey import GlobalKey
    except ImportError:
        from PyQt5.QtCore import pyqtSignal, QObject

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
