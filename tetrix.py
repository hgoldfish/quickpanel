#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

"""
从Qt的示例程序改的俄罗斯方块。最早出现在PyQt的例子里面，但是有些BUG，而且不够好看。
我拿过来改一改
"""

import random, sys, sip
try:
    sip.setapi("QString" ,2)
except ValueError:
    pass

from PyQt4 import QtCore, QtGui


NoShape, ZShape, SShape, LineShape, TShape, SquareShape, LShape, MirroredLShape = range(8)

random.seed(None)

__all__ = ["TetrixWindow"]

class TetrixWindow(QtGui.QWidget):
    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent, QtCore.Qt.Window)

        self.board = TetrixBoard()
        self.indictor = TetrixIndictor()

        nextPieceLabel = QtGui.QLabel(self)
        nextPieceLabel.setFrameStyle(QtGui.QFrame.Box | QtGui.QFrame.Raised)
        nextPieceLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.board.setNextPieceLabel(nextPieceLabel)

        scoreLcd = QtGui.QLCDNumber(6)
        scoreLcd.setSegmentStyle(QtGui.QLCDNumber.Filled)
        levelLcd = QtGui.QLCDNumber(2)
        levelLcd.setSegmentStyle(QtGui.QLCDNumber.Filled)
        linesLcd = QtGui.QLCDNumber(6)
        linesLcd.setSegmentStyle(QtGui.QLCDNumber.Filled)

        startButton = QtGui.QPushButton(self.trUtf8("开始(&S)"))
        startButton.setFocusPolicy(QtCore.Qt.NoFocus)
        quitButton = QtGui.QPushButton(self.trUtf8("退出(&X)"))
        quitButton.setFocusPolicy(QtCore.Qt.NoFocus)
        pauseButton = QtGui.QPushButton(self.trUtf8("暂停(&P)"))
        pauseButton.setFocusPolicy(QtCore.Qt.NoFocus)

        startButton.clicked.connect(self.board.start)
        pauseButton.clicked.connect(self.board.pause)
        quitButton.clicked.connect(self.close)
        self.board.scoreChanged.connect(scoreLcd.display)
        self.board.levelChanged.connect(levelLcd.display)
        self.board.linesRemovedChanged.connect(linesLcd.display)
        self.board.act.connect(self.indictor.showIndictor)

        layout1 = QtGui.QHBoxLayout()
        layout3 = QtGui.QVBoxLayout()
        layout3.addWidget(self.board)
        layout3.addWidget(self.indictor)
        layout3.setSpacing(0)
        layout1.addLayout(layout3)
        layout2 = QtGui.QVBoxLayout()
        layout2.addWidget(self.createLabel(self.trUtf8("下一个方块")))
        layout2.addWidget(nextPieceLabel)
        layout2.addWidget(self.createLabel(self.trUtf8("级别")))
        layout2.addWidget(levelLcd)
        layout2.addWidget(self.createLabel(self.trUtf8("成绩")),)
        layout2.addWidget(scoreLcd)
        layout2.addWidget(self.createLabel(self.trUtf8("总共消去行数")))
        layout2.addWidget(linesLcd)
        layout2.addWidget(startButton)
        layout2.addWidget(quitButton)
        layout2.addWidget(pauseButton)
        layout1.addLayout(layout2)
        layout1.setStretch(0, 75)
        layout1.setStretch(1, 25)
        self.setLayout(layout1)

        self.setWindowTitle(self.trUtf8("俄罗斯方块(Tetrix)"))
        self.resize(self.logicalDpiX() / 96 * 275, self.logicalDpiY() / 96 * 380)

        r = self.geometry()
        r.moveCenter(QtGui.qApp.desktop().screenGeometry().center())
        self.setGeometry(r)

    def createLabel(self, text):
        lbl = QtGui.QLabel(text)
        lbl.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
        return lbl


class TetrixIndictor(QtGui.QWidget):
    """位于主游戏区下方的一个扁小的控件，用于显示当前位置落下时的位置。
    现在主要的问题是游戏区的大小超出了人类的眼睛的焦点区。
    或许可以让整个游戏界面更小一些。"""

    def __init__(self, parent = None):
        QtGui.QWidget.__init__(self, parent)
        self.begin = self.end = None
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)

    def showIndictor(self, curX, piece):
        self.begin = curX + piece.minX()
        self.end = curX + piece.maxX()
        self.update()

    def paintEvent(self, event):
        QtGui.QWidget.paintEvent(self, event)
        if self.begin is None:
            return
        board = self.parent().board
        pieceWidth = board.contentsRect().width() // TetrixBoard.BoardWidth
        brush = QtGui.QBrush(QtCore.Qt.yellow)
        painter = QtGui.QPainter(self)
        painter.setBrush(brush)
        painter.drawRect(board.contentsRect().left() + self.begin * pieceWidth, 0, \
                         (self.end - self.begin + 1) * pieceWidth, self.height() - 1 )

    def sizeHint(self):
        return QtCore.QSize(self.parent().board.width(), 8)


