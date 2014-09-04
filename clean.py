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

import os

currentDir = os.path.dirname(os.path.abspath(__file__))

for root, dirs, filenames in os.walk(str(currentDir)):
    for filename in filenames:
        path = os.path.join(root, filename)
        if filename.endswith((".pyc", ".pyo")):
            os.unlink(path)
        elif filename.startswith("Ui_") and filename.endswith(".py"):
            os.unlink(path)
