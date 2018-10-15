from PyQt5.QtWidgets import QFrame, QPlainTextEdit, QHBoxLayout

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

