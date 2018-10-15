from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QFrame, QSizePolicy

__all__ = ["Canvas"]

class Canvas(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.widgets = []
        self.previousSize = None

    def showWidget(self, widget):
        self.widgets.append(widget)
        factorForWidth = self.width() / 40
        factorForHeight = self.height() / 30
        vrect = widget.rect
        trect = QRect(vrect.left() * factorForWidth + 3, vrect.top() * factorForHeight + 3,
                    vrect.width() * factorForWidth - 6, vrect.height() * factorForHeight - 6)
        widget.widget.setGeometry(trect)
        widget.widget.show()

    def closeWidget(self, widget):
        i = 0
        for widget_ in self.widgets:
            if widget_ is widget:
                self.widgets.pop(i)
                break
            i += 1

    def positWidgets(self, force = False):
        "显示QuickPanel时重新排布一下部件。因为屏幕分辨率可能会有改动什么的。"
        if not force and self.previousSize == self.size():
            return
        factorForWidth = self.width() / 40
        factorForHeight = self.height() / 30
        for widget in self.widgets:
            vrect = widget.rect
            trect = QRect(vrect.left() * factorForWidth + 3, vrect.top() * factorForHeight + 3,
                        vrect.width() * factorForWidth - 6, vrect.height() * factorForHeight - 6)
            widget.widget.setGeometry(trect)
        self.previousSize = self.size()

