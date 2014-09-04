# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

from PyQt4.QtGui import QFrame, QPlainTextEdit, QHBoxLayout

__all__ = ["TextpadWidget"]

class TextpadWidget(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.textpad = QPlainTextEdit(self)
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.textpad)

        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setStyleSheet("QPlainTextEdit{background:transparent;}")

        settings = self.window().platform.getSettings()
        text = settings.value("textpad", "")
        self.textpad.setPlainText(text)

    def finalize(self):
        settings = self.window().platform.getSettings()
        settings.setValue("textpad", self.textpad.toPlainText())

