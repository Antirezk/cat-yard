"""Shared play surface: Qt child arena, Explorer desktop, or floating overlay."""
import ctypes
import sys
import weakref
from ctypes import wintypes
from PyQt5.QtCore import Qt, QPointF, QRect
from PyQt5.QtWidgets import QApplication

arena = None
mode = 'window'
widgets = weakref.WeakKeyDictionary()

def unregister(widget):
    widgets.pop(widget, None)

def bounds():
    if mode == 'window' and arena is not None:
        return arena.rect()
    screen = QApplication.primaryScreen()
    # Overlay coordinates use the primary screen's available local area.
    return QRect(0, 0, screen.availableGeometry().width(), screen.availableGeometry().height()) if screen else QRect(0, 0, 800, 600)

def _api():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowExW.restype = wintypes.HWND
    user.GetParent.argtypes = [wintypes.HWND]
    user.GetParent.restype = wintypes.HWND
    user.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user.SetParent.restype = wintypes.HWND
    user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    return user

def desktop_host():
    if sys.platform != 'win32':
        return None
    user = _api()
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    @callback_type
    def callback(hwnd, _):
        if user.FindWindowExW(hwnd, 0, 'SHELLDLL_DefView', None):
            found.append(hwnd)
        return True
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows(callback, 0)
    return found[0] if found else None

def _detach(widget):
    if getattr(widget, '_desktop_attached', False):
        user = _api()
        hwnd = int(widget.winId())
        user.SetParent(hwnd, 0)
        style = user.GetWindowLongPtrW(hwnd, -16)
        user.SetWindowLongPtrW(hwnd, -16, (style & ~0x40000000) | 0x80000000)
        widget._desktop_attached = False

def _attach(widget):
    host = desktop_host()
    if not host:
        raise RuntimeError('Windows Explorer desktop was not found.')
    user = _api()
    hwnd = int(widget.winId())
    style = user.GetWindowLongPtrW(hwnd, -16)
    user.SetWindowLongPtrW(hwnd, -16, (style & ~0x80000000) | 0x40000000)
    ctypes.set_last_error(0)
    user.SetParent(hwnd, host)
    if user.GetParent(hwnd) != host:
        user.SetWindowLongPtrW(hwnd, -16, style)
        raise ctypes.WinError(ctypes.get_last_error())
    widget._desktop_attached = True
    user.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0010 | 0x0001 | 0x0002 | 0x0020)

def configure(widget, role):
    widgets[widget] = role
    _detach(widget)
    passive = role in ('particles', 'bubble')
    if mode == 'window' and arena is not None:
        widget.setParent(arena)
        widget.setWindowFlags(Qt.Widget)
    else:
        widget.setParent(None)
        flags = Qt.Tool | Qt.FramelessWindowHint
        if mode == 'top':
            flags |= Qt.WindowStaysOnTopHint
        if passive:
            flags |= Qt.WindowTransparentForInput
        widget.setWindowFlags(flags)

def finish(widget):
    if mode == 'desktop':
        _attach(widget)

def fit(widget):
    role = widgets[widget]
    rect = bounds()
    if role == 'particles':
        widget.setGeometry(rect)
        widget.lower()
        return
    x = max(0, min(widget.x(), rect.width() - widget.width()))
    y = max(0, min(widget.y(), rect.height() - widget.height()))
    widget.move(x, y)
    if role == 'pet':
        widget.apply_scale()
        widget._screen_width, widget._screen_height = rect.width(), rect.height()
        widget.pos_f = QPointF(x, y)
    if role == 'bubble':
        widget._screen = rect

def switch(new_mode):
    global mode
    if new_mode == 'desktop' and not desktop_host():
        raise RuntimeError('Windows Explorer desktop was not found.')
    mode = new_mode
    for widget, role in list(widgets.items()):
        widget.hide()
        configure(widget, role)
        fit(widget)
        widget.show()
        finish(widget)
    # Keep effects above the arena background but below clickable sprites.
    for widget, role in list(widgets.items()):
        if role == 'bubble':
            widget.raise_()

def resize_arena():
    if mode == 'window':
        for widget in list(widgets):
            fit(widget)
