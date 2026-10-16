"""Continuous cat animation layered over inherited pet/game physics."""
import math
import time
from PyQt5.QtCore import Qt, QTimer, QPointF, QSize
from PyQt5.QtGui import QPainter, QCursor
from PyQt5.QtWidgets import QMenu
from widgets.physics_pet import PetWidget as PhysicsPet, State
from cat_art import CatRig, clamp, breed_name
from preferences import tr
import surface
import wand

class PetWidget(PhysicsPet):
    def __init__(self, controller, is_baby=False, breed='calico'):
        self.rig = CatRig(breed)
        self._last_frame = time.perf_counter()
        self._elapsed = 1 / 60
        self._facing_target = 1
        self._action = 'idle'
        self._action_until = 0
        self._hugging = False
        self._play_velocity = QPointF()
        self._purr_at = 0
        self._poop_pending = False
        self.standoff = None
        self._flee_until = 0.0
        self._flee_dir = QPointF(1, 0)
        self.paint_times = []
        self.frame_times = []
        super().__init__(controller, is_baby)

    @property
    def breed(self):
        return self.rig.breed

    @property
    def neutered(self):
        return self.rig.neutered

    @neutered.setter
    def neutered(self, value):
        self.rig.neutered = bool(value); self.update()

    def set_breed(self, breed):
        self.rig.set_breed(breed)
        self.update()

    def breed_label(self):
        return tr(breed_name(self.breed, True), breed_name(self.breed, False))

    def _init_ui(self):
        surface.configure(self, 'pet')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._original_size = QSize(192, 144)
        self.apply_scale()
        rect = surface.bounds()
        self._screen_width, self._screen_height = rect.width(), rect.height()
        self.pos_f = QPointF(max(0, (rect.width() - self.width()) / 2), max(0, (rect.height() - self.height()) / 2))
        self.move(int(self.pos_f.x()), int(self.pos_f.y()))
        self._pick_wander_direction()
        self._state_timer = 110
        self.show(); surface.fit(self); surface.finish(self)
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.PreciseTimer)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(16)

    def stop(self):
        self._tick_timer.stop()

    def apply_scale(self):
        display = min(self.scale_factor, 1.65 if surface.mode != 'window' else 1.25)
        self.resize(int(192 * display), int(144 * display))

    def place(self, x, y):
        rect = surface.bounds()
        x = clamp(x, 0, max(0, rect.width() - self.width()))
        y = clamp(y, 0, max(0, rect.height() - self.height()))
        self.pos_f = QPointF(x, y); self.move(round(x), round(y))

    def cue(self, action, duration=1.8):
        self._action = action
        self._action_until = time.perf_counter() + duration

    def current_action(self):
        return self._action if time.perf_counter() < self._action_until else 'idle'

    def foot(self):
        """Point on the ground under the cat's body, in surface coordinates."""
        return QPointF(self.pos_f.x() + self.width() * .5, self.pos_f.y() + self.height() * .8)

    def flee(self, direction, seconds=3.2):
        """Bolt away at full speed, bouncing off the edges."""
        self._flee_dir = QPointF(direction)
        self._flee_until = time.perf_counter() + seconds
        self._action_until = 0

    @property
    def fleeing(self):
        return time.perf_counter() < self._flee_until

    def status(self):
        """Short state label for the roster."""
        if self.standoff is not None: return 'standoff'
        if self._dragging: return 'held'
        if self.fleeing: return 'flee'
        if self.rig.pose.sleep > .5: return 'sleep'
        action = self.current_action()
        if action in ('eat', 'poop', 'pet'): return action
        return 'walk'

    def is_free(self):
        """True when the cat is just roaming and could bump into another cat."""
        return (not self._dragging and self.standoff is None and self.state != State.THROWN and not self.fleeing
                and not self._hugging and not self._poop_pending
                and self.current_action() in ('idle', 'pet'))

    def mouth_anchor(self):
        p = self.rig.pose
        projected = (.3 + .7 * abs(p.facing)) * (1 if p.facing >= 0 else -1)
        head_x, head_y = self.rig.head_xy()
        angle = math.radians(self.rig.head_angle())
        vx = (head_x - 120) * projected + math.cos(angle) - 14 * math.sin(angle)
        vy = head_y + math.sin(angle) + 14 * math.cos(angle) + math.cos(p.phase * 2) * 1.6 * p.gait - 126
        tilt = math.radians(p.cuddle * (-16 + math.sin(p.clock * 13) * 2.5) + p.held * math.sin(p.clock * 4) * 5)
        x = 120 + vx * math.cos(tilt) - vy * math.sin(tilt)
        y = 126 + vx * math.sin(tilt) + vy * math.cos(tilt)
        return QPointF(x * self.width() / 240, y * self.height() / 180)

    def _tick(self):
        now = time.perf_counter()
        dt = clamp(now - self._last_frame, .001, .05)
        self._last_frame = now
        self._elapsed = dt
        if len(self.frame_times) < 1200: self.frame_times.append(dt)
        pointer = wand.current.point if wand.current else QCursor.pos()
        pointer = self.parentWidget().mapFromGlobal(pointer) if self.parentWidget() else pointer
        mouth = self.pos_f + self.mouth_anchor()
        look = ((pointer.x() - mouth.x()) / 150, (pointer.y() - mouth.y()) / 150)
        play = bool(wand.current and wand.current.active)
        action = self.current_action()
        if self._dragging:
            action = 'held'; self._hugging = False
        elif self.standoff is not None:
            action = 'hiss'; self._hugging = False; play = False
            look = self._hold_standoff(dt)
        elif self.fleeing:
            action = 'chase'; self._hugging = False; play = False
            self._run_away(dt)
        elif action == 'poop':
            self.vel *= .80
        elif play:
            action = self._play(pointer, dt)
        else:
            if self._hugging: self.controller.bubble.show_text('That was fun!', 1700)
            self._hugging = False
            self._play_velocity *= .7
            if action in ('eat', 'pet'): self.vel *= .85
            else:
                super()._tick()
                if self.controller.mood == 'sleeping': action = 'sleep'
        speed = math.hypot(self.vel.x(), self.vel.y()) * 60 if not play else math.hypot(self._play_velocity.x(), self._play_velocity.y())
        if action in ('sleep', 'eat', 'poop', 'held', 'pet', 'cuddle', 'hiss'): speed = 0
        self.rig.advance(dt, speed, self._facing_target, action, look)
        self.update()

    def _run_away(self, dt):
        step = self._flee_dir * 330 * dt
        old = QPointF(self.pos_f)
        self.vel = self._flee_dir * 5.5
        self.pos_f = self._bounce(self.pos_f + step)
        # Bounced: turn around along that axis.
        if abs(self.pos_f.x() - (old.x() + step.x())) > .5: self._flee_dir.setX(-self._flee_dir.x())
        if abs(self.pos_f.y() - (old.y() + step.y())) > .5: self._flee_dir.setY(-self._flee_dir.y())
        self.move(round(self.pos_f.x()), round(self.pos_f.y()))
        if abs(self._flee_dir.x()) > .1: self._facing_target = 1 if self._flee_dir.x() > 0 else -1
        if time.perf_counter() + dt >= self._flee_until:
            self.vel = self._flee_dir * 1.5
            self._enter_wandering(); self._target_dir = QPointF(self._flee_dir)

    def _hold_standoff(self, dt):
        """Freeze, face the rival, and keep a tense little gap between the two cats."""
        other = self.standoff.other(self)
        dx = other.foot().x() - self.foot().x()
        if abs(dx) < 1: dx = 1 if self is self.standoff.a else -1
        self._facing_target = 1 if dx > 0 else -1
        spacing = (self.width() + other.width()) * .27
        if abs(dx) < spacing:
            step = min(70 * dt, spacing - abs(dx)) * (-1 if dx > 0 else 1)
            self.pos_f = self._bounce(QPointF(self.pos_f.x() + step, self.pos_f.y()))
            self.move(round(self.pos_f.x()), round(self.pos_f.y()))
        self.vel = QPointF(); self._play_velocity = QPointF()
        dy = other.foot().y() - self.foot().y()
        return (1 if dx > 0 else -1, clamp(dy / 120, -.6, .6))

    def _play(self, pointer, dt):
        self.controller._idle_seconds = 0
        if self.controller.mood == 'sleeping': self.controller.mood = 'happy'
        difference = QPointF(pointer) - (self.pos_f + self.mouth_anchor())
        distance = math.hypot(difference.x(), difference.y())
        if not self._hugging and abs(difference.x()) > 34:
            self._facing_target = 1 if difference.x() > 0 else -1
        if distance < 22: self._hugging = True
        elif distance > 175: self._hugging = False
        if self._hugging:
            stiffness, damping, maximum = 145, 23, 680
            if time.perf_counter() > self._purr_at:
                self.controller.bubble.show_text('Caught you! Nom nom~', 1300)
                self._purr_at = time.perf_counter() + 3
        else:
            stiffness, damping, maximum = 13, 6.8, 390
        self._play_velocity += (difference * stiffness - self._play_velocity * damping) * dt
        speed = math.hypot(self._play_velocity.x(), self._play_velocity.y())
        if speed > maximum: self._play_velocity *= maximum / speed
        self.pos_f = self._bounce(self.pos_f + self._play_velocity * dt)
        self.move(round(self.pos_f.x()), round(self.pos_f.y()))
        self.vel = self._play_velocity / 60
        return 'cuddle' if self._hugging else ('pounce' if distance < 130 else 'chase')

    def _update_facing(self):
        if abs(self.vel.x()) > .2:
            self.is_facing_right = self.vel.x() >= 0
            self._facing_target = 1 if self.is_facing_right else -1

    def _update_state_transitions(self):
        super()._update_state_transitions()
        if self.controller.snacks: self.state = State.CHASING

    def _do_chase(self):
        if not self.controller.snacks: return
        mouth = self.pos_f + self.mouth_anchor()
        target = min(self.controller.snacks, key=lambda s: (QPointF(s.frameGeometry().center()) - mouth).manhattanLength())
        difference = QPointF(target.frameGeometry().center()) - mouth
        distance = math.hypot(difference.x(), difference.y())
        if distance > 1:
            self.vel += difference / distance * .23
            self._clamp_speed(3.5)
            if abs(difference.x()) > 30: self._facing_target = 1 if difference.x() > 0 else -1

    def _apply_velocity(self):
        step = self._elapsed * 60
        self.vel *= .96 ** step
        self.pos_f = self._bounce(self.pos_f + self.vel * step)
        self.move(round(self.pos_f.x()), round(self.pos_f.y()))

    def _bounce(self, pos):
        for axis, extent, size in [('x', self._screen_width, self.width()), ('y', self._screen_height, self.height())]:
            value = pos.x() if axis == 'x' else pos.y()
            limit = max(0, extent - size)
            if value < 0 or value > limit:
                if axis == 'x':
                    pos.setX(clamp(value, 0, limit)); self.vel.setX(-self.vel.x() * .45)
                else:
                    pos.setY(clamp(value, 0, limit)); self.vel.setY(-self.vel.y() * .45)
        return pos

    def paintEvent(self, event):
        started = time.perf_counter()
        painter = QPainter(self)
        painter.translate(self.pos_f.x() - self.x(), self.pos_f.y() - self.y())
        self.rig.paint(painter, self.width(), self.height())
        painter.end()
        if len(self.paint_times) < 1200: self.paint_times.append((time.perf_counter() - started) * 1000)

    def mousePressEvent(self, event):
        if wand.current and wand.current.active:
            event.ignore(); return
        if event.button() != Qt.LeftButton:
            event.ignore(); return
        if self._action != 'poop': self._action_until = 0
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # Dragging one of two hissing cats away breaks up the standoff.
        if self._dragging and self.standoff is not None and \
                (event.globalPos() - self._press_global).manhattanLength() >= 8:
            self.controller.end_standoff(self.standoff)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        title = menu.addAction(self.breed_label() + (tr(' · 小猫', ' · kitten') if self.is_baby else ''))
        title.setEnabled(False)
        menu.addSeparator()
        menu.addAction(tr('摸摸', 'Pet'), lambda: self.controller.pet_kirby(self))
        if self.standoff is not None:
            menu.addAction(tr('分开它们', 'Separate them'), lambda: self.controller.end_standoff(self.standoff, nudge=True))
        if not self.neutered:
            menu.addAction(tr('绝育', 'Neuter'), lambda: self.controller.neuter(self))
        if self is not self.controller.pet:
            menu.addAction(tr('送养这只猫', 'Rehome this cat'), lambda: self.controller.rehome(self))
        menu.exec_(event.globalPos())
