# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

from PyQt4.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt4.QtGui import QComboBox, QHeaderView, QMenu, QMessageBox, QStyledItemDelegate, \
        QWidget, QCursor
from .todo_backend import SimpleBackend
from .Ui_todolist import Ui_TodoListWidget

__all__ = ["TodoListWidget"]

def setListValue(listWidget, value):
    "设置QComboBox的值"
    for i in range(listWidget.count()):
        if listWidget.itemText(i) == value:
            listWidget.setCurrentIndex(i)
            return
    if listWidget.isEditable():
        listWidget.setEditText(value)

class TodoListWidget(QWidget, Ui_TodoListWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.backend = SimpleBackend(parent.window().platform.databaseFile)
        self.todoListModel = TodoListModel()
        self.todoListDelegate = TodoListDelegate()
        self.todoListModel.updateTodoList(self.backend.listTodo())
        self.tvTodoList.setModel(self.todoListModel)
        self.tvTodoList.header().setResizeMode(QHeaderView.ResizeToContents)
        self.tvTodoList.setItemDelegate(self.todoListDelegate)
        self.makeConnections()
        self.setStyleSheet("QTreeView {background:transparent;}")

    def makeConnections(self):
        self.tvTodoList.customContextMenuRequested.connect(self.onTodoListContextMenuReqeusted)
        self.actionCreateTodo.triggered.connect(self.createTodo)
        self.actionEditTodo.triggered.connect(self.editTodo)
        self.actionRemoveTodo.triggered.connect(self.removeTodo)
        self.actionModifyTodoSubject.triggered.connect(self.modifyTodoSubject)
        self.actionMarkFinished.triggered.connect(self.markFinished)
        self.actionMarkUnfinished.triggered.connect(self.markUnfinished)
        self.actionMarkProcessing.triggered.connect(self.markProcessing)
        self.btnAddTodo.clicked.connect(self.addTodoQuickly)
        self.todoListModel.taskUpdated.connect(self.backend.updateTaskById)
        self.chkShowAll.toggled.connect(self.setShowAll)

    def setShowAll(self, showAll):
        self.backend.setShowAll(showAll)
        self.todoListModel.updateTodoList(self.backend.listTodo())

    def showEvent(self, event):
        self.todoListModel.updateTodoList(self.backend.listTodo())
        QWidget.showEvent(self, event)

    def onTodoListContextMenuReqeusted(self, pos):
        index = self.tvTodoList.indexAt(pos)
        if index.isValid():
            self.tvTodoList.setCurrentIndex(index)
        menu = QMenu()
        if index.isValid():
            task = self.todoListModel.taskAt(index)
            if task["finishment"] == 0:
                menu.addAction(self.actionMarkProcessing)
                menu.addAction(self.actionMarkFinished)
            elif task["finishment"] < 100:
                menu.addAction(self.actionMarkUnfinished)
                menu.addAction(self.actionMarkFinished)
            else:
                menu.addAction(self.actionMarkUnfinished)
                menu.addAction(self.actionMarkProcessing)
        menu.addSeparator()
        menu.addAction(self.actionCreateTodo)
        if index.isValid():
            menu.addAction(self.actionRemoveTodo)
            menu.addAction(self.actionModifyTodoSubject)
            menu.addAction(self.actionEditTodo)
        try:
            getattr(menu, "exec")(QCursor.pos())
        except AttributeError:
            getattr(menu, "exec_")(QCursor.pos())

    def editTodo(self):
        currentIndex = self.tvTodoList.currentIndex()
        task = self.todoListModel.taskAt(currentIndex)
        if task is None:
            return
        if self.backend.editTask(self, task):
            self.todoListModel.updateTodo(currentIndex)

    def createTodo(self):
        task = self.backend.createTodo(self)
        if task is None:
            return
        index = self.todoListModel.appendTodo(task)
        if index.isValid():
            self.tvTodoList.setCurrentIndex(index)

    def removeTodo(self):
        currentIndex = self.tvTodoList.currentIndex()
        if not currentIndex.isValid():
            return
        self.backend.removeTodo(self.todoListModel.todoAt(currentIndex))
        self.todoListModel.removeTodo(currentIndex)

    def modifyTodoSubject(self):
        currentIndex = self.tvTodoList.currentIndex()
        if not currentIndex.isValid():
            return
        currentIndex = self.todoListModel.index(currentIndex.row(), 1, QModelIndex())
        self.tvTodoList.edit(currentIndex)

    def markFinished(self):
        self.markTodoState(100)

    def markUnfinished(self):
        self.markTodoState(0)

    def markProcessing(self):
        self.markTodoState(50)

    def markTodoState(self, finishment, currentIndex = None):
        if currentIndex is None:
            currentIndex = self.tvTodoList.currentIndex()
        if not currentIndex.isValid():
            return
        task = self.todoListModel.taskAt(currentIndex)
        task["finishment"] = finishment
        self.todoListModel.updateTodo(currentIndex)
        self.backend.updateTaskById(task["id"])

    def addTodoQuickly(self):
        subject = self.txtTodoSubject.text().strip()
        if subject == "":
            QMessageBox.information(self, self.trUtf8("添加待办事项"), self.trUtf8("不能添加空的待办事项。"))
            return
        task = self.backend.createTodoQuickly(subject)
        index = self.todoListModel.appendTodo(task)
        self.tvTodoList.setCurrentIndex(index)
        self.txtTodoSubject.setText("")
        self.txtTodoSubject.setFocus(Qt.OtherFocusReason)


class TodoListModel(QAbstractTableModel):
    taskUpdated = pyqtSignal(str) #当用户直接编辑待办事项的主题时引发这个信号，其中的参数是待办事项的ID

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.todoList = []

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.todoList)
        return 0

    def columnCount(self, parent):
        if not parent.isValid():
            return 2
        return 0

    def data(self, index, role):
        if not index.isValid():
            return None
        if index.column() == 1 and role in (Qt.DisplayRole, Qt.EditRole):
            return self.todoList[index.row()]["subject"]
        elif index.column() == 0 and role in (Qt.DisplayRole, Qt.EditRole):
            finishment = self.todoList[index.row()]["finishment"]
            if finishment == 0:
                state = self.trUtf8("未开始")
            elif finishment == 100:
                state = self.trUtf8("已完成")
            else:
                state = self.trUtf8("进行中")
            return state
        return None

    def setData(self, index, value, role):
        if role == Qt.EditRole and index.isValid():
            task = self.todoList[index.row()]
            if index.column() == 0:
                if value == self.trUtf8("未开始"):
                    task["finishment"] = 0
                elif value == self.trUtf8("已完成"):
                    task["finishment"] = 100
                else:
                    task["finishment"] = 50
            else:
                assert index.column() == 1
                task["subject"] = value
            self.dataChanged.emit(index, index)
            self.taskUpdated.emit(task["id"])
            return True
        return QAbstractTableModel.setData(self, index, value, role)

    def flags(self, index):
        if index.isValid():
            return Qt.ItemIsEditable | QAbstractTableModel.flags(self, index)
        return QAbstractTableModel.flags(self, index)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return self.trUtf8("完成状态") #注意标题宽度要大于编辑完成状态时显示的QComboBox
            elif section == 1:
                return self.trUtf8("标题")
        return None

    def updateTodoList(self, todoList):
        "更新待办事项列表。当快捷面板被显示时，刷新列表内容。"
        self.todoList = todoList
        self.reset()

    def todoAt(self, index):
        assert index.isValid()
        return self.todoList[index.row()]

    def removeTodo(self, index):
        self.beginRemoveRows(QModelIndex(), index.row(), index.row())
        self.todoList.pop(index.row())
        self.endRemoveRows()

    def updateTodo(self, index):
        topLeft = self.createIndex(index.row(), 0)
        bottomRight = self.createIndex(index.row(), 1)
        self.dataChanged.emit(topLeft, bottomRight)

    def taskAt(self, index):
        return self.todoList[index.row()]

    def appendTodo(self, task):
        self.beginInsertRows(QModelIndex(), len(self.todoList), len(self.todoList))
        self.todoList.append(task)
        self.endInsertRows()
        return self.createIndex(len(self.todoList) - 1, 0)


class TodoListDelegate(QStyledItemDelegate):
    "待办事项列表第一列是状态，需要使用QComboBox进行选择。所以设置自定义的Delegate"
    def createEditor(self, parent, option, index):
        if index.isValid() and index.column() == 0:
            finishmentWidget = QComboBox(parent)
            finishmentWidget.addItems([self.trUtf8("已完成"), self.trUtf8("进行中"), self.trUtf8("未完成")])
            return finishmentWidget
        return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, widget, index):
        if index.isValid() and index.column() == 0:
            setListValue(widget, index.data(Qt.EditRole))
            return
        QStyledItemDelegate.setEditorData(self, widget, index)

    def setModelData(self, editor, model, index):
        if index.isValid() and index.column() == 0:
            model.setData(index, editor.currentText(), Qt.EditRole)
            return
        QStyledItemDelegate.setModelData(self, editor, model, index)
