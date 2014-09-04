# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import uuid
from PyQt4.QtGui import QDialog, QMessageBox
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

    def editTask(self, task):
        d = SimpleTodoEditor()
        if d.edit(task) == QDialog.Accepted:
            task.update(d.getResult())
            return True
        return False

    def createTodo(self):
        d = SimpleTodoEditor()
        if d.create() == QDialog.Accepted:
            task = d.getResult()
            task["id"] = str(uuid.uuid4())
            return self.db.insertSimpleTodo(task)
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
            if todo["finishment"] == 100:
                continue
            todoList.append(todo)
        return todoList

    def updateTaskById(self, taskId):
        #不需要刷新其它界面
        pass


class SimpleTodoEditor(QDialog, Ui_SimpleTodoEditor):
    def __init__(self):
        QDialog.__init__(self) #TODO 选择一个parent
        self.setupUi(self)

    def edit(self, task):
        self.setWindowTitle(self.trUtf8("编辑待办事项"))
        self.btnSave.setText(self.trUtf8("保存(&S)"))
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
        self.setWindowTitle(self.trUtf8("创建待办事项"))
        self.btnSave.setText(self.trUtf8("创建(&C)"))
        self.rdoUnfinished.setChecked(True)
        try:
            return getattr(self, "exec")()
        except AttributeError:
            return getattr(self, "exec_")()

    def accept(self):
        if self.txtSubject.text().strip() == "":
            QMessageBox.information(self, self.windowTitle(), self.trUtf8("标题不能为空。"))
            return
        if not (self.rdoFinished.isChecked() or self.rdoProcessing.isChecked() or self.rdoUnfinished.isChecked()):
            QMessageBox.information(self, self.windowTitle(), self.trUtf8("请选择完成度。"))
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
