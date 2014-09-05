# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
try:
    str = unicode
except NameError:
    pass

try:
    from PyQt4.QtCore import QObject, QTimer
except ImportError:
    try:
        from PyQt5.QtCore import QObject, QTimer
    except ImportError:
        class QObject: pass
        QTimer = None

import pickle
from besteam.utils.sql import transaction, Table, Database

class Preference(Table):
    pkName = "key"
    columns = {"key":"text",
             "value":"blob"}

class PreferenceDatabase(Database):
    tables = (Preference, )

class _Settings(QObject):
    class Item:
        key = None
        value = None
        dirty = False

    def __init__(self, db):
        super(_Settings, self).__init__()
        if type(db) is PreferenceDatabase:
            self.db = db
        else:
            self.db = PreferenceDatabase(db)
        self.preferences = []
        for row in self.db.selectPreference(""):
            item = _Settings.Item()
            item.key = row["key"]
            item.value = pickle.loads(row["value"])
            self.preferences.append(item)
        if QTimer:
            self.autoSaveTimer = QTimer()
            self.autoSaveTimer.timeout.connect(self.save)
            self.autoSaveTimer.start(5000)

    def __del__(self):
        self.save()

    def contains(self, key):
        for item in self.preferences:
            if item.key == key:
                return True
        return False

    def getPreference(self, key):
        for item in self.preferences:
            if item.key == key:
                return item.value
        raise KeyError()

    def setPreference(self, key, value):
        for item in self.preferences:
            if item.key == key:
                item.value = value
                item.dirty = True
                return True
        item = _Settings.Item()
        item.key = key
        item.value = value
        item.dirty = True
        self.preferences.append(item)
        return True

    def getPreferenceKeysWithPrefix(self, prefix):
        #XXX 是否包含子目录的键值呢？对照QSettings，应该是不包含的
        assert prefix.endswith("/")
        keys = []
        for item in self.preferences:
            if item.key.startswith(prefix):
                name = item.key[len(prefix):]
                if "/" not in name:
                    keys.append(name)
        return keys

    @transaction
    def removePreference(self, key):
        for item in self.preferences:
            if item.key == key:
                self.preferences.remove(item)
                self.db.deletePreference("where key=?", key)
                return
        raise KeyError()

    @transaction
    def save(self):
        for item in self.preferences:
            if not item.dirty:
                continue
            self.db.deletePreference("where key=?", item.key)
            self.db.insertPreference({"key":item.key, "value":pickle.dumps(item.value, 2)})
            item.dirty = False

class Settings:
    """供各个模块存储用户使用偏好，比如窗口大小，显示的字段等数据。
    与QSettings类似，数据被抽象成文件夹
    在使用前需要使用beginGroup与endGroup来定位文件夹，然后才能读取数据
    所有的数据存储在数据库中。使用方法如：
        >>> settings = Settings()
        <user.services.Settings instance at 0x...>
        >>> settings.beginGroup("/appearance")
        >>> settings.value("style", "plastique")
        'phase'
        >>> settings.endGroup()
    """
    def __init__(self, _settings):
        "_Settings读取/保存用户配置。而Settings类则提供了类似于QSettings的访问界面"
        self._settings = _settings
        self.prefix = []

    def duplicate(self):
        """创建一个新的Settings对象，不包含当前Settings的任何状态。方便没有userService时使用
        使用场景参见im.chat.ChatWindowController.loadSettings()"""
        return Settings(self._settings)

    def sync(self):
        self._settings.save()

    def beginGroup(self, groupName):
        """定位到某个路径，接下来的读取与存储操作都定位于这个路径。
        groupName可以是绝对路径也可以是相对路径。默认的路径是'/'。"""
        if groupName.startswith("/"):
            self.prefix = [groupName[1:]]
        else:
            self.prefix.append(groupName)

    def endGroup(self):
        assert len(self.prefix) > 0
        self.prefix.pop()

    def _prefix(self):
        "返回当前路径的全路径名"
        return "/" + "".join([groupName + "/" for groupName in self.prefix])

    def keys(self):
        prefix = self._prefix()
        return self._settings.getPreferenceKeysWithPrefix(prefix)

    def setValue(self, k, v):
        key = self._prefix() + k
        self._settings.setPreference(key, v)

    def value(self, k, default = None):
        try:
            key = self._prefix() + k
            return self._settings.getPreference(key)
        except KeyError:
            return default

    def contains(self, k):
        key = self._prefix() + k
        return self._settings.contains(key)

    def remove(self, k):
        key = self._prefix() + k
        try:
            self._settings.removePreference(key)
        except KeyError:
            return False
        else:
            return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.sync()
