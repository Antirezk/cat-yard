"""Kirby desktop pet widget with state-machine AI and velocity-based physics."""

from __future__ import annotations

import math
import random
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from PyQt5.QtWidgets import QLabel, QWidget
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import Qt, QTimer, QPointF

from utils.utils import (
    resource_path, screen_geometry,
    PET_FPS, PET_MAX_SPEED, PET_CHASE_MAX_SPEED, PET_ACCELERATION,
    PET_FRICTION, PET_THROW_FRICTION, PET_THROW_GRAVITY,
    PET_FLIP_SPEED_THRESHOLD, PET_THROW_STOP_SPEED,
    PET_MAX_THROW_SPEED, PET_MIN_THROW_SPEED,
    PET_BOUNCE_FACTOR_NORMAL, PET_BOUNCE_FACTOR_THROWN,
    PET_WANDER_NUDGE_CHANCE, PET_REST_SWAY_CHANCE,
    PET_WANDER_NUDGE_SIGMA, PET_REST_SWAY_SIGMA,
    PET_CHASE_STEERING, PET_CHASE_ACCEL_MULTIPLIER,
    PET_SLEEP_FRICTION, PET_REST_FRICTION, PET_INIT_MARGIN,
    PET_MAX_THROW_BOUNCES,
    PET_THROW_VELOCITY_SCALE, PET_CLICK_THRESHOLD_PX, PET_DRAG_HISTORY_LEN,
    ADULT_SCALE, BABY_SCALE,
    BABY_MAX_SPEED, BABY_CHASE_MAX_SPEED, BABY_ACCELERATION,
    WANDER_DURATION, IDLE_DURATION, REST_DURATION, INIT_WANDER_DURATION,
)
from utils.macos_window import pin_window_above_mission_control
import surface

if TYPE_CHECKING:
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QPoint
    from core.main_controller import MainController


class State(Enum):
    """Pet behavior states for the finite state machine."""

    WANDERING = auto()
    IDLE = auto()
    CHASING = auto()
    RESTING = auto()
    THROWN = auto()


