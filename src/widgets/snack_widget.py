"""Food widget that spawns at a random screen position."""

from __future__ import annotations

import random
from typing import Optional, Tuple

from PyQt5.QtWidgets import QLabel, QWidget
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from utils.utils import FOODS, SNACK_SPAWN_MARGIN, screen_geometry
from utils.macos_window import pin_window_above_mission_control
import surface

FoodDef = Tuple[str, str, int, int]  # (emoji, name, hunger_restore, xp_reward)


class SnackWidget(QWidget):
    """Food widget that spawns at a random screen position."""

    def __init__(self, food_def: Optional[FoodDef] = None) -> None:
        super().__init__()
        if food_def is None:
            food_def = random.choice(FOODS)
        self.food_emoji, self.food_name, self.hunger_restore, self.xp_reward = food_def
        self._init_ui()

    def _init_ui(self) -> None:
        surface.configure(self, "snack")
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self.food_emoji, self)
        self.label.setFont(QFont("Segoe UI Emoji", 20))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.adjustSize()
        self.resize(self.label.size())

        screen = screen_geometry()
        max_x = screen.width() - self.width() - SNACK_SPAWN_MARGIN
        max_y = screen.height() - self.height() - SNACK_SPAWN_MARGIN
        x = random.randint(SNACK_SPAWN_MARGIN, max(SNACK_SPAWN_MARGIN, max_x))
        y = random.randint(SNACK_SPAWN_MARGIN, max(SNACK_SPAWN_MARGIN, max_y))
        self.move(x, y)
        self.show()
        pin_window_above_mission_control(self)
        surface.fit(self)
        surface.finish(self)
