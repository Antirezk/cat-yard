"""macOS menu-bar tray icon — the view layer for the Kirby controller.

``TrayPresenter`` owns the ``QSystemTrayIcon`` and rebuilds its menu from
the controller's game state, only when a hashable snapshot of that state
actually changes (so we don't churn the menu every refresh tick).
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont, QImage
from PyQt5.QtCore import Qt

from utils.utils import (
    __version__, ACHIEVEMENTS, MOOD_EMOJIS,
    TRAY_ICON_SIZE, TRAY_ICON_RETINA_SCALE, TRAY_ICON_FONT_SIZE,
)

if TYPE_CHECKING:
    from core.main_controller import MainController

_DEFAULT_MOOD_EMOJI = "😊"

_TRAY_MENU_STYLE = """
    QMenu {
        background-color: #2a2a3e;
        color: white;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 20px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #4a4a6e;
    }
    QMenu::separator {
        height: 1px;
        background: #444;
        margin: 4px 8px;
    }
"""


def make_tray_icon(text: str, size: int = TRAY_ICON_SIZE) -> QIcon:
    """Render *text* (an emoji) into a crisp retina menu-bar icon."""
    scale = TRAY_ICON_RETINA_SCALE
    img = QImage(size * scale, size * scale, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    img.setDevicePixelRatio(scale)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setFont(QFont("Apple Color Emoji", TRAY_ICON_FONT_SIZE))
    painter.drawText(0, 0, size, size, Qt.AlignCenter, text)
    painter.end()
    return QIcon(QPixmap.fromImage(img))


class TrayPresenter:
    """Owns and refreshes the menu-bar tray icon for a ``MainController``."""

    def __init__(self, controller: "MainController", app: QApplication) -> None:
        self._ctrl = controller
        self._app = app
        self._last_snapshot: Optional[tuple] = None

        self.tray = QSystemTrayIcon(app)
        self.tray.setIcon(make_tray_icon("🩷"))
        self._build_menu()
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    # --- Refresh ---

    def refresh(self) -> None:
        """Update tooltip every tick; rebuild the menu only when state changes."""
        ctrl = self._ctrl
        mood_emoji = MOOD_EMOJIS.get(ctrl.mood, _DEFAULT_MOOD_EMOJI)
        self.tray.setToolTip(
            f"Kirby Lv.{ctrl.level} | {mood_emoji} | Hunger: {ctrl.hunger}%"
        )
        snapshot = self._snapshot()
        if snapshot != self._last_snapshot:
            self._build_menu()
            self._last_snapshot = snapshot

    def _snapshot(self) -> tuple:
        """Hashable snapshot of everything the menu displays."""
        ctrl = self._ctrl
        return (
            ctrl.mood, ctrl.level, ctrl.xp, ctrl.hunger,
            round(ctrl.pet.scale_factor * 100, 1),
            ctrl.total_eats, ctrl.total_pets,
            len(ctrl.extra_pets), round(ctrl.cpu_percent),
            len(ctrl.unlocked_achievements),
        )

    # --- Menu construction ---

    def _build_menu(self) -> None:
        ctrl = self._ctrl
        menu = QMenu()
        menu.setStyleSheet(_TRAY_MENU_STYLE)

        mood_emoji = MOOD_EMOJIS.get(ctrl.mood, _DEFAULT_MOOD_EMOJI)
        self._add_info(menu, f"  {mood_emoji} {ctrl.username}'s Kirby  (v{__version__})")
        menu.addSeparator()
        self._build_stats(menu)
        menu.addSeparator()
        self._build_achievements(menu)
        menu.addSeparator()
        self._build_actions(menu)

        self.tray.setContextMenu(menu)

    def _build_stats(self, menu: QMenu) -> None:
        ctrl = self._ctrl
        stats_lines = [
            f"  Lv. {ctrl.level}   XP: {ctrl.xp}/{ctrl.xp_for_next_level}",
            f"  Hunger: {ctrl.hunger}%",
            f"  Size: {round(ctrl.pet.scale_factor * 100, 1)}%",
            f"  Foods Eaten: {ctrl.total_eats}",
            f"  Times Petted: {ctrl.total_pets}",
        ]
        if ctrl.extra_pets:
            stats_lines.append(f"  Babies: {len(ctrl.extra_pets)}")
        stats_lines.append(f"  CPU: {ctrl.cpu_percent:.0f}%")
        for line in stats_lines:
            self._add_info(menu, line)

    def _build_achievements(self, menu: QMenu) -> None:
        ctrl = self._ctrl
        total = len(ACHIEVEMENTS)
        unlocked = len(ctrl.unlocked_achievements)
        action = QAction(f"  🏆 Achievements: {unlocked}/{total}", menu)
        action.triggered.connect(ctrl.show_achievements)
        menu.addAction(action)

    def _build_actions(self, menu: QMenu) -> None:
        ctrl = self._ctrl
        actions: list[tuple[str, Callable[[], None]]] = [
            ("  🍕 Feed Kirby", ctrl.spawn_snack),
            ("  💕 Pet Kirby", ctrl.pet_kirby),
            ("  📊 Ranking Board", ctrl.show_ranking),
        ]
        for label, callback in actions:
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)

        menu.addSeparator()
        quit_action = QAction("  ❌ Quit", menu)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)

    @staticmethod
    def _add_info(menu: QMenu, text: str) -> None:
        """Add a non-interactive (disabled) informational menu row."""
        action = QAction(text, menu)
        action.setEnabled(False)
        menu.addAction(action)

    # --- Events ---

    def _on_activated(self, reason: int) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._ctrl.spawn_snack()
