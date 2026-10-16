"""Poop widget left behind by Kirby after eating."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QLabel, QWidget
from PyQt5.QtGui import QFont, QMouseEvent
from PyQt5.QtCore import Qt

from utils.macos_window import pin_window_above_mission_control
import surface

if TYPE_CHECKING:
    from core.main_controller import MainController


class PoopWidget(QWidget):
    """Clickable poop left behind by Kirby. Click to clean for XP."""

    def __init__(self, x: float, y: float, controller: "MainController") -> None:
        super().__init__()
        self.controller = controller
        surface.configure(self, "poop")
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel("💩", self)
        self.label.setFont(QFont("Segoe UI Emoji", 18))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.adjustSize()
        self.resize(self.label.size())
        self.move(int(x), int(y))
        self.show()
        pin_window_above_mission_control(self)
        surface.fit(self)
        surface.finish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.controller.clean_poop(self)
