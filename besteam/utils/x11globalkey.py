import ctypes
import ctypes.util
import logging
import threading
import time

from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QKeySequence

__all__ = ["GlobalKey"]

logger = logging.getLogger(__name__)


# ---- X 协议层修饰位掩码（与 xcb 数值一致） ----
ShiftMask = 1 << 0
LockMask = 1 << 1          # CapsLock
ControlMask = 1 << 2
Mod1Mask = 1 << 3          # Alt
Mod2Mask = 1 << 4          # NumLock
Mod3Mask = 1 << 5
Mod4Mask = 1 << 6          # Super / Win
Mod5Mask = 1 << 7

# 匹配时需要忽略的修饰位：NumLock / CapsLock 不应影响快捷键
_IGNORED_MASK = LockMask | Mod2Mask

KeyPress = 2  # X KeyPress 事件类型（<X11/X.h>）
KeyRelease = 3  # X KeyRelease 事件类型（<X11/X.h>）
GrabModeAsync = 1  # 指针/键盘异步抓取，不冻结输入


def _build_special_keys():
    """Qt::Key -> X11 keysym 的特殊键映射。

    ASCII 区间（0x20..0x7e）的 Qt::Key 枚举值本身就是 X11 latin-1 keysym，
    无需查表；这里只覆盖其余需要用到的特殊键。
    """
    table = {
        Qt.Key_Escape: 0xff1b,
        Qt.Key_Tab: 0xff09,
        Qt.Key_Backtab: 0xfe20,
        Qt.Key_Backspace: 0xff08,
        Qt.Key_Return: 0xff0d,
        Qt.Key_Enter: 0xff8d,
        Qt.Key_Insert: 0xff63,
        Qt.Key_Delete: 0xffff,
        Qt.Key_Home: 0xff50,
        Qt.Key_End: 0xff57,
        Qt.Key_Left: 0xff51,
        Qt.Key_Up: 0xff52,
        Qt.Key_Right: 0xff53,
        Qt.Key_Down: 0xff54,
        Qt.Key_PageUp: 0xff55,
        Qt.Key_PageDown: 0xff56,
    }
    for i in range(1, 13):
        table[getattr(Qt, "Key_F%d" % i)] = 0xffbe + (i - 1)
    return table


_SPECIAL_KEYS = _build_special_keys()

_MODIFIER_MASK = int(
    Qt.ShiftModifier
    | Qt.ControlModifier
    | Qt.AltModifier
    | Qt.MetaModifier
    | Qt.KeypadModifier
    | Qt.GroupSwitchModifier
)

# 上档符号（shift 层字符）-> 未 shift 的基础键（US 布局）。
# QKeySequence 会把 "~" 解析成独立的 Key_AsciiTilde 而不附加 Shift，
# 但物理上这些符号都打在某个基础键的 shift 层上，需还原成基础键 + ShiftMask。
_SHIFTED_KEYS = {
    0x7e: 0x60,  # ~  -> grave
    0x21: 0x31,  # !  -> 1
    0x40: 0x32,  # @  -> 2
    0x23: 0x33,  # #  -> 3
    0x24: 0x34,  # $  -> 4
    0x25: 0x35,  # %  -> 5
    0x5e: 0x36,  # ^  -> 6
    0x26: 0x37,  # &  -> 7
    0x2a: 0x38,  # *  -> 8
    0x28: 0x39,  # (  -> 9
    0x29: 0x30,  # )  -> 0
    0x5f: 0x2d,  # _  -> -
    0x2b: 0x3d,  # +  -> =
    0x7b: 0x5b,  # {  -> [
    0x7d: 0x5d,  # }  -> ]
    0x7c: 0x5c,  # |  -> backslash
    0x3a: 0x3b,  # :  -> ;
    0x22: 0x27,  # "  -> '
    0x3c: 0x2c,  # <  -> ,
    0x3e: 0x2e,  # >  -> .
    0x3f: 0x2f,  # ?  -> /
}


