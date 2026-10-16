"""Stats and achievements dialog."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from utils.utils import ACHIEVEMENTS, is_achievement_met

if TYPE_CHECKING:
    from core.main_controller import MainController


class StatsDialog(QDialog):
    """Shows detailed Kirby stats and achievements."""

    def __init__(
        self, controller: "MainController", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kirby Stats")
        self.setFixedSize(400, 520)
        self.setStyleSheet("background-color: #1a1a2e; color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        self._build_header(layout, controller)
        self._build_stats(layout, controller)
        self._build_achievements(layout, controller)
        layout.addStretch()

    @staticmethod
    def _build_header(layout: QVBoxLayout, ctrl: "MainController") -> None:
        title = QLabel(f"📊 {ctrl.username}'s Kirby")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FFD700; margin-bottom: 12px;")
        layout.addWidget(title)

    @staticmethod
    def _build_stats(layout: QVBoxLayout, ctrl: "MainController") -> None:
        stats = [
            f"Level: {ctrl.level}",
            f"XP: {ctrl.xp} / {ctrl.xp_for_next_level}",
            f"Size: {round(ctrl.pet.scale_factor * 100, 1)}%",
            f"Total Foods Eaten: {ctrl.total_eats}",
            f"Star Candies Eaten: {ctrl.star_eats}",
            f"Times Petted: {ctrl.total_pets}",
            f"Hunger: {ctrl.hunger}%",
            f"Mood: {ctrl.mood}",
        ]
        for s in stats:
            lbl = QLabel(s)
            lbl.setFont(QFont("Arial", 12))
            lbl.setStyleSheet("padding: 2px 0;")
            layout.addWidget(lbl)

    @staticmethod
    def _build_achievements(layout: QVBoxLayout, ctrl: "MainController") -> None:
        ach_title = QLabel("🏆 Achievements")
        ach_title.setFont(QFont("Arial", 14, QFont.Bold))
        ach_title.setStyleSheet("color: #FFD700; margin-top: 16px; margin-bottom: 4px;")
        layout.addWidget(ach_title)

        for ach in ACHIEVEMENTS:
            unlocked = is_achievement_met(
                ach,
                total_eats=ctrl.total_eats,
                level=ctrl.level,
                total_pets=ctrl.total_pets,
                star_eats=ctrl.star_eats,
            )
            icon = "✅" if unlocked else "🔒"
            color = "#90EE90" if unlocked else "#666"
            lbl = QLabel(f"{icon} {ach['name']} — {ach['desc']}")
            lbl.setFont(QFont("Arial", 10))
            lbl.setStyleSheet(f"color: {color}; padding: 1px 0;")
            layout.addWidget(lbl)