class PetWidget(QWidget):
    """
    Kirby with state-machine movement: wander, pause, rest, chase food.
    Uses velocity with acceleration for smooth, natural motion.
    """

    def __init__(self, controller: "MainController", is_baby: bool = False) -> None:
        super().__init__()
        self.controller = controller
        self.is_baby = is_baby
        self.scale_factor = BABY_SCALE if is_baby else ADULT_SCALE

        # Drag state
        self._dragging = False
        self._drag_offset: Optional[QPoint] = None
        self._drag_positions: list[tuple[QPoint, int]] = []

        # Physics
        self._max_speed = BABY_MAX_SPEED if is_baby else PET_MAX_SPEED
        self._chase_max_speed = BABY_CHASE_MAX_SPEED if is_baby else PET_CHASE_MAX_SPEED
        self._acceleration = BABY_ACCELERATION if is_baby else PET_ACCELERATION
        self.pos_f = QPointF(0, 0)
        self.vel = QPointF(0, 0)
        self._target_dir = QPointF(1, 0)
        self.is_facing_right = True
        self._throw_bounces = 0

        # State machine
        self.state = State.WANDERING
        self._state_timer = 0

        self._init_ui()

    # --- Initialization ---

    def _init_ui(self) -> None:
        surface.configure(self, "pet")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.label = QLabel(self)
        self._right_movie = QMovie(resource_path("images/Y3il.gif"))
        self._left_movie = QMovie(resource_path("images/Y3il-reverse.gif"))
        self._current_movie = self._right_movie
        self.label.setMovie(self._current_movie)
        self._current_movie.start()
        self.label.setScaledContents(True)
        self.label.resize(self._current_movie.frameRect().size())

        screen = screen_geometry()
        self._screen_width = screen.width()
        self._screen_height = screen.height()

        self.resize(self._current_movie.frameRect().size())
        self._original_size = self._current_movie.frameRect().size()

        # Clamp the high bound so randint never sees an empty range on
        # small/secondary displays (mirrors SnackWidget's guard).
        margin = PET_INIT_MARGIN
        hi_x = max(margin, self._screen_width - self.width() - margin)
        hi_y = max(margin, self._screen_height - self.height() - margin)
        init_x = random.randint(margin, hi_x)
        init_y = random.randint(margin, hi_y)
        self.move(init_x, init_y)
        self.pos_f = QPointF(init_x, init_y)

        self._pick_wander_direction()
        self._state_timer = random.randint(*INIT_WANDER_DURATION)
        self.show()
        pin_window_above_mission_control(self)
        surface.fit(self)
        surface.finish(self)

        if self.is_baby:
            self.apply_scale()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000 // PET_FPS)

    def stop(self) -> None:
        """Stop the tick timer and movies for clean shutdown."""
        self._tick_timer.stop()
        self._right_movie.stop()
        self._left_movie.stop()

    # --- Main tick ---

    def _tick(self) -> None:
        if self._dragging:
            return

        if self.state == State.THROWN:
            self._do_thrown()
            self._apply_velocity()
            self.controller.check_collision()
            return

        if self.controller.mood == "sleeping":
            self.vel *= PET_SLEEP_FRICTION
            self._apply_velocity()
            return

        self._state_timer -= 1
        self._update_state_transitions()
        self._execute_state_behavior()
        self._apply_velocity()
        self.controller.check_collision()

    def _update_state_transitions(self) -> None:
        """Handle state machine transitions."""
        has_food = bool(self.controller.snacks)
        should_chase = has_food if self.is_baby else (self.controller.mood == "hungry" and has_food)

        if should_chase:
            self.state = State.CHASING
        elif self.state == State.CHASING and not should_chase:
            self._enter_wandering()
        elif self._state_timer <= 0:
            self._next_state()

    def _execute_state_behavior(self) -> None:
        """Execute the current state's behavior."""
        behaviors = {
            State.WANDERING: self._do_wander,
            State.IDLE: self._do_idle,
            State.RESTING: self._do_rest,
            State.CHASING: self._do_chase,
        }
        handler = behaviors.get(self.state)
        if handler:
            handler()

    # --- State transitions ---

    def _next_state(self) -> None:
        if self.state == State.WANDERING:
            roll = random.random()
            if roll < 0.5:
                self._enter_idle()
            elif roll < 0.75:
                self._enter_resting()
            else:
                self._enter_wandering()
        elif self.state in (State.IDLE, State.RESTING):
            self._enter_wandering()

    def _enter_wandering(self) -> None:
        self.state = State.WANDERING
        self._pick_wander_direction()
        self._state_timer = random.randint(*WANDER_DURATION)

    def _enter_idle(self) -> None:
        self.state = State.IDLE
        self._state_timer = random.randint(*IDLE_DURATION)

    def _enter_resting(self) -> None:
        self.state = State.RESTING
        self._state_timer = random.randint(*REST_DURATION)

    def _pick_wander_direction(self) -> None:
        angle = random.uniform(0, 2 * math.pi)
        self._target_dir = QPointF(math.cos(angle), math.sin(angle))

    # --- State behaviors ---

    def _do_wander(self) -> None:
        if random.random() < PET_WANDER_NUDGE_CHANCE:
            nudge = random.gauss(0, PET_WANDER_NUDGE_SIGMA)
            cos_a, sin_a = math.cos(nudge), math.sin(nudge)
            dx = self._target_dir.x() * cos_a - self._target_dir.y() * sin_a
            dy = self._target_dir.x() * sin_a + self._target_dir.y() * cos_a
            self._target_dir = QPointF(dx, dy)
            self._normalize_target()

        ax = self._target_dir.x() * self._acceleration
        ay = self._target_dir.y() * self._acceleration
        self.vel = QPointF(self.vel.x() + ax, self.vel.y() + ay)
        self._clamp_speed(self._max_speed)
        self._update_facing()

    def _do_idle(self) -> None:
        self.vel *= PET_FRICTION

    def _do_rest(self) -> None:
        self.vel *= PET_REST_FRICTION
        if random.random() < PET_REST_SWAY_CHANCE:
            self.vel = QPointF(
                self.vel.x() + random.gauss(0, PET_REST_SWAY_SIGMA),
                self.vel.y() + random.gauss(0, PET_REST_SWAY_SIGMA),
            )

    def _do_chase(self) -> None:
        target = self._nearest_snack_center()
        if target is None:
            return
        center = self.frameGeometry().center()
        dx = target.x() - center.x()
        dy = target.y() - center.y()
        dist = math.hypot(dx, dy)
        if dist < 1:
            return

        desired = QPointF(dx / dist, dy / dist)
        self._target_dir = QPointF(
            self._target_dir.x() + (desired.x() - self._target_dir.x()) * PET_CHASE_STEERING,
            self._target_dir.y() + (desired.y() - self._target_dir.y()) * PET_CHASE_STEERING,
        )
        self._normalize_target()

        chase_accel = self._acceleration * PET_CHASE_ACCEL_MULTIPLIER
        self.vel = QPointF(
            self.vel.x() + self._target_dir.x() * chase_accel,
            self.vel.y() + self._target_dir.y() * chase_accel,
        )
        self._clamp_speed(self._chase_max_speed)
        self._update_facing()

    def _do_thrown(self) -> None:
        """Kirby was flung — apply gravity and high friction until stopped."""
        self.vel = QPointF(
            self.vel.x() * PET_THROW_FRICTION,
            self.vel.y() * PET_THROW_FRICTION + PET_THROW_GRAVITY,
        )
        self._update_facing()
        speed = math.hypot(self.vel.x(), self.vel.y())
        if speed < PET_THROW_STOP_SPEED:
            self._throw_bounces = 0
            self._enter_wandering()
            self.controller.bubble.show_text(
                random.choice(["Whoa!", "Dizzy...", "Poyo~?!", "Again!!"]), 2000
            )

    # --- Physics helpers ---

    def _apply_velocity(self) -> None:
        self.vel = QPointF(self.vel.x() * PET_FRICTION, self.vel.y() * PET_FRICTION)
        new_pos = QPointF(self.pos_f.x() + self.vel.x(), self.pos_f.y() + self.vel.y())
        new_pos = self._bounce(new_pos)
        self.pos_f = new_pos
        self.move(int(new_pos.x()), int(new_pos.y()))

    def _clamp_speed(self, max_spd: float) -> None:
        speed = math.hypot(self.vel.x(), self.vel.y())
        if speed > max_spd:
            ratio = max_spd / speed
            self.vel = QPointF(self.vel.x() * ratio, self.vel.y() * ratio)

    def _normalize_target(self) -> None:
        mag = math.hypot(self._target_dir.x(), self._target_dir.y())
        if mag > 0:
            self._target_dir = QPointF(self._target_dir.x() / mag, self._target_dir.y() / mag)

    def _update_facing(self) -> None:
        speed = math.hypot(self.vel.x(), self.vel.y())
        if speed < PET_FLIP_SPEED_THRESHOLD:
            return
        facing_right = self.vel.x() >= 0
        if facing_right != self.is_facing_right:
            self.is_facing_right = facing_right
            new_movie = self._right_movie if facing_right else self._left_movie
            self._current_movie.stop()
            self._current_movie = new_movie
            self.label.setMovie(self._current_movie)
            self._current_movie.start()

    def _bounce(self, pos: QPointF) -> QPointF:
        max_x = self._screen_width - self.width()
        max_y = self._screen_height - self.height()
        bounce_factor = (
            PET_BOUNCE_FACTOR_THROWN if self.state == State.THROWN
            else PET_BOUNCE_FACTOR_NORMAL
        )
        bounced = False

        for axis, limit_lo, limit_hi in [("x", 0, max_x), ("y", 0, max_y)]:
            getter = pos.x if axis == "x" else pos.y
            setter = pos.setX if axis == "x" else pos.setY
            vel_get = self.vel.x if axis == "x" else self.vel.y
            vel_set = self.vel.setX if axis == "x" else self.vel.setY
            tdir_get = self._target_dir.x if axis == "x" else self._target_dir.y
            tdir_set = self._target_dir.setX if axis == "x" else self._target_dir.setY

            if getter() < limit_lo:
                setter(limit_lo)
                vel_set(abs(vel_get()) * bounce_factor)
                tdir_set(abs(tdir_get()))
                bounced = True
            elif getter() > limit_hi:
                setter(limit_hi)
                vel_set(-abs(vel_get()) * bounce_factor)
                tdir_set(-abs(tdir_get()))
                bounced = True

        if bounced and self.state == State.THROWN:
            self._throw_bounces += 1
            if self._throw_bounces <= PET_MAX_THROW_BOUNCES:
                center = self.frameGeometry().center()
                self.controller.particles.emit_eat(center.x(), center.y())
        return pos

    def _nearest_snack_center(self) -> "Optional[QPoint]":
        if not self.controller.snacks:
            return None
        center = self.frameGeometry().center()
        nearest = min(
            self.controller.snacks,
            key=lambda s: (center - s.frameGeometry().center()).manhattanLength(),
        )
        return nearest.frameGeometry().center()

    def apply_scale(self) -> None:
        w = int(self._original_size.width() * self.scale_factor)
        h = int(self._original_size.height() * self.scale_factor)
        self.resize(w, h)
        self.label.resize(w, h)

    # --- Mouse interactions ---

    def mousePressEvent(self, event: "QMouseEvent") -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.pos()
            self._press_global = event.globalPos()
            self._drag_positions = [(event.globalPos(), event.timestamp())]

    def mouseMoveEvent(self, event: "QMouseEvent") -> None:
        if self._dragging and self._drag_offset is not None:
            pointer = self.parentWidget().mapFromGlobal(event.globalPos()) if self.parentWidget() else event.globalPos()
            new_pos = pointer - self._drag_offset
            self.move(new_pos)
            self.pos_f = QPointF(new_pos.x(), new_pos.y())
            self._drag_positions.append((event.globalPos(), event.timestamp()))
            if len(self._drag_positions) > PET_DRAG_HISTORY_LEN:
                self._drag_positions.pop(0)

    def mouseReleaseEvent(self, event: "QMouseEvent") -> None:
        if event.button() != Qt.LeftButton or not self._dragging or self._drag_offset is None:
            return

        delta = event.globalPos() - self._press_global
        if delta.manhattanLength() < PET_CLICK_THRESHOLD_PX:
            # Click — pet Kirby
            self.controller.pet_kirby(self)
        else:
            self._try_throw()

        self._dragging = False
        self._drag_offset = None
        self._drag_positions = []

    def _try_throw(self) -> None:
        """Calculate throw velocity from drag history and enter THROWN state."""
        if len(self._drag_positions) < 2:
            return

        p1, t1 = self._drag_positions[0]
        p2, t2 = self._drag_positions[-1]
        dt = max(1, t2 - t1)
        vx = (p2.x() - p1.x()) / dt * PET_THROW_VELOCITY_SCALE
        vy = (p2.y() - p1.y()) / dt * PET_THROW_VELOCITY_SCALE
        speed = math.hypot(vx, vy)

        if speed < PET_MIN_THROW_SPEED:
            return

        if speed > PET_MAX_THROW_SPEED:
            ratio = PET_MAX_THROW_SPEED / speed
            vx *= ratio
            vy *= ratio

        self.vel = QPointF(vx, vy)
        self.state = State.THROWN
        self._throw_bounces = 0
        self.controller.bubble.show_text(
            random.choice(["Wheee!", "Poyooo~!", "Waaaah!"]), 1500
        )
