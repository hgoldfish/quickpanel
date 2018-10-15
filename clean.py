#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
os.unlink(os.path.join(current_dir, "quickpanel_rc.py"))
for root, dirs, filenames in os.walk(current_dir):
    for filename in filenames:
        path = os.path.join(root, filename)
        if filename.endswith((".pyc", ".pyo")):
            os.unlink(path)
        elif filename.startswith("Ui_") and filename.endswith(".py"):
            os.unlink(path)
