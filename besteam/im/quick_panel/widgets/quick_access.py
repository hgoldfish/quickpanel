from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QFrame, QListView, QHBoxLayout

__all__ = ["QuickAccessWidget"]

class QuickAccessWidget(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setStyleSheet("QListView {background: transparent; }")
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.listView = QListView(self)
        self.layout().addWidget(self.listView)

        self.listView.setModel(self.window().quickAccessModel)
        self.listView.setMovement(QListView.Snap)
        self.listView.setFlow(QListView.LeftToRight)
        self.listView.setResizeMode(QListView.Adjust)
        gridSize = self.logicalDpiX() / 96 * 60
        self.listView.setGridSize(QSize(gridSize, gridSize))
        self.listView.setViewMode(QListView.IconMode)

        self.listView.activated.connect(self.listView.model().runShortcut)