class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


# XEvent 是 union，64 位下占 192 字节；只按 KeyPress 读取前部字段。
class XEvent(ctypes.Structure):
    _fields_ = [("pad", ctypes.c_ubyte * 192)]


_XErrorHandlerType = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

# Xlib 错误回调没有上下文可传，只能通过模块级标志把结果带回来。
# _grab() 在持锁状态下设置/重置它，错误处理器在 XSync 期间被同步调用，
# 因此不存在跨线程竞争。
_error_seen = False


def _x_error_handler(display, event):
    global _error_seen
    _error_seen = True
    return 0


def _load_lib():
    name = ctypes.util.find_library("X11") or "libX11.so.6"
    lib = ctypes.CDLL(name)
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    lib.XCloseDisplay.restype = ctypes.c_int
    lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    lib.XDefaultRootWindow.restype = ctypes.c_ulong
    lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.XKeysymToKeycode.restype = ctypes.c_uint
    lib.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint,
                             ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.XGrabKey.restype = ctypes.c_int
    lib.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
    lib.XUngrabKey.restype = ctypes.c_int
    lib.XPending.argtypes = [ctypes.c_void_p]
    lib.XPending.restype = ctypes.c_int
    lib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(XEvent)]
    lib.XNextEvent.restype = ctypes.c_int
    lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.XSync.restype = ctypes.c_int
    lib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
    lib.XSetErrorHandler.restype = ctypes.c_void_p
    return lib


_x11 = _load_lib()
_x_error_handler_cb = _XErrorHandlerType(_x_error_handler)
_x_error_handler_ptr = ctypes.cast(_x_error_handler_cb, ctypes.c_void_p)

# 线程安全：libX11 默认非线程安全，需先 XInitThreads() 才允许并发。
# 本进程的 XInitThreads() 已由 Qt 5 xcb 平台插件在 QApplication 构造时调用，
# 故子线程可直接调 Xlib 而不崩溃。但 XInitThreads 只防数据损坏、不保证语义：
# XSetErrorHandler 是进程级全局、事件队列也非线程安全，仍需下面这把锁把
# 所有 Xlib 调用串行化，保证「换 handler→XSync→恢复」和同一 Display 的队列操作原子。
_x11_lock = threading.Lock()


def _qt_modifiers_to_x11(mods):
    native = 0
    if mods & Qt.ShiftModifier:
        native |= ShiftMask
    if mods & Qt.ControlModifier:
        native |= ControlMask
    if mods & Qt.AltModifier:
        native |= Mod1Mask
    if mods & Qt.MetaModifier:
        native |= Mod4Mask
    return native


def _qt_key_to_keysym(qt_key):
    if 0x20 <= qt_key <= 0x7e:
        return qt_key
    return _SPECIAL_KEYS.get(qt_key)