class TetrixBoard(QtGui.QFrame):
    BoardWidth = 11
    BoardHeight = 22

    scoreChanged = QtCore.pyqtSignal(int)
    levelChanged = QtCore.pyqtSignal(int)
    linesRemovedChanged = QtCore.pyqtSignal(int)
    act = QtCore.pyqtSignal(int, "PyQt_PyObject")

    def __init__(self, parent = None):
        super(TetrixBoard, self).__init__(parent)
        self.setStyleSheet("background-color:black;border:2px solid darkGreen;")

        self.timer = QtCore.QBasicTimer()
        self.nextPieceLabel = None
        self.isWaitingAfterLine = False
        self.curPiece = TetrixPiece()
        self.nextPiece = TetrixPiece()
        self.curX = 0
        self.curY = 0
        self.numLinesRemoved = 0
        self.numPiecesDropped = 0
        self.score = 0
        self.level = 0
        self.board = None

        #self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Sunken)
        self.setFrameStyle(QtGui.QFrame.Box)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.isStarted = False
        self.isPaused = False
        self.clearBoard()

        self.nextPiece.setRandomShape()

    def focusOutEvent(self, event):
        if self.isStarted and not self.isPaused:
            self.pause()
        QtGui.QFrame.focusOutEvent(self, event)

    def shapeAt(self, x, y):
        return self.board[(y * TetrixBoard.BoardWidth) + x]

    def setShapeAt(self, x, y, shape):
        self.board[(y * TetrixBoard.BoardWidth) + x] = shape

    def timeoutTime(self):
        return 1000 // (1 + self.level)

    def squareWidth(self):
        return self.contentsRect().width() // TetrixBoard.BoardWidth

    def squareHeight(self):
        return self.contentsRect().height() // TetrixBoard.BoardHeight

    def setNextPieceLabel(self, label):
        self.nextPieceLabel = label
        #label.setScaledContents(True)
        label.setMinimumSize(label.width(), label.width())

    def sizeHint(self):
        return QtCore.QSize(TetrixBoard.BoardWidth * 15 + self.frameWidth() * 2,
                TetrixBoard.BoardHeight * 15 + self.frameWidth() * 2)

    def minimumSizeHint(self):
        return QtCore.QSize(TetrixBoard.BoardWidth * 15 + self.frameWidth() * 2,
                TetrixBoard.BoardHeight * 15 + self.frameWidth() * 2)

    def start(self):
        if self.isPaused:
            return

        self.isStarted = True
        self.isWaitingAfterLine = False
        self.numLinesRemoved = 0
        self.numPiecesDropped = 0
        self.score = 0
        self.level = 1
        self.clearBoard()

        self.linesRemovedChanged.emit(self.numLinesRemoved)
        self.scoreChanged.emit(self.score)
        self.levelChanged.emit(self.level)

        self.newPiece()
        self.timer.start(self.timeoutTime(), self)

    def pause(self):
        if not self.isStarted:
            return

        self.isPaused = not self.isPaused
        if self.isPaused:
            self.timer.stop()
        else:
            self.timer.start(self.timeoutTime(), self)

        self.update()

    def paintEvent(self, event):
        super(TetrixBoard, self).paintEvent(event)

        painter = QtGui.QPainter(self)
        rect = self.contentsRect()

        if self.isPaused:
            painter.drawText(rect, QtCore.Qt.AlignCenter, self.trUtf8("暂停"))
            return

        boardTop = rect.bottom() - TetrixBoard.BoardHeight * self.squareHeight()

        for i in range(TetrixBoard.BoardHeight):
            for j in range(TetrixBoard.BoardWidth):
                shape = self.shapeAt(j, TetrixBoard.BoardHeight - i - 1)
                if shape != NoShape:
                    self.drawSquare(painter,
                            rect.left() + j * self.squareWidth(),
                            boardTop + i * self.squareHeight(), shape)

        if self.curPiece.shape() != NoShape:
            for i in range(4):
                x = self.curX + self.curPiece.x(i)
                y = self.curY - self.curPiece.y(i)
                self.drawSquare(painter, rect.left() + x * self.squareWidth(),
                        boardTop + (TetrixBoard.BoardHeight - y - 1) * self.squareHeight(),
                        self.curPiece.shape())

    def keyPressEvent(self, event):
        if not self.isStarted or self.isPaused or self.curPiece.shape() == NoShape:
            super(TetrixBoard, self).keyPressEvent(event)
            return

        key = event.key()
        if key == QtCore.Qt.Key_Left:
            self.tryMove(self.curPiece, self.curX - 1, self.curY)
        elif key == QtCore.Qt.Key_Right:
            self.tryMove(self.curPiece, self.curX + 1, self.curY)
        elif key == QtCore.Qt.Key_Down:
            self.tryMove(self.curPiece.rotatedRight(), self.curX, self.curY)
        elif key == QtCore.Qt.Key_Up:
            self.tryMove(self.curPiece.rotatedLeft(), self.curX, self.curY)
        elif key == QtCore.Qt.Key_Space:
            self.dropDown()
        elif key == QtCore.Qt.Key_D:
            self.oneLineDown()
        else:
            super(TetrixBoard, self).keyPressEvent(event)

    def timerEvent(self, event):
        if event.timerId() == self.timer.timerId():
            if self.isWaitingAfterLine:
                self.isWaitingAfterLine = False
                self.newPiece()
                self.timer.start(self.timeoutTime(), self)
            else:
                self.oneLineDown()
        else:
            super(TetrixBoard, self).timerEvent(event)

    def clearBoard(self):
        self.board = [NoShape for i in range(TetrixBoard.BoardHeight * TetrixBoard.BoardWidth)]

    def dropDown(self):
        dropHeight = 0
        newY = self.curY
        while newY > 0:
            if not self.tryMove(self.curPiece, self.curX, newY - 1):
                break
            newY -= 1
            dropHeight += 1

        self.pieceDropped(dropHeight)

    def oneLineDown(self):
        if not self.tryMove(self.curPiece, self.curX, self.curY - 1):
            self.pieceDropped(0)

    def pieceDropped(self, dropHeight):
        for i in range(4):
            x = self.curX + self.curPiece.x(i)
            y = self.curY - self.curPiece.y(i)
            self.setShapeAt(x, y, self.curPiece.shape())

        self.numPiecesDropped += 1
        if self.numPiecesDropped % 25 == 0:
            self.level += 1
            self.timer.start(self.timeoutTime(), self)
            self.levelChanged.emit(self.level)

        self.score += dropHeight + 7
        self.scoreChanged.emit(self.score)
        self.removeFullLines()

        if not self.isWaitingAfterLine:
            self.newPiece()

    def removeFullLines(self):
        numFullLines = 0

        for i in range(TetrixBoard.BoardHeight - 1, -1, -1):
            lineIsFull = True

            for j in range(TetrixBoard.BoardWidth):
                if self.shapeAt(j, i) == NoShape:
                    lineIsFull = False
                    break

            if lineIsFull:
                numFullLines += 1
                for k in range(i, TetrixBoard.BoardHeight - 1):
                    for j in range(TetrixBoard.BoardWidth):
                        self.setShapeAt(j, k, self.shapeAt(j, k + 1))

                for j in range(TetrixBoard.BoardWidth):
                    self.setShapeAt(j, TetrixBoard.BoardHeight - 1, NoShape)

        if numFullLines > 0:
            self.numLinesRemoved += numFullLines
            self.score += 10 * numFullLines
            self.linesRemovedChanged.emit(self.numLinesRemoved)
            self.scoreChanged.emit(self.score)

            self.timer.start(200, self)
            self.isWaitingAfterLine = True
            self.curPiece.setShape(NoShape)
            self.update()

    def newPiece(self):
        self.curPiece = self.nextPiece
        self.nextPiece = TetrixPiece()
        self.nextPiece.setRandomShape()
        self.showNextPiece()
        self.curX = TetrixBoard.BoardWidth // 2
        self.curY = TetrixBoard.BoardHeight - 1 + self.curPiece.minY()
        self.act.emit(self.curX, self.curPiece)

        if not self.tryMove(self.curPiece, self.curX, self.curY):
            self.curPiece.setShape(NoShape)
            self.timer.stop()
            self.isStarted = False

    def showNextPiece(self):
        if self.nextPieceLabel is None:
            return

        dx = self.nextPiece.maxX() - self.nextPiece.minX() + 1
        dy = self.nextPiece.maxY() - self.nextPiece.minY() + 1

        self.pixmapNextPiece = QtGui.QPixmap(dx * self.squareWidth(), dy * self.squareHeight())
        painter = QtGui.QPainter(self.pixmapNextPiece)
        painter.fillRect(self.pixmapNextPiece.rect(), self.nextPieceLabel.palette().background())

        for i in range(4):
            x = self.nextPiece.x(i) - self.nextPiece.minX()
            y = self.nextPiece.y(i) - self.nextPiece.minY()
            self.drawSquare(painter, x * self.squareWidth(),
                    y * self.squareHeight(), self.nextPiece.shape())

        self.nextPieceLabel.setPixmap(self.pixmapNextPiece)

    def tryMove(self, newPiece, newX, newY):
        for i in range(4):
            x = newX + newPiece.x(i)
            y = newY - newPiece.y(i)
            if x < 0 or x >= TetrixBoard.BoardWidth or y < 0 or y >= TetrixBoard.BoardHeight:
                return False
            if self.shapeAt(x, y) != NoShape:
                return False

        self.curPiece = newPiece
        self.curX = newX
        self.curY = newY
        self.update()
        self.act.emit(self.curX, self.curPiece)
        return True

    def drawSquare(self, painter, x, y, shape):
        colorTable = [0x000000, 0xCC6666, 0x66CC66, 0x6666CC,
                      0xCCCC66, 0xCC66CC, 0x66CCCC, 0xDAAA00]

        color = QtGui.QColor(colorTable[shape])
        painter.fillRect(x + 1, y + 1, self.squareWidth() - 2,
                self.squareHeight() - 2, color)

        painter.setPen(color.light())
        painter.drawLine(x, y + self.squareHeight() - 1, x, y)
        painter.drawLine(x, y, x + self.squareWidth() - 1, y)

        painter.setPen(color.dark())
        painter.drawLine(x + 1, y + self.squareHeight() - 1,
                x + self.squareWidth() - 1, y + self.squareHeight() - 1)
        painter.drawLine(x + self.squareWidth() - 1,
                y + self.squareHeight() - 1, x + self.squareWidth() - 1, y + 1)


