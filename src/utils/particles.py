"""Full-screen transparent particle overlay for visual effects."""

from __future__ import annotations

import math
import random

from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QPaintEvent
from PyQt5.QtCore import Qt, QTimer, QPointF

from utils.macos_window import pin_window_above_mission_control
import surface
from utils.utils import (
    PARTICLE_GRAVITY, PARTICLE_DECAY_RANGE, PARTICLE_TICK_MS, MAX_PARTICLES,
    PARTICLE_SPEED_RANGE, PARTICLE_UPWARD_BOOST, PARTICLE_MIN_LIFE,
    screen_geometry,
)


class Particle:
    """A single animated character that floats, falls, and fades."""

    __slots__ = ("pos", "vel", "char", "color", "size", "life", "decay")

    def __init__(self, x: float, y: float, char: str, color: QColor, size: int = 14) -> None:
        self.pos = QPointF(x, y)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(*PARTICLE_SPEED_RANGE)
        self.vel = QPointF(
            math.cos(angle) * speed,
            math.sin(angle) * speed - PARTICLE_UPWARD_BOOST,
        )
        self.char = char
        self.color = color
        self.size = size
        self.life = 1.0
        self.decay = random.uniform(*PARTICLE_DECAY_RANGE)

    def update(self) -> bool:
        """Advance one frame. Returns ``True`` while the particle is alive."""
        self.pos += self.vel
        self.vel.setY(self.vel.y() + PARTICLE_GRAVITY)
        self.life -= self.decay
        return self.life > PARTICLE_MIN_LIFE


class ParticleOverlay(QWidget):
    """Full-screen transparent overlay that renders particles."""

    # Preset definitions: (chars, colors, count, size_range)
    _PRESETS = {
        "eat": {
            "chars": ["★", "✦", "✧", "⭐", "+XP"],
            "colors": [
                QColor(255, 215, 0),
                QColor(255, 165, 0),
                QColor(255, 255, 100),
                QColor(255, 200, 50),
            ],
            "count": 8,
            "size_range": (12, 20),
        },
        "heart": {
            "chars": ["♥"],
            "colors": None,  # generated randomly
            "count": 5,
            "size_range": (14, 22),
        },
        "achievement": {
            "chars": ["🏆", "⭐", "✨", "🎉"],
            "colors": [QColor(255, 215, 0)],
            "count": 12,
            "size_range": (16, 26),
        },
        "angry": {
            "chars": ["💢", "!", "⚡"],
            "colors": [QColor(230, 60, 60), QColor(255, 120, 40), QColor(255, 210, 60)],
            "count": 3,
            "size_range": (14, 22),
        },
        "level_up": {
            "chars": ["▲", "UP!", "★", "LV"],
            "colors": [QColor(0, 255, 100), QColor(100, 255, 200), QColor(255, 255, 0)],
            "count": 10,
            "size_range": (14, 22),
        },
    }

    def __init__(self) -> None:
        super().__init__()
        surface.configure(self, "particles")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        screen = screen_geometry()
        self.setGeometry(screen)
        self._particles: list[Particle] = []

        # Reusable paint objects — avoid per-particle, per-frame allocation.
        self._font_cache: dict[int, QFont] = {}
        self._scratch_color = QColor()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(PARTICLE_TICK_MS)
        self.show()
        pin_window_above_mission_control(self)
        surface.fit(self)
        surface.finish(self)

    # --- Public emitters ---

    def _can_emit(self, count: int = 1) -> bool:
        """Check if we can add more particles without exceeding the cap."""
        return len(self._particles) + count <= MAX_PARTICLES

    def emit_preset(self, name: str, x: float, y: float) -> None:
        """Emit particles from a named preset."""
        preset = self._PRESETS[name]
        if not self._can_emit(preset["count"]):
            return
        for _ in range(preset["count"]):
            char = random.choice(preset["chars"])
            if preset["colors"] is None:
                color = QColor(
                    random.randint(200, 255),
                    random.randint(50, 120),
                    random.randint(100, 180),
                )
            else:
                color = random.choice(preset["colors"])
            size = random.randint(*preset["size_range"])
            self._particles.append(Particle(x, y, char, color, size))

    def emit_eat(self, x: float, y: float) -> None:
        self.emit_preset("eat", x, y)

    def emit_heart(self, x: float, y: float) -> None:
        self.emit_preset("heart", x, y)

    def emit_achievement(self, x: float, y: float) -> None:
        self.emit_preset("achievement", x, y)

    def emit_angry(self, x: float, y: float) -> None:
        self.emit_preset("angry", x, y)

    def emit_level_up(self, x: float, y: float) -> None:
        self.emit_preset("level_up", x, y)

    def emit_sleep(self, x: float, y: float) -> None:
        if not self._can_emit(1):
            return
        color = QColor(150, 180, 255, 200)
        p = Particle(x, y, "Z", color, random.randint(16, 24))
        p.vel = QPointF(random.uniform(-0.5, 0.5), -1.5)
        p.decay = 0.01
        self._particles.append(p)

    def emit_sweat(self, x: float, y: float) -> None:
        if not self._can_emit(3):
            return
        sweat_offset = 10
        for _ in range(3):
            color = QColor(100, 180, 255, 220)
            p = Particle(
                x + random.randint(-sweat_offset, sweat_offset),
                y - sweat_offset,
                "💧", color, random.randint(10, 16),
            )
            p.vel = QPointF(random.uniform(-0.5, 0.5), random.uniform(1.0, 2.5))
            p.decay = 0.02
            self._particles.append(p)

    def emit_poop(self, x: float, y: float) -> None:
        if not self._can_emit(1):
            return
        color = QColor(139, 90, 43)
        p = Particle(x, y, "💩", color, 18)
        p.vel = QPointF(0, -1.5)
        p.decay = 0.015
        self._particles.append(p)

    def stop(self) -> None:
        """Stop the particle timer for clean shutdown."""
        self._timer.stop()

    # --- Internal ---

    def _font_for(self, size: int) -> QFont:
        """Return a cached bold font for *size* (sizes are bounded ints)."""
        font = self._font_cache.get(size)
        if font is None:
            font = QFont("Arial", size)
            font.setBold(True)
            self._font_cache[size] = font
        return font

    def _tick(self) -> None:
        self._particles = [p for p in self._particles if p.update()]
        if self._particles:
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scratch = self._scratch_color
        for p in self._particles:
            base = p.color
            scratch.setRgb(base.red(), base.green(), base.blue())
            scratch.setAlphaF(max(0.0, min(1.0, p.life)))
            painter.setPen(scratch)
            painter.setFont(self._font_for(p.size))
            painter.drawText(int(p.pos.x()), int(p.pos.y()), p.char)
