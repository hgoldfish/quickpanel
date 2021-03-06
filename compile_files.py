#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

class NotFound(Exception):
    pass

def findPyQtTools_win32():
    pythondir = os.path.dirname(sys.executable)
    systempaths = os.environ["PATH"].split(";")
    systempaths = [path.strip() for path in systempaths]

    def findTool(toolname):
        tool = os.path.join(pythondir, toolname)
        if not os.path.exists(tool):
            tool = os.path.join(pythondir, "Scripts", toolname)
        if not os.path.exists(tool):
            tool = os.path.join(pythondir, "Lib\\site-packages\\PyQt5", toolname)
        if not os.path.exists(tool):
            for systempath in systempaths:
                tool = os.path.join(systempath, toolname)
                if os.path.exists(tool):
                    break
        if not os.path.exists(tool):
            raise NotFound()
        return tool

    pyrcc = findTool("pyrcc5.bat")
    pyuic = findTool("pyuic5.bat")
    return pyrcc, pyuic

def findPyQtTools_linux():
    pyrcc = "/usr/bin/pyrcc5"
    if not os.path.exists(pyrcc):
        pyrcc = "/usr/local/bin/pyrcc5"
    if not os.path.exists(pyrcc):
        raise NotFound()

    pyuic = "/usr/bin/pyuic5"
    if not os.path.exists(pyuic):
        pyuic = "/usr/local/bin/pyuic5"
    if not os.path.exists(pyuic):
        raise NotFound()

    return pyrcc, pyuic

curdir = os.path.abspath(os.path.dirname(__file__))
J = os.path.join

try:
    pyrcc, pyuic = findPyQtTools_win32() if os.name == "nt" else findPyQtTools_linux()
except NotFound:
    print("pyqt tools are not found in your machine.")
    sys.exit(1)

if not os.path.exists(J(curdir, "quickpanel_rc.py")) or \
        os.path.getmtime(J(curdir, "quickpanel_rc.py")) < os.path.getmtime(J(curdir, "quickpanel.qrc")):
    print("compile quickpanel.qrc to quickpanel_rc.py")
    os.system("{2} -o {0} {1}".format(J(curdir, "quickpanel_rc.py"), J(curdir, "quickpanel.qrc"), pyrcc))

for root, dirs, files in os.walk(os.path.join(curdir, "besteam")):
    for filename in files:
        if not filename.endswith(".ui"):
            continue
        basename = "Ui_" + os.path.splitext(filename)[0] + ".py"
        pyfile = J(root, basename)
        uifile = J(root, filename)
        if os.path.exists(pyfile) and os.path.getmtime(pyfile) > os.path.getmtime(uifile):
            continue
        print("compiling", uifile, "to", pyfile)
        os.system("{2} -x -o {0} {1}".format(pyfile, uifile, pyuic))
