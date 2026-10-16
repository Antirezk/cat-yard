"""Hold-to-play global feather cursor, with release and crash recovery."""
import atexit
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QCursor

def user32():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.LoadImageW.restype = wintypes.HANDLE
    user.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user.LoadCursorW.restype = wintypes.HANDLE
    user.CopyIcon.argtypes = [wintypes.HANDLE]; user.CopyIcon.restype = wintypes.HANDLE
    user.SetSystemCursor.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    user.DestroyCursor.argtypes = [wintypes.HANDLE]
    user.GetAsyncKeyState.argtypes = [ctypes.c_int]; user.GetAsyncKeyState.restype = ctypes.c_short
    return user

def paint_feather(painter):
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor('#75543c'), 3, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(42, 47), QPointF(26, 25))
    painter.setPen(QPen(QColor('#dfb484'), 1, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(43, 46), QPointF(27, 25))
    painter.setPen(QPen(QColor('#a99074'), 1))
    path = QPainterPath(QPointF(27, 25)); path.cubicTo(13, 36, 26, 13, 13, 13)
    painter.drawPath(path)
    for angle, color in [(-30, '#659b8c'), (0, '#d59662'), (28, '#8caab4')]:
        painter.save(); painter.translate(14, 14); painter.rotate(angle)
        feather = QPainterPath(QPointF(0, 5)); feather.cubicTo(-12, 5, -9, -9, -2, -11)
        feather.cubicTo(4, -6, 6, 2, 0, 5)
        painter.setBrush(QColor(color)); painter.setPen(QPen(QColor(color).darker(120), .7)); painter.drawPath(feather)
        painter.setPen(QPen(QColor('#f7eee0'), .65)); painter.drawLine(QPointF(0, 4), QPointF(-2, -8))
        for i in range(3):
            painter.drawLine(QPointF(-1, 1 - i * 2), QPointF(-6 + i, -i * 2))
        painter.restore()

def write_cursor(path):
    size = 48
    image = QImage(size, size, QImage.Format_ARGB32); image.fill(Qt.transparent)
    painter = QPainter(image); paint_feather(painter); painter.end()
    # Uncompressed 32-bit DIB plus AND transparency mask, supported by Windows cursors.
    color_rows, mask_rows = [], []
    for y in reversed(range(size)):
        row = bytearray(); mask = bytearray(8)
        for x in range(size):
            c = image.pixelColor(x, y)
            row.extend((c.blue(), c.green(), c.red(), c.alpha()))
            if c.alpha() < 8: mask[x // 8] |= 0x80 >> (x % 8)
        color_rows.append(bytes(row)); mask_rows.append(bytes(mask))
    dib = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    payload = dib + b''.join(color_rows) + b''.join(mask_rows)
    header = struct.pack('<HHH', 0, 2, 1) + struct.pack('<BBBBHHII', size, size, 0, 0, 14, 14, len(payload), 22)
    path.write_bytes(header + payload)

def guard_loop(pid, marker):
    """An independent helper resets themed cursors if its owning app crashes."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, int(pid))
    if handle:
        kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
        kernel.CloseHandle(handle)
    marker = Path(marker)
    if marker.exists():
        user32().SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS: restore current user theme
        marker.unlink(missing_ok=True)

class Wand:
    def __init__(self, app, root):
        self.active = False
        self.point = QCursor.pos()
        self.user = user32()
        self.root = Path(root)
        self.marker = self.root / f'cursor-active-{os.getpid()}.flag'
        self.cursor_file = self.root / 'feather.cur'
        self.guard = None
        self.originals = {}
        self.enabled = True
        self.override = None
        self._closed = False
        self.timer = QTimer(app); self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.poll); self.timer.start(16)
        atexit.register(self.close)
        app.aboutToQuit.connect(self.close)

    def _start_guard(self):
        if self.guard and self.guard.poll() is None: return
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command += [str(Path(__file__).resolve()), str(os.getpid()), str(self.marker)]
        else:
            command += ['--cursor-guard', str(os.getpid()), str(self.marker)]
        self.guard = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)

    def activate(self):
        if self.active: return
        write_cursor(self.cursor_file)
        self._start_guard()
        self.marker.write_text('active', encoding='ascii')
        for cursor_id in (32512, 32513, 32515, 32649):
            original = self.user.CopyIcon(self.user.LoadCursorW(None, ctypes.c_void_p(cursor_id)))
            if not original: raise ctypes.WinError(ctypes.get_last_error())
            self.originals[cursor_id] = original
            replacement = self.user.LoadImageW(None, str(self.cursor_file), 2, 0, 0, 0x10)
            if not replacement: raise ctypes.WinError(ctypes.get_last_error())
            if not self.user.SetSystemCursor(replacement, cursor_id):
                self.user.DestroyCursor(replacement)
                self.restore()
                raise ctypes.WinError(ctypes.get_last_error())
        self.active = True

    def restore(self):
        if self.originals:
            failed = False
            for cursor_id, original in self.originals.items():
                if not self.user.SetSystemCursor(original, cursor_id): failed = True
            if failed: self.user.SystemParametersInfoW(0x0057, 0, None, 0)
            self.originals.clear()
        elif self.active:
            self.user.SystemParametersInfoW(0x0057, 0, None, 0)
        self.marker.unlink(missing_ok=True)
        self.active = False

    def poll(self):
        self.point = QCursor.pos()
        held = bool(self.user.GetAsyncKeyState(0x11) & 0x8000 and self.user.GetAsyncKeyState(0x12) & 0x8000)
        if self.override is not None:
            held, self.point = self.override
        held = held and self.enabled
        try:
            if held and not self.active: self.activate()
            elif not held and self.active: self.restore()
        except Exception:
            logging.exception('Could not enable feather cursor')
            self.restore()
            self.enabled = False

    def close(self):
        if self._closed: return
        self._closed = True
        self.timer.stop()
        self.restore()

current = None

if __name__ == '__main__':
    guard_loop(sys.argv[1], sys.argv[2])
