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
            #init from left to right, and then from top to bottom

            desktopIconWidget = {}
            desktopIconWidget["id"] = "dd6afcb0-e223-4156-988d-20f20266c6f0"
            desktopIconWidget["enabled"] = True
            desktopIconWidget["left"] = 0
            desktopIconWidget["top"] = 0
            desktopIconWidget["width"] = 20
            desktopIconWidget["height"] = 22
            self.insertQuickPanelWidget(desktopIconWidget)

            machineLoadWidget = {}
            machineLoadWidget["id"] = "b0b6b9eb-aec0-4fe5-bfd0-d4d317fdd547"
            machineLoadWidget["enabled"] = True
            machineLoadWidget["left"] = 0
            machineLoadWidget["top"] = 22
            machineLoadWidget["width"] = 20
            machineLoadWidget["height"] = 5
            self.insertQuickPanelWidget(machineLoadWidget)

            calendarWidget = {}
            calendarWidget["id"] = "d94db588-663b-4a6f-b935-4ca9ff283c75"
            calendarWidget["enabled"] = True
            calendarWidget["left"] = 0
            calendarWidget["top"] = 27
            calendarWidget["width"] = 20
            calendarWidget["height"] = 3
            self.insertQuickPanelWidget(calendarWidget)

            quickAccessWidget = {}
            quickAccessWidget["id"] = "be6c197b-0181-47c0-a9fc-6a1fe5f1b3e6"
            quickAccessWidget["enabled"] = True
            quickAccessWidget["left"] = 20
            quickAccessWidget["top"] = 0
            quickAccessWidget["width"] = 20
            quickAccessWidget["height"] = 6
            quickAccessWidget["factory"] = "im.quick_panel.widgets.quick_access.QuickAccessWidget"
            self.insertQuickPanelWidget(quickAccessWidget)

            todoListWidget = {}
            todoListWidget["id"] = "bc8ada4f-50b8-49f7-917a-da163b6763e9"
            todoListWidget["enabled"] = True
            todoListWidget["left"] = 20
            todoListWidget["top"] = 6
            todoListWidget["width"] = 20
            todoListWidget["height"] = 16
            self.insertQuickPanelWidget(todoListWidget)

            textpadWidget = {}
            textpadWidget["id"] = "45d1ee54-f9bd-435e-93cf-b46a05b56514"
            textpadWidget["enabled"] = True
            textpadWidget["left"] = 20
            textpadWidget["top"] = 22
            textpadWidget["width"] = 20
            textpadWidget["height"] = 8
            self.insertQuickPanelWidget(textpadWidget)

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