class GlobalKey(QObject):
    catched = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._display = _x11.XOpenDisplay(None)
        self._root = None
        self._thread = None
        self._running = False
        self._next_id = 0
        self._keys = {}  # keyId -> (keycode, base_mods)
        self._pressed = set()  # 已按下且已触发的 keycode，用于去抖 auto-repeat
        if not self._display:
            logger.warning("cannot open X11 display, global key disabled")
            return
        self._root = _x11.XDefaultRootWindow(self._display)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self._running:
            hit = None
            with _x11_lock:
                while _x11.XPending(self._display) > 0:
                    event = XEvent()
                    if _x11.XNextEvent(self._display, ctypes.byref(event)) != 0:
                        break
                    key = ctypes.cast(ctypes.byref(event), ctypes.POINTER(XKeyEvent)).contents
                    if key.type == KeyPress:
                        # XGrabKey 在键按住时会因 auto-repeat 持续收到 KeyPress，
                        # 已按下的 keycode 直接跳过，只在边沿触发一次。
                        if key.keycode in self._pressed:
                            continue
                        hit = self._find_match(key.state, key.keycode)
                        if hit is not None:
                            self._pressed.add(key.keycode)
                            break
                    elif key.type == KeyRelease:
                        self._pressed.discard(key.keycode)
            if hit is not None:
                self.catched.emit(hit)
            time.sleep(0.005)

    def _find_match(self, state, keycode):
        """在已登记的快捷键里找命中的 keyId，未命中返回 None。"""
        state &= ~_IGNORED_MASK
        for key_id, (kc, mods) in self._keys.items():
            if kc == keycode and state == mods:
                return key_id
        return None

    def _variants(self, mods):
        return [mods, mods | LockMask, mods | Mod2Mask, mods | LockMask | Mod2Mask]

    def _grab(self, keycode, mods):
        """grab 一个键的 4 个 NumLock/CapsLock 变体。

        调用者必须持有 _x11_lock：XSetErrorHandler 是进程级全局，
        必须与其它 Xlib 调用串行化。
        """
        global _error_seen
        variants = self._variants(mods)
        for v in variants:
            _error_seen = False
            prev = _x11.XSetErrorHandler(_x_error_handler_ptr)
            try:
                _x11.XGrabKey(self._display, keycode, v, self._root,
                              True, GrabModeAsync, GrabModeAsync)
                _x11.XSync(self._display, False)
            finally:
                _x11.XSetErrorHandler(prev)
            if _error_seen:
                self._ungrab(keycode, variants)
                return False
        return True

    def _ungrab(self, keycode, variants):
        """释放 keycode 的若干修饰位变体。调用者必须持有 _x11_lock。"""
        for v in variants:
            _x11.XUngrabKey(self._display, keycode, v, self._root)
        _x11.XSync(self._display, False)

    def addHotKey(self, name, key):
        if not self._display:
            self._next_id += 1
            return self._next_id - 1

        if isinstance(key, QKeySequence):
            seq = key
        else:
            seq = QKeySequence(key)
        try:
            combo = seq[0]
        except IndexError:
            return -1

        qt_mods = combo & _MODIFIER_MASK
        qt_key = combo & ~_MODIFIER_MASK

        if qt_key in _SHIFTED_KEYS:
            keysym = _SHIFTED_KEYS[qt_key]
            qt_mods |= Qt.ShiftModifier
        else:
            keysym = _qt_key_to_keysym(qt_key)

        if keysym is None:
            logger.warning("unsupported key: %r", key)
            return -1

        with _x11_lock:
            keycode = _x11.XKeysymToKeycode(self._display, keysym)
            if not keycode:
                logger.warning("cannot resolve keycode for %r", key)
                return -1
            mods = _qt_modifiers_to_x11(qt_mods)
            if (keycode, mods) in self._keys.values():
                logger.warning("duplicate global key %r", key)
                return -1
            if not self._grab(keycode, mods):
                logger.warning("failed to grab global key %r", key)
                return -1
            self._keys[self._next_id] = (keycode, mods)
            self._next_id += 1
            return self._next_id - 1

    def removeHotKey(self, key_id):
        if not self._display:
            return
        with _x11_lock:
            # self._keys 的读写必须与 _run 线程里 _find_match 的遍历
            # 一样受锁保护，否则字典在迭代中被改会抛 RuntimeError。
            if key_id not in self._keys:
                return
            keycode, mods = self._keys.pop(key_id)
            self._ungrab(keycode, self._variants(mods))

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._display is None:
            return
        with _x11_lock:
            # 这里不调用 removeHotKey：threading.Lock 不可重入，
            # 在已持锁的情况下再进 removeHotKey 会死锁，故内联清理逻辑。
            for key_id in list(self._keys.keys()):
                keycode, mods = self._keys[key_id]
                self._ungrab(keycode, self._variants(mods))
            self._keys.clear()
            _x11.XCloseDisplay(self._display)
        self._display = None
