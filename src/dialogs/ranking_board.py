"""Ranking board dialog with auto-refresh."""

from __future__ import annotations

from typing import Any, Optional

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget
from PyQt5.QtGui import QFont, QColor, QPainter, QLinearGradient, QPaintEvent
from PyQt5.QtCore import Qt, QTimer, QRectF

from utils.utils import (
    RANKING_FILE, RANKING_WINDOW_SIZE, RANKING_REFRESH_MS,
    RANKING_ROW_HEIGHT, load_json_safe,
)


def _entry_level(entry: dict) -> float:
    """Return an entry's level as a number, treating bad values as 0."""
    level = entry.get("level", 0)
    return level if isinstance(level, (int, float)) else 0


class RankingBoard(QDialog):
    """Styled ranking board with auto-refresh."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ranking Board")
        self.setFixedSize(*RANKING_WINDOW_SIZE)
        self.setStyleSheet("background-color: #1a1a2e; color: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🏆 Kirby Rankings")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FFD700; margin-bottom: 8px;")
        layout.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(6)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

        self._last_data: Optional[list] = None  # avoid rebuilding if unchanged
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(RANKING_REFRESH_MS)

    def _refresh(self) -> None:
        ranking = load_json_safe(RANKING_FILE, default=[])
        if not isinstance(ranking, list):
            ranking = []
        # Tolerate a hand-edited or corrupt file: drop non-dict rows and
        # sort by a coerced numeric level so a null level can't raise.
        ranking = [e for e in ranking if isinstance(e, dict)]
        ranking.sort(key=_entry_level, reverse=True)

        # Skip rebuild if data hasn't changed
        if ranking == self._last_data:
            return
        self._last_data = ranking

        # Clear existing
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not ranking:
            empty = QLabel("No ranking data yet.\nStart playing!")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #888; font-size: 14px; padding: 40px;")
            self._content_layout.addWidget(empty)
            return

        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(ranking):
            medal = medals[i] if i < 3 else f"#{i + 1}"
            name = entry.get("username", "Unknown")
            level = entry.get("level", 0)
            size = entry.get("size", 100)
            row = RankingRow(medal, name, level, size)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch()


class RankingRow(QWidget):
    """Single row in the ranking board."""

    def __init__(self, rank: str, name: str, level: Any, size: Any) -> None:
        super().__init__()
        self._rank = rank
        self._name = name
        self._level = level
        self._size = size
        self.setFixedHeight(RANKING_ROW_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(40, 40, 70, 180))
        gradient.setColorAt(1, QColor(60, 40, 90, 140))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

        painter.setPen(QColor(255, 255, 255, 220))
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(10, 0, 40, self.height(), Qt.AlignVCenter, str(self._rank))

        font.setBold(False)
        painter.setFont(font)
        painter.drawText(55, 0, 160, self.height(), Qt.AlignVCenter, self._name)

        painter.setPen(QColor(100, 255, 150))
        painter.drawText(220, 0, 80, self.height(), Qt.AlignVCenter, f"Lv.{self._level}")

        painter.setPen(QColor(255, 200, 100))
        painter.drawText(310, 0, 80, self.height(), Qt.AlignVCenter, f"{self._size}%")
