import sys
import logging

__all__ = ["GlobalKey"]

logger = logging.getLogger(__name__)


if sys.platform == "win32":
    from .winglobalkey import GlobalKey
else:
    try:
        from .x11globalkey import GlobalKey
    except (ImportError, OSError):
        logging.warning("X11 global key is not available, using fallback implementation")
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
