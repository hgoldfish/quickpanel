import uuid
from PyQt5.QtWidgets import QDialog, QMessageBox, QDialogButtonBox
from besteam.utils.sql import Database, Table
from .Ui_todo_editor import Ui_SimpleTodoEditor

__all__ = ["SimpleBackend"]

class SimpleTodo(Table):
    columns = {"id":"text",
            "finishment":"number",
            "subject":"text",
            }

class SimpleTodoDatabas(Database):
    tables = (SimpleTodo, )

class SimpleBackend:
    def __init__(self, databaseFile):
        self.db = SimpleTodoDatabas(databaseFile)
        self.showAll = False

    def editTask(self, parent, task):
        d = SimpleTodoEditor(parent)
        quickpanel = parent.window()
        result = quickpanel.runDialog(d.edit, task)
        if result == QDialog.Accepted:
            task.update(d.getResult())
            d.deleteLater()
            return True
        d.deleteLater()
        return False

    def createTodo(self, parent):
        d = SimpleTodoEditor(parent)
        quickpanel = parent.window()
        result = quickpanel.runDialog(d.create)
        if result == QDialog.Accepted:
            task = d.getResult()
            task["id"] = str(uuid.uuid4())
            d.deleteLater()
            return self.db.insertSimpleTodo(task)
        d.deleteLater()
        return None

    def createTodoQuickly(self, subject):
        task = {
                "id": str(uuid.uuid4()),
                "subject": subject,
                "finishment": 0,
        }
        return self.db.insertSimpleTodo(task)

    def removeTodo(self, task):
        task.deleteFromDatabase()

    def listTodo(self):
        todoList = []
        for todo in self.db.selectSimpleTodo(""):
            if not self.showAll and todo["finishment"] == 100:
                continue
            todoList.append(todo)
        return todoList

    def updateTaskById(self, taskId):
        #不需要刷新其它界面
        pass

    def setShowAll(self, showAll):
        self.showAll = showAll

class SimpleTodoEditor(QDialog, Ui_SimpleTodoEditor):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)

    def edit(self, task):
        self.setWindowTitle(self.tr("编辑待办事项"))
        self.txtSubject.setText(task["subject"])
        if task["finishment"] == 0:
            self.rdoUnfinished.setChecked(True)
        elif task["finishment"] == 100:
            self.rdoFinished.setChecked(True)
        else:
            self.rdoProcessing.setChecked(True)
        try:
            return getattr(self, "exec")()
        except AttributeError:
            return getattr(self, "exec_")()

    def create(self):
        self.setWindowTitle(self.tr("创建待办事项"))
        btnSave = self.buttonBox.button(QDialogButtonBox.Save)
        btnSave.setText(self.tr("创建(&C)"))
        self.rdoUnfinished.setChecked(True)
        try:
            return getattr(self, "exec")()
        except AttributeError:
            return getattr(self, "exec_")()

    def accept(self):
        if self.txtSubject.text().strip() == "":
            QMessageBox.information(self, self.windowTitle(), self.tr("标题不能为空。"))
            return
        if not (self.rdoFinished.isChecked() or self.rdoProcessing.isChecked() or self.rdoUnfinished.isChecked()):
            QMessageBox.information(self, self.windowTitle(), self.tr("请选择完成度。"))
            return
        QDialog.accept(self)

    def getResult(self):
        task = {}
        task["subject"] = self.txtSubject.text().strip()
        if self.rdoFinished.isChecked():
            task["finishment"] = 100
        elif self.rdoUnfinished.isChecked():
            task["finishment"] = 0
        else:
            task["finishment"] = 50
        return task
