import dbus
from dbus.mainloop.glib import DBusGMainLoop
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QKeySequence
import sys

class GlobalKey(QObject):
    catched = pyqtSignal(int)

    def __init__(self):
        print("DEBUG: GlobalKey.__init__() called", file=sys.stderr)
        super().__init__()
        self.nextId = 0
        self.shortcuts = {}  # 存储快捷键信息: {id: (component_name, action_name)}
        self.component_name = "quickpanel"  # 组件名称

        # 初始化 D-Bus
        print("DEBUG: Initializing D-Bus with DBusGMainLoop", file=sys.stderr)
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        self.kglobalaccel = None
        self.monitoring = False

        try:
            print("DEBUG: Connecting to KDE global accelerator service", file=sys.stderr)
            self.kglobalaccel = self.bus.get_object('org.kde.kglobalaccel',
                                                   '/kglobalaccel')
            print(f"DEBUG: Got kglobalaccel object: {self.kglobalaccel}", file=sys.stderr)
            self.kglobalaccel_interface = dbus.Interface(self.kglobalaccel,
                                                        'org.kde.KGlobalAccel')
            print("DEBUG: Created kglobalaccel interface", file=sys.stderr)
            # 连接到激活信号
            print("DEBUG: Adding signal receiver for shortcut activation", file=sys.stderr)
            # 尝试监听可能的信号
            try:
                self.bus.add_signal_receiver(self._on_shortcut_activated,
                                           signal_name='invokeAction',
                                           dbus_interface='org.kde.kglobalaccel',
                                           bus_name='org.kde.kglobalaccel',
                                           path='/kglobalaccel')
                print("DEBUG: Added invokeAction signal receiver", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Failed to add invokeAction signal receiver: {e}", file=sys.stderr)

            # 也尝试监听 yourShortcutsChanged 信号
            try:
                self.bus.add_signal_receiver(self._on_shortcuts_changed,
                                           signal_name='yourShortcutsChanged',
                                           dbus_interface='org.kde.KGlobalAccel',
                                           bus_name='org.kde.kglobalaccel',
                                           path='/kglobalaccel')
                print("DEBUG: Added yourShortcutsChanged signal receiver", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Failed to add yourShortcutsChanged signal receiver: {e}", file=sys.stderr)
            print("DEBUG: KDE global accelerator service initialized successfully", file=sys.stderr)
        except dbus.exceptions.DBusException as e:
            # KDE 全局快捷键服务不可用
            print(f"DEBUG: KDE global accelerator service not available: {e}", file=sys.stderr)
            self.kglobalaccel = None

    def close(self):
        print(f"DEBUG: GlobalKey.close() called, {len(self.shortcuts)} shortcuts to clean up", file=sys.stderr)
        self.monitoring = False
        # 这里需要使用 list(self.shortcuts.keys()) 来避免在迭代过程中修改字典
        for keyId in list(self.shortcuts.keys()):
            self.removeHotKey(keyId)
        self.shortcuts.clear()
        print("DEBUG: GlobalKey.close() completed", file=sys.stderr)

    def addHotKey(self, name, key):
        print(f"DEBUG: addHotKey called with name='{name}', key='{key}'", file=sys.stderr)
        if not self.kglobalaccel:
            # 如果没有 KDE 全局快捷键服务，返回虚拟 ID
            print("DEBUG: KDE global accelerator not available, returning virtual ID", file=sys.stderr)
            t = self.nextId
            self.nextId += 1
            return t

        # 转换快捷键格式
        key_int = self._key_to_int(key)
        print(f"DEBUG: Converted key '{key}' to int: {key_int}", file=sys.stderr)
        if key_int is None:
            print(f"DEBUG: Failed to convert key '{key}' to int, returning virtual ID", file=sys.stderr)
            t = self.nextId
            self.nextId += 1
            return t

        action_id = [self.component_name, f"quickpanel_{name}_{self.nextId}"]
        print(f"DEBUG: Created action_id: {action_id}", file=sys.stderr)

        # 检查快捷键是否可用
        try:
            available = self.kglobalaccel_interface.isGlobalShortcutAvailable(key_int, self.component_name)
            print(f"DEBUG: isGlobalShortcutAvailable({key_int}, {self.component_name}) = {available}", file=sys.stderr)
            if not available:
                # 获取当前使用此快捷键的操作
                actions = self.kglobalaccel_interface.getGlobalShortcutsByKey(key_int)
                print(f"DEBUG: getGlobalShortcutsByKey({key_int}) returned: {actions}", file=sys.stderr)
                if actions:
                    # 注意：KDE 可能没有直接的 stealShortcutSystemwide 方法
                    # 在这种情况下，我们跳过窃取步骤
                    print("DEBUG: Shortcut not available but conflicts found, skipping steal step", file=sys.stderr)
                    pass
        except dbus.exceptions.DBusException as e:
            # D-Bus 调用失败，继续尝试注册
            print(f"DEBUG: D-Bus call failed when checking availability: {e}", file=sys.stderr)
            pass

        # 注册快捷键
        try:
            # 首先尝试使用 setForeignShortcut (为外部应用设计)
            print(f"DEBUG: Trying setForeignShortcut with action='{action_id[1]}', keys=[{key_int}]", file=sys.stderr)
            try:
                self.kglobalaccel_interface.setForeignShortcut(action_id[1], [key_int])
                print("DEBUG: setForeignShortcut succeeded", file=sys.stderr)
            except dbus.exceptions.DBusException as e:
                print(f"DEBUG: setForeignShortcut failed: {e}, trying setShortcut", file=sys.stderr)
                # 如果 setForeignShortcut 失败，尝试 setShortcut
                result = self.kglobalaccel_interface.setShortcut(action_id,  # [component, action]
                                                               [key_int],   # 快捷键列表
                                                               0)           # flags
                print(f"DEBUG: setShortcut returned: {result}", file=sys.stderr)
                if not result:
                    print("DEBUG: setShortcut returned empty array - registration may have failed", file=sys.stderr)
            self.shortcuts[self.nextId] = (action_id, key_int)
            print(f"DEBUG: Stored shortcut in self.shortcuts[{self.nextId}]", file=sys.stderr)
            self.nextId += 1
            return self.nextId - 1
        except dbus.exceptions.DBusException as e:
            # 注册失败，返回虚拟 ID
            print(f"DEBUG: Failed to register shortcut: {e}", file=sys.stderr)
            self.nextId += 1
            return self.nextId - 1

    def removeHotKey(self, keyId):
        print(f"DEBUG: removeHotKey called with keyId={keyId}", file=sys.stderr)
        if keyId not in self.shortcuts:
            print(f"DEBUG: keyId {keyId} not found in shortcuts", file=sys.stderr)
            return

        if self.kglobalaccel:
            action_id, key_int = self.shortcuts[keyId]
            print(f"DEBUG: Removing shortcut with action_id={action_id}, key_int={key_int}", file=sys.stderr)
            try:
                # 尝试使用 setForeignShortcut 移除
                self.kglobalaccel_interface.setForeignShortcut(action_id[1], [])
                print("DEBUG: setForeignShortcut removal succeeded", file=sys.stderr)
            except dbus.exceptions.DBusException as e:
                print(f"DEBUG: setForeignShortcut removal failed: {e}, trying setShortcut", file=sys.stderr)
                try:
                    # 如果 setForeignShortcut 失败，尝试 setShortcut
                    result = self.kglobalaccel_interface.setShortcut(action_id,  # [component, action]
                                                           [],          # 移除所有快捷键
                                                           0)           # flags
                    print(f"DEBUG: setShortcut removal returned: {result}", file=sys.stderr)
                except dbus.exceptions.DBusException as e2:
                    print(f"DEBUG: Failed to remove shortcut with setShortcut: {e2}", file=sys.stderr)
                    pass

        del self.shortcuts[keyId]
        print(f"DEBUG: Removed keyId {keyId} from shortcuts", file=sys.stderr)

    def _on_shortcut_activated(self, component, action, timestamp):
        """处理快捷键激活信号"""
        print(f"DEBUG: _on_shortcut_activated called with component='{component}', action='{action}', timestamp={timestamp}", file=sys.stderr)
        if component != self.component_name:
            print(f"DEBUG: Component '{component}' != '{self.component_name}', ignoring", file=sys.stderr)
            return

        # 查找对应的 keyId
        for keyId, (action_id, key_int) in self.shortcuts.items():
            print(f"DEBUG: Checking shortcut {keyId}: action_id={action_id}, key_int={key_int}", file=sys.stderr)
            if len(action_id) >= 2 and action_id[1] == action:
                print(f"DEBUG: Found matching shortcut {keyId}, emitting catched signal", file=sys.stderr)
                self.catched.emit(keyId)
                break
        else:
            print(f"DEBUG: No matching shortcut found for action '{action}'", file=sys.stderr)

    def _on_shortcuts_changed(self, action_id, keys):
        """处理快捷键变更信号"""
        print(f"DEBUG: _on_shortcuts_changed called with action_id={action_id}, keys={keys}", file=sys.stderr)
        # 这个信号可能在快捷键被激活时也会发送
        # 我们可以检查 action_id 是否匹配我们的快捷键
        if isinstance(action_id, list) and len(action_id) >= 2:
            component, action = action_id[0], action_id[1]
            if component == self.component_name:
                print(f"DEBUG: Shortcuts changed for our component: {component}, action: {action}", file=sys.stderr)
                # 查找对应的 keyId
                for keyId, (stored_action_id, key_int) in self.shortcuts.items():
                    if stored_action_id == action_id:
                        print(f"DEBUG: Found matching shortcut {keyId}, this might indicate activation", file=sys.stderr)
                        # 注意：这个信号不一定表示激活，可能只是变更
                        break

    def _key_to_int(self, key):
        """将 PyQt5 QKeySequence 转换为 KDE 使用的整数格式"""
        print(f"DEBUG: _key_to_int called with key='{key}' (type: {type(key)})", file=sys.stderr)
        # 如果 key 已经是整数，直接返回
        if isinstance(key, int):
            print(f"DEBUG: Key is already an int: {key}", file=sys.stderr)
            return key

        # 如果 key 是字符串，尝试转换为 QKeySequence 然后获取整数值
        try:
            if isinstance(key, str):
                print(f"DEBUG: Converting string key '{key}' to QKeySequence", file=sys.stderr)
                seq = QKeySequence(key)
                result = seq[0]
                print(f"DEBUG: QKeySequence('{key}')[0] = {result}", file=sys.stderr)
                return result
            elif isinstance(key, QKeySequence):
                result = key[0]
                print(f"DEBUG: QKeySequence[0] = {result}", file=sys.stderr)
                return result
        except (ImportError, IndexError) as e:
            print(f"DEBUG: Failed to convert key: {e}", file=sys.stderr)
            pass

        # 如果无法转换，返回 None
        print(f"DEBUG: Unable to convert key '{key}' to int, returning None", file=sys.stderr)
        return None