class TetrixPiece(object):
    coordsTable = (
        ((0, 0),     (0, 0),     (0, 0),     (0, 0)),
        ((0, -1),    (0, 0),     ( - 1, 0),    ( - 1, 1)),
        ((0, -1),    (0, 0),     (1, 0),     (1, 1)),
        ((0, -1),    (0, 0),     (0, 1),     (0, 2)),
        (( - 1, 0),    (0, 0),     (1, 0),     (0, 1)),
        ((0, 0),     (1, 0),     (0, 1),     (1, 1)),
        (( - 1, -1),   (0, -1),    (0, 0),     (0, 1)),
        ((1, -1),    (0, -1),    (0, 0),     (0, 1))
    )

    def __init__(self):
        self.coords = [[0,0] for _ in range(4)]
        self.pieceShape = NoShape

        self.setShape(NoShape)

    def shape(self):
        return self.pieceShape

    def setShape(self, shape):
        table = TetrixPiece.coordsTable[shape]
        for i in range(4):
            for j in range(2):
                self.coords[i][j] = table[i][j]

        self.pieceShape = shape

    def setRandomShape(self):
        self.setShape(random.randint(1, 7))

    def x(self, index):
        return self.coords[index][0]

    def y(self, index):
        return self.coords[index][1]

    def setX(self, index, x):
        self.coords[index][0] = x

    def setY(self, index, y):
        self.coords[index][1] = y

    def minX(self):
        m = self.coords[0][0]
        for i in range(4):
            m = min(m, self.coords[i][0])

        return m

    def maxX(self):
        m = self.coords[0][0]
        for i in range(4):
            m = max(m, self.coords[i][0])

        return m

    def minY(self):
        m = self.coords[0][1]
        for i in range(4):
            m = min(m, self.coords[i][1])

        return m

    def maxY(self):
        m = self.coords[0][1]
        for i in range(4):
            m = max(m, self.coords[i][1])

        return m

    def rotatedLeft(self):
        if self.pieceShape == SquareShape:
            return self

        result = TetrixPiece()
        result.pieceShape = self.pieceShape
        for i in range(4):
            result.setX(i, self.y(i))
            result.setY(i, -self.x(i))

        return result

    def rotatedRight(self):
        if self.pieceShape == SquareShape:
            return self

        result = TetrixPiece()
        result.pieceShape = self.pieceShape
        for i in range(4):
            result.setX(i, -self.y(i))
            result.setY(i, self.x(i))

        return result

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = TetrixWindow()
    window.show()
    if hasattr(app, "exec"):
        result = getattr(app, "exec")()
    else:
        result = getattr(app, "exec_")()
    sys.exit(result)

