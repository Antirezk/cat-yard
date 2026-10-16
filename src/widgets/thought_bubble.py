"""Floating thought bubble that follows Kirby and shows text."""

from __future__ import annotations

from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QPainterPath, QPaintEvent
from PyQt5.QtCore import Qt, QTimer, QRectF

from utils.macos_window import pin_window_above_mission_control
import surface
from utils.utils import FADE_TICK_MS, screen_geometry

_OPACITY_THRESHOLD = 0.01
_FADE_RATE = 0.15

# Bubble geometry (presentation only).
_BUBBLE_WIDTH = 160
_BUBBLE_HEIGHT = 60
_FOLLOW_DX = 20  # horizontal offset from Kirby's top-left
_FOLLOW_DY = 65  # sit this far above Kirby


class ThoughtBubble(QWidget):
    """A floating thought bubble that follows Kirby and shows his mood."""

    def __init__(self) -> None:
        super().__init__()
        surface.configure(self, "bubble")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.resize(_BUBBLE_WIDTH, _BUBBLE_HEIGHT)
        self._text = ""
        self._opacity = 0.0
        self._target_opacity = 0.0

        # Built once and reused every paint.
        self._font = QFont("Arial", 11)
        self._font.setBold(True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fade_tick)
        self._timer.start(FADE_TICK_MS)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)

        self._screen = screen_geometry()
        self.show()
        pin_window_above_mission_control(self)
        surface.fit(self)
        surface.finish(self)

    def stop(self) -> None:
        """Stop all timers for clean shutdown."""
        self._timer.stop()
        self._hide_timer.stop()

    def show_text(self, text: str, duration_ms: int = 3000) -> None:
        from language import thought
        self._text = thought(text)
        self._target_opacity = 1.0
        self._hide_timer.stop()
        self._hide_timer.start(duration_ms)
        self.update()

    def fade_out(self) -> None:
        self._target_opacity = 0.0

    def follow(self, x: int, y: int) -> None:
        """Follow Kirby, clamped to screen bounds."""
        bx = max(0, min(x - _FOLLOW_DX, self._screen.width() - self.width()))
        by = max(0, min(y - _FOLLOW_DY, self._screen.height() - self.height()))
        self.move(int(bx), int(by))

    def _fade_tick(self) -> None:
        diff = self._target_opacity - self._opacity
        if abs(diff) > _OPACITY_THRESHOLD:
            self._opacity += diff * _FADE_RATE
            self.update()
        elif diff != 0:
            self._opacity = self._target_opacity
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._opacity < _OPACITY_THRESHOLD:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._opacity)

        # Bubble body
        path = QPainterPath()
        bubble_rect = QRectF(5, 5, self.width() - 10, self.height() - 20)
        path.addRoundedRect(bubble_rect, 12, 12)
        painter.fillPath(path, QColor(255, 255, 255, 220))
        painter.setPen(QColor(180, 180, 180))
        painter.drawPath(path)

        # Small circles for tail
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawEllipse(25, self.height() - 18, 10, 10)
        painter.drawEllipse(20, self.height() - 8, 6, 6)

        # Text
        painter.setPen(QColor(60, 60, 60))
        painter.setFont(self._font)
        painter.drawText(bubble_rect, Qt.AlignCenter | Qt.TextWordWrap, self._text)
