# -*- coding:utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

import logging
from besteam.utils.sql import Database, Table

__all__ = ["WidgetConfigure", "QuickPanelDatabase"]

logger = logging.getLogger(__name__)

class WidgetConfigure:
    id = None
    name = None
    description = None
    factory = None
    rect = None
    enabled = False
    widget = None

    def __repr__(self):
        return repr(self.__dict__)


class QuickPanelWidget(Table):
    columns = {
        "id":"text",
        "enabled":"bool", #当前是否启用
        "left":"number", #接下来的left, top, width, height纪录插件的位置，如果插件没有被启用。这四个字段是没有意义的
        "top":"number",
        "width":"number",
        "height":"number",
    }

class QuickPanelDatabase(Database):
    tables = (QuickPanelWidget, )

    def createInitialData(self, table):
        if table is QuickPanelWidget:
            caculatorWidget = {}
            caculatorWidget["id"] = "eb7e96a0-d839-4d8c-9fbf-84c1a81803ae"
            caculatorWidget["enabled"] = True
            caculatorWidget["left"] = 20
            caculatorWidget["top"] = 20
            caculatorWidget["width"] = 20
            caculatorWidget["height"] = 10
            self.insertQuickPanelWidget(caculatorWidget)

            desktopIconWidget = {}
            desktopIconWidget["id"] = "dd6afcb0-e223-4156-988d-20f20266c6f0"
            desktopIconWidget["enabled"] = True
            desktopIconWidget["left"] = 0
            desktopIconWidget["top"] = 0
            desktopIconWidget["width"] = 20
            desktopIconWidget["height"] = 20
            self.insertQuickPanelWidget(desktopIconWidget)

            textpadWidget = {}
            textpadWidget["id"] = "45d1ee54-f9bd-435e-93cf-b46a05b56514"
            textpadWidget["enabled"] = True
            textpadWidget["left"] = 0
            textpadWidget["top"] = 20
            textpadWidget["width"] = 20
            textpadWidget["height"] = 10
            self.insertQuickPanelWidget(textpadWidget)

            quickAccessWidget = {}
            quickAccessWidget["id"] = "be6c197b-0181-47c0-a9fc-6a1fe5f1b3e6"
            quickAccessWidget["enabled"] = True
            quickAccessWidget["left"] = 20
            quickAccessWidget["top"] = 0
            quickAccessWidget["width"] = 20
            quickAccessWidget["height"] = 8
            quickAccessWidget["factory"] = "im.quick_panel.widgets.quick_access.QuickAccessWidget"
            self.insertQuickPanelWidget(quickAccessWidget)

            todoListWidget = {}
            todoListWidget["id"] = "bc8ada4f-50b8-49f7-917a-da163b6763e9"
            todoListWidget["enabled"] = True
            todoListWidget["left"] = 20
            todoListWidget["top"] = 8
            todoListWidget["width"] = 20
            todoListWidget["height"] = 12
            self.insertQuickPanelWidget(todoListWidget)

    def getWidgetConfig(self, id):
        rows = self.selectQuickPanelWidget("where id=?", id)
        if not rows:
            return None
        return dict(rows[0])

    def saveWidgetConfig(self, config):
        rows = self.selectQuickPanelWidget("where id=?", config["id"])
        if rows:
            self.updateQuickPanelWidget(config, "where id=?", config["id"])
        else:
            self.insertQuickPanelWidget(config)

    def setWidgetEnabled(self, id, enabled):
        self.updateQuickPanelWidget({"enabled": enabled}, "where id=?", id)
