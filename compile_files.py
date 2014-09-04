#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import os, sys

curdir = os.path.abspath(os.path.dirname(__file__))
J = os.path.join
if os.path.exists("C:\\Python26\\pyrcc4.exe"):
    pyrcc = "C:\\Python26\\pyrcc4.exe"
elif os.path.exists(r"C:\Python34\Lib\site-packages\PyQt4\pyrcc4.exe"):
    pyrcc = r"C:\Python34\Lib\site-packages\PyQt4\pyrcc4.exe -py3"
elif os.path.exists("/usr/bin/pyrcc4"):
    pyrcc = "/usr/bin/pyrcc4"
else:
    print("pyrcc command is not exists.")
    sys.exit(1)

if os.path.exists("C:\\Python26\\pyuic4.bat"):
    pyuic = "C:\\Python26\\pyuic4.bat"
elif os.path.exists(r"C:\Python34\Lib\site-packages\PyQt4\pyuic4.bat"):
    pyuic = r"C:\Python34\Lib\site-packages\PyQt4\pyuic4.bat -w"
elif os.path.exists("/usr/bin/pyuic4"):
    pyuic = "/usr/bin/pyuic4"
else:
    print("pyuic command is not exists.")
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
