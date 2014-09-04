# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

from PyQt4.QtCore import QSize
from PyQt4.QtGui import QFrame, QListView, QHBoxLayout

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
