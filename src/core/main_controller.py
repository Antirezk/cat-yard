"""Central game controller — all UI lives in the macOS menu-bar tray icon."""

from __future__ import annotations

import datetime
import logging
import math
import random
import time

import psutil
import preferences as prefs
from PyQt5.QtWidgets import QApplication, QInputDialog
from PyQt5.QtCore import QTimer, QPointF
from PyQt5.QtGui import QCursor

from widgets.pet_widget import PetWidget
from widgets.snack_widget import SnackWidget
from widgets.poop_widget import PoopWidget
from widgets.grave_widget import GraveWidget
from widgets.thought_bubble import ThoughtBubble
from utils.utils import (
    STATE_FILE, RANKING_FILE, ACHIEVEMENTS,
    xp_for_level, is_achievement_met, validate_state,
    load_json_safe, save_json_safe, screen_geometry,
    EATS_UNTIL_POOP, POOP_SPAWN_CHANCE, RANDOM_EVENT_CHANCE,
    CPU_HIGH_THRESHOLD, MAX_KIRBYS, BREEDING_DISTANCE,
    BREED_COOLDOWN_FRAMES, POOP_CLEAN_XP, BREED_XP, STAR_FIND_XP,
    MAX_HUNGER, HUNGER_SLEEP_THRESHOLD, HUNGER_HUNGRY_THRESHOLD,
    HUNGER_EXCITED_THRESHOLD, HUNGER_AUTO_FEED_THRESHOLD,
    HUNGER_STARVING_THRESHOLD,
    MAX_POOPS, MAX_SNACKS, BABY_SCALE, MAX_USERNAME_LENGTH,
    MAX_LEVELUPS_PER_TICK, BABY_SPAWN_MARGIN, BABY_SPAWN_VX_RANGE, BABY_SPAWN_VY,
    EVENT_TRIP_HOP, EVENT_DANCE_HSPEED, EVENT_DANCE_HOP,
    EVENT_SNEEZE_PUSH, EVENT_SNEEZE_HOP, EVENT_HICCUP_HOP,
    PET_GROWTH_BASE, PET_GROWTH_DIMINISH,
    HUNGER_TICK_MS, HUNGER_RATE, AUTO_SAVE_MS, MOOD_TICK_MS,
    SLEEP_THRESHOLD_S, TRAY_REFRESH_MS, EVENT_TICK_MS,
    CPU_TICK_MS, BREED_CHECK_MS, BUBBLE_TICK_MS,
)
from core.tray_menu import TrayPresenter
from utils.particles import ParticleOverlay
from cat_art import ADOPTABLE, breed_name
import sound
import surface

STANDOFF_LINES = ['老吴老吴老吴老吴', '哦内个内个内个内个...', '嗷呜嗷呜～老吴老吴！', '哈——！！',
                  '老吴老吴老吴老吴！！', '哦内个内个内个...内个...']
STANDOFF_COOLDOWN_S = 6.0
MAX_BREED_TOTAL = 20      # kittens stop being born past this many cats (adoption is unlimited)
FLEE_CHANCE = .55         # when a standoff times out, chance that one cat bolts


class Standoff:
    """Two cats of different breeds frozen in a hissing face-off."""

    def __init__(self, a: PetWidget, b: PetWidget) -> None:
        self.a, self.b = a, b
        a.standoff = b.standoff = self
        self.bubble = ThoughtBubble()
        self.bubble.raise_()
        now = time.monotonic()
        self.started = now
        # Random length, but never shorter than the configured minimum.
        minimum = max(5, prefs.values.get('standoff_min', 45))
        self.end_at = now + minimum + min(120, random.expovariate(1 / 25))
        self.next_line = 0.0
        self.next_puff = 0.0
        self.line = random.randrange(len(STANDOFF_LINES))
        self.next_poop = {a: now + random.uniform(3, 9), b: now + random.uniform(3, 9)}
        # Kitten vs grown cat: 50% chance the adult goes for the paw swipe and lands it.
        self.kitten = a if a.is_baby and not b.is_baby else (b if b.is_baby and not a.is_baby else None)
        self.bully = self.other(self.kitten) if self.kitten else None
        self.doomed = self.kitten is not None and random.random() < .5
        self.swipe_at = now + random.uniform(8, 30)
        self.swipe_forced = False
        self.sound = sound.start_standoff_loop()

    def other(self, pet: PetWidget) -> PetWidget:
        return self.b if pet is self.a else self.a

    def stop_sound(self) -> None:
        if self.sound is not None:
            self.sound.stop()
            self.sound = None

    def close(self) -> None:
        self.stop_sound()
        self.a.standoff = self.b.standoff = None
        surface.unregister(self.bubble)
        self.bubble.stop(); self.bubble.close(); self.bubble.deleteLater()

logger = logging.getLogger(__name__)


class MainController:
    """Central game controller.

    Owns the game state and every game system (food, XP, hunger, mood,
    achievements, poop, random events, CPU monitor, breeding, persistence).
    The macOS menu-bar UI is delegated to :class:`TrayPresenter`.
    """

    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.username = self._ask_username()

        # Game state
        self.hunger = 0
        self.xp = 0
        self.level = 1
        self.total_eats = 0
        self.total_pets = 0
        self.star_eats = 0
        self.mood = "happy"
        self.unlocked_achievements: set[str] = set()
        self.snacks: list[SnackWidget] = []
        self.poops: list[PoopWidget] = []
        self.graves: list[GraveWidget] = []
        self._idle_seconds: float = 0.0
        self._eats_since_poop = 0
        self._cpu_percent = 0.0
        self._breed_cooldown = 0

        # Widgets
        self.particles = ParticleOverlay()
        self.pet = PetWidget(self, breed=prefs.values.get('breed', 'calico'))
        self.extra_pets: list[PetWidget] = []
        self.bubble = ThoughtBubble()
        self.standoffs: list[Standoff] = []
        self._near_pairs: set = set()
        self._pair_cooldown: dict = {}
        self._standoff_seeded = False
        self._last_cursor = QCursor.pos()
        self._last_move = time.monotonic()

        self._load_state()
        self._setup_tray()
        self._init_timers()
        self._time_greeting()

    # --- Initialization helpers ---

    @staticmethod
    def _ask_username() -> str:
        username, ok = QInputDialog.getText(None, "Username", "Enter your username:")
        name = username.strip() if ok and username.strip() else "Player"
        return name[:MAX_USERNAME_LENGTH]

    def _init_timers(self) -> None:
        """Create and start all game timers."""
        timer_defs = [
            (HUNGER_TICK_MS,  self._hunger_tick),
            (MOOD_TICK_MS,    self._mood_tick),
            (AUTO_SAVE_MS,    self.save_state),
            (BUBBLE_TICK_MS,  self._update_bubble_pos),
            (TRAY_REFRESH_MS, self.tray.refresh),
            (EVENT_TICK_MS,   self._random_event),
            (CPU_TICK_MS,     self._cpu_tick),
            (BREED_CHECK_MS,  self._check_breeding),
            (100,             self._check_standoffs),
            (1000,            self._idle_check),
        ]
        self._timers: list[QTimer] = []
        for interval_ms, callback in timer_defs:
            timer = QTimer()
            timer.timeout.connect(callback)
            timer.start(interval_ms)
            self._timers.append(timer)

    def stop_all_timers(self) -> None:
        """Stop every timer and tear down widgets cleanly. Called on quit."""
        for timer in self._timers:
            timer.stop()
        # Tear down widget-owned timers / movies.
        self.particles.stop()
        self.bubble.stop()
        for standoff in self.standoffs[:]:
            standoff.close()
        self.standoffs.clear()
        sound.stop_all()
        self.pet.stop()
        for baby in self.extra_pets:
            baby.stop()
            baby.close()
        for snack in self.snacks:
            snack.close()
        for poop in self.poops:
            poop.close()
        for grave in self.graves:
            grave.close()

    # --- Tray (macOS menu bar) ---

    def _setup_tray(self) -> None:
        self.tray = TrayPresenter(self, self.app)

    def show_ranking(self) -> None:
        from dialogs.ranking_board import RankingBoard
        RankingBoard().exec_()

    def show_achievements(self) -> None:
        from dialogs.stats_dialog import StatsDialog
        StatsDialog(self).exec_()

    # --- Properties ---

    @property
    def xp_for_next_level(self) -> int:
        return xp_for_level(self.level)

    @property
    def all_pets(self) -> list:
        return [self.pet] + self.extra_pets

    @property
    def _poop_pending(self) -> bool:
        return any(p._poop_pending for p in self.all_pets)

    @property
    def cpu_percent(self) -> float:
        """Most recent CPU-load reading, in percent."""
        return self._cpu_percent

    # --- Food ---

    def spawn_snack(self) -> None:
        if len(self.snacks) >= MAX_SNACKS:
            return  # prevent snack spam
        snack = SnackWidget()
        rect = screen_geometry()
        # Keep food reachable by the cat's mouth while its whole body stays inside.
        x = random.uniform(75, max(76, rect.width() - 75))
        y = random.uniform(64, max(65, rect.height() - 90))
        snack.move(int(x - snack.width() / 2), int(y - snack.height() / 2))
        self.snacks.append(snack)

    def _remove_snack(self, snack: SnackWidget) -> None:
        if snack in self.snacks:
            import surface
            surface.unregister(snack)
            snack.close()
            self.snacks.remove(snack)
            snack.deleteLater()

    def _legacy_check_collision(self) -> None:
        pet_rect = self.pet.frameGeometry()
        for snack in self.snacks[:]:
            if pet_rect.intersects(snack.frameGeometry()):
                self._eat(snack)

        for baby in self.extra_pets:
            baby_rect = baby.frameGeometry()
            for snack in self.snacks[:]:
                if baby_rect.intersects(snack.frameGeometry()):
                    self._eat(snack)
                    break

    def check_collision(self) -> None:
        for pet in [self.pet] + getattr(self, 'extra_pets', []):
            mouth = pet.pos_f + pet.mouth_anchor()
            for snack in self.snacks[:]:
                center = snack.frameGeometry().center()
                if math.hypot(center.x() - mouth.x(), center.y() - mouth.y()) < 23:
                    self._eat(snack, pet)
                    break

    def _eat(self, snack: SnackWidget, pet: PetWidget | None = None) -> None:
        pet = pet or self.pet
        pet.cue('eat', 2.0)
        self.hunger = max(0, self.hunger - snack.hunger_restore)
        self._add_xp(snack.xp_reward)
        self.total_eats += 1
        self._eats_since_poop += 1
        if snack.food_name == "Star Treat":
            self.star_eats += 1

        center = snack.frameGeometry().center()
        self.particles.emit_eat(center.x(), center.y())

        thoughts = [
            f"Yum! {snack.food_name}!",
            "Delicious~",
            f"+{snack.xp_reward} XP!",
            "More food!",
            "Poyo~!",
        ]
        self.bubble.show_text(random.choice(thoughts), 2000)
        self._remove_snack(snack)
        self._reset_idle()
        self._check_achievements()

        if prefs.values['poop_mode'] == 'food' and self._eats_since_poop >= prefs.values['meals']:
            self._eats_since_poop = 0
            if random.random() >= prefs.values['chance'] / 100:
                return
            self._spawn_poop(pet)

    # --- XP / Level ---

    def _add_xp(self, amount: int) -> None:
        self.xp += amount
        count = 0
        while self.xp >= self.xp_for_next_level and count < MAX_LEVELUPS_PER_TICK:
            needed = self.xp_for_next_level
            if needed <= 0:
                break
            self.xp -= needed
            self.level += 1
            self._on_level_up()
            count += 1

    def _on_level_up(self) -> None:
        growth = PET_GROWTH_BASE / (1 + (self.level - 1) * PET_GROWTH_DIMINISH)
        self.pet.scale_factor += growth
        self.pet.apply_scale()

        center = self.pet.frameGeometry().center()
        self.particles.emit_level_up(center.x(), center.y())
        self.bubble.show_text(f"Level {self.level}!", 3000)

    # --- Hunger ---

    def _hunger_tick(self) -> None:
        if self.hunger < MAX_HUNGER:
            self.hunger = min(MAX_HUNGER, self.hunger + HUNGER_RATE)
        # Auto-feed only if no snacks already pending
        if self.hunger >= HUNGER_AUTO_FEED_THRESHOLD and not self.snacks:
            self.spawn_snack()

    # --- Mood ---

    def _mood_tick(self) -> None:
        self._idle_seconds += MOOD_TICK_MS / 1000
        if self.mood == "sleeping":
            self._emit_sleep_particles()
            return
        if self.hunger >= HUNGER_HUNGRY_THRESHOLD:
            self.mood = "hungry"
            if self.hunger >= HUNGER_STARVING_THRESHOLD:
                self.bubble.show_text("I'm starving...", 3000)
        elif self.total_eats > 0 and self.hunger < HUNGER_EXCITED_THRESHOLD:
            self.mood = "excited"
        else:
            self.mood = "happy"

    def _idle_check(self) -> None:
        """Cats fall asleep when the mouse hasn't moved for a while (hissing cats stay up)."""
        now = time.monotonic()
        cursor = QCursor.pos()
        if cursor != self._last_cursor:
            self._last_cursor, self._last_move = cursor, now
            if self.mood == "sleeping":
                self.mood = "happy"
            return
        limit = max(1, prefs.values.get('sleep_minutes', 5)) * 60
        if now - self._last_move >= limit and self.mood != "sleeping":
            self.mood = "sleeping"
            self.bubble.show_text("Zzz...", 5000)

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_move

    def _emit_sleep_particles(self) -> None:
        for pet in self.all_pets:
            if pet.standoff is None and pet.rig.pose.sleep > .5:
                center = pet.frameGeometry().center()
                self.particles.emit_sleep(center.x() + 20, center.y() - 10)

    def _reset_idle(self) -> None:
        self._idle_seconds = 0.0
        if self.mood == "sleeping":
            self.mood = "happy"

    # --- Petting ---

    def pet_kirby(self, pet: PetWidget | None = None) -> None:
        pet = pet or self.pet
        if pet.standoff is None:
            pet.cue('pet', 1.8)
        self.total_pets += 1
        self._reset_idle()
        center = pet.frameGeometry().center()
        self.particles.emit_heart(center.x(), center.y() - 20)

        reactions = ["Poyo~!", "♥♥♥", "Hehe~", "That tickles!", "More pets!"]
        self.bubble.show_text(random.choice(reactions), 2500)
        self._check_achievements()

    # --- Achievements ---

    def _check_achievements(self) -> None:
        for ach in ACHIEVEMENTS:
            if ach["id"] in self.unlocked_achievements:
                continue
            if is_achievement_met(
                ach,
                total_eats=self.total_eats,
                level=self.level,
                total_pets=self.total_pets,
                star_eats=self.star_eats,
            ):
                self.unlocked_achievements.add(ach["id"])
                center = self.pet.frameGeometry().center()
                self.particles.emit_achievement(center.x(), center.y())
                self.bubble.show_text(f"🏆 {ach['name']}!", 4000)

    # --- Poop ---

    def _spawn_poop(self, pet: PetWidget | None = None) -> None:
        if pet is None:
            # Interval mode: whichever cat is free goes, the main cat preferred.
            free = [p for p in self.all_pets if not p._poop_pending and p.standoff is None]
            pet = self.pet if self.pet in free else (random.choice(free) if free else None)
        if pet is None or pet._poop_pending:
            return
        pet._poop_pending = True
        pet.cue('poop', 2.1)
        QTimer.singleShot(1500, lambda: self._finish_poop(pet))

    def _finish_poop(self, pet: PetWidget | None = None) -> None:
        pet = pet or self.pet
        pet._poop_pending = False
        if pet is self.pet or pet in self.extra_pets:
            self._deposit_poop(pet)

    def _deposit_poop(self, pet: PetWidget | None = None, scared: bool = False) -> None:
        # No cap: poop piles up forever until someone cleans it.
        self._eats_since_poop = 0
        pet = pet or self.pet
        pos = pet.pos()
        # Poop sits under the tail, which is on the opposite side of the facing direction.
        tail_side = .30 if pet.rig.pose.facing >= 0 else .62
        self._add_poop(pos.x() + int(pet.width() * tail_side), pos.y() + int(pet.height() * .82))
        center = self.poops[-1].frameGeometry().center()
        self.particles.emit_poop(center.x(), center.y())
        if not scared:
            self.bubble.show_text(random.choice(["Oops...", "Uh oh~", "Excuse me!"]), 2000)

    def _add_poop(self, x: float, y: float) -> PoopWidget:
        """Poops stay forever (and across restarts) until someone cleans them."""
        poop = PoopWidget(x, y, self)
        self.poops.append(poop)
        return poop

    def clean_poop(self, poop: PoopWidget) -> None:
        if poop in self.poops:
            import surface
            surface.unregister(poop)
            center = poop.frameGeometry().center()  # capture before close()
            poop.close()
            self.poops.remove(poop)
            poop.deleteLater()
            self._add_xp(POOP_CLEAN_XP)
            self.particles.emit_eat(center.x(), center.y())
            self.bubble.show_text(random.choice(["Thanks!", "Clean~!", "Sparkle!"]), 1500)

    # --- Random Events ---

    def _random_event(self) -> None:
        if self.mood == "sleeping":
            return
        if random.random() > RANDOM_EVENT_CHANCE:
            return

        events = [
            self._event_trip,
            self._event_find_star,
            self._event_dance,
            self._event_sneeze,
            self._event_hiccup,
        ]
        random.choice(events)()

    def _event_trip(self) -> None:
        self.bubble.show_text("*trips* Poyo!", 2500)
        center = self.pet.frameGeometry().center()
        self.particles.emit_eat(center.x(), center.y())
        self.pet.vel.setY(EVENT_TRIP_HOP)

    def _event_find_star(self) -> None:
        self._add_xp(STAR_FIND_XP)
        self.bubble.show_text(f"Found a star! +{STAR_FIND_XP} XP!", 3000)
        center = self.pet.frameGeometry().center()
        self.particles.emit_achievement(center.x(), center.y())

    def _event_dance(self) -> None:
        self.bubble.show_text("Dance time!", 3000)
        center = self.pet.frameGeometry().center()
        self.pet.vel = QPointF(
            random.choice([-EVENT_DANCE_HSPEED, EVENT_DANCE_HSPEED]), EVENT_DANCE_HOP
        )
        for _ in range(6):
            self.particles.emit_heart(
                center.x() + random.randint(-30, 30),
                center.y() + random.randint(-30, 30),
            )

    def _event_sneeze(self) -> None:
        self.bubble.show_text("Achoo!", 2000)
        direction = -EVENT_SNEEZE_PUSH if self.pet.is_facing_right else EVENT_SNEEZE_PUSH
        self.pet.vel = QPointF(direction, EVENT_SNEEZE_HOP)

    def _event_hiccup(self) -> None:
        self.bubble.show_text("*hic* ...hic!", 2500)
        self.pet.vel.setY(EVENT_HICCUP_HOP)

    # --- CPU Monitor ---

    def _cpu_tick(self) -> None:
        self._cpu_percent = psutil.cpu_percent(interval=None)
        if self._cpu_percent > CPU_HIGH_THRESHOLD:
            self.bubble.show_text(
                random.choice(["So hot...", "CPU burning!", "Need rest...", "Working hard!"]),
                3000,
            )
            center = self.pet.frameGeometry().center()
            self.particles.emit_sweat(center.x(), center.y())

    # --- Time-based ---

    def _time_greeting(self) -> None:
        hour = datetime.datetime.now().hour
        greetings = [
            (range(5, 9),   "Good morning! Let's code!"),
            (range(9, 12),  "Time to be productive!"),
            (range(12, 14), "Lunch time? Feed me!"),
            (range(14, 18), "Afternoon coding session!"),
            (range(18, 22), "Evening already? Keep going!"),
        ]
        msg = "So late... still coding?"
        for hours, greeting in greetings:
            if hour in hours:
                msg = greeting
                break
        QTimer.singleShot(2000, lambda: self.bubble.show_text(msg, 4000))

    # --- Breeding ---

    def _check_breeding(self) -> None:
        if self._breed_cooldown > 0:
            self._breed_cooldown -= 1
            return

        all_pets = [self.pet] + self.extra_pets
        if len(all_pets) < 2 or len(all_pets) >= MAX_BREED_TOTAL:
            return

        for i in range(len(all_pets)):
            for j in range(i + 1, len(all_pets)):
                if all_pets[i].breed != all_pets[j].breed:
                    continue  # strangers of another breed get a standoff instead
                if all_pets[i].standoff or all_pets[j].standoff:
                    continue
                if all_pets[i].neutered or all_pets[j].neutered:
                    continue  # neutered cats never have kittens
                ac = all_pets[i].frameGeometry().center()
                bc = all_pets[j].frameGeometry().center()
                if math.hypot(ac.x() - bc.x(), ac.y() - bc.y()) < BREEDING_DISTANCE:
                    self._breed(all_pets[i], all_pets[j])
                    return

    def _breed(self, parent_a: PetWidget, parent_b: PetWidget) -> None:
        # Re-check limit (guard against concurrent breeding)
        if len([self.pet] + self.extra_pets) >= MAX_BREED_TOTAL:
            return
        self._breed_cooldown = BREED_COOLDOWN_FRAMES

        screen = screen_geometry()
        max_x = screen.width() - BABY_SPAWN_MARGIN
        max_y = screen.height() - BABY_SPAWN_MARGIN
        mid_x = max(0, min(max_x, (parent_a.pos().x() + parent_b.pos().x()) / 2))
        mid_y = max(0, min(max_y, (parent_a.pos().y() + parent_b.pos().y()) / 2))

        for _ in range(12):
            self.particles.emit_heart(
                int(mid_x) + random.randint(-20, 20),
                int(mid_y) + random.randint(-20, 20),
            )

        self.bubble.show_text(
            random.choice(["A baby Kirby!", "New friend!", "Poyo poyo~!", "Family grows!"]),
            4000,
        )

        baby = PetWidget(self, is_baby=True, breed=random.choice([parent_a.breed, parent_b.breed]))
        baby.scale_factor = BABY_SCALE
        baby.apply_scale()
        baby.move(int(mid_x), int(mid_y))
        baby.pos_f = QPointF(mid_x, mid_y)
        baby.vel = QPointF(random.uniform(*BABY_SPAWN_VX_RANGE), BABY_SPAWN_VY)
        self.extra_pets.append(baby)
        self._grace(baby)

        self._add_xp(BREED_XP)

    # --- Standoffs between different breeds ---

    @staticmethod
    def _pair_key(a: PetWidget, b: PetWidget) -> tuple:
        return (a, b) if id(a) < id(b) else (b, a)

    def _check_standoffs(self) -> None:
        now = time.monotonic()
        pets = self.all_pets
        for i in range(len(pets)):
            for j in range(i + 1, len(pets)):
                a, b = pets[i], pets[j]
                if a.breed == b.breed:
                    continue
                key = self._pair_key(a, b)
                fa, fb = a.foot(), b.foot()
                distance = math.hypot(fa.x() - fb.x(), (fa.y() - fb.y()) * 1.6)
                threshold = (a.width() + b.width()) * .30
                if distance < threshold:
                    if key in self._near_pairs:
                        continue
                    if not self._standoff_seeded or now < self._pair_cooldown.get(key, 0):
                        self._near_pairs.add(key)  # must walk apart before they can meet again
                    elif a.is_free() and b.is_free():
                        self._near_pairs.add(key)
                        self.start_standoff(a, b)
                elif distance > threshold * 1.2:
                    self._near_pairs.discard(key)
        self._standoff_seeded = True
        for standoff in self.standoffs[:]:
            if now >= standoff.end_at:
                self.end_standoff(standoff, timed_out=True)
            else:
                self._animate_standoff(standoff, now)

    def start_standoff(self, a: PetWidget, b: PetWidget) -> Standoff:
        for pet in (a, b):
            pet.vel = QPointF(); pet._action_until = 0
        standoff = Standoff(a, b)
        self.standoffs.append(standoff)
        self._animate_standoff(standoff, time.monotonic())
        return standoff

    def refresh_sound(self) -> None:
        """Apply the sound on/off and volume settings to every running standoff."""
        for standoff in self.standoffs:
            if prefs.values.get('sound', True):
                if standoff.sound is None:
                    standoff.sound = sound.start_standoff_loop()
            else:
                standoff.stop_sound()
        sound.apply_volume()

    def _animate_standoff(self, standoff: Standoff, now: float) -> None:
        a, b = standoff.a, standoff.b
        mid_x = (a.pos_f.x() + a.width() / 2 + b.pos_f.x() + b.width() / 2) / 2
        top = min(a.pos_f.y(), b.pos_f.y())
        standoff.bubble.follow(int(mid_x - 60), int(top + 40))
        if now >= standoff.next_line:
            standoff.bubble.show_text(STANDOFF_LINES[standoff.line % len(STANDOFF_LINES)], 2400)
            standoff.line += random.choice((1, 1, 2))
            standoff.next_line = now + 2.6
        if now >= standoff.next_puff:
            for pet in (a, b):
                head = pet.pos_f + pet.mouth_anchor()
                self.particles.emit_angry(head.x(), head.y() - 25)
            standoff.next_puff = now + 1.5
        if standoff.doomed and now >= standoff.swipe_at:
            if not standoff.swipe_forced:
                standoff.bully.rig.force_style('swipe'); standoff.swipe_forced = True
            elif now >= standoff.swipe_at + 1.2 and standoff.bully.rig.striking():
                self.kill_kitten(standoff.kitten, standoff)
                return
        # Scared stiff: hissing cats poop a lot.
        for pet in (a, b):
            if now >= standoff.next_poop[pet]:
                standoff.next_poop[pet] = now + random.uniform(6, 14)
                if prefs.values['poop_mode'] != 'off' and random.random() < .7:
                    self._deposit_poop(pet, scared=True)

    def end_standoff(self, standoff: Standoff | None, nudge: bool = False, timed_out: bool = False) -> None:
        if standoff is None or standoff not in self.standoffs:
            return
        a, b = standoff.a, standoff.b
        self.standoffs.remove(standoff)
        standoff.close()
        self._pair_cooldown[self._pair_key(a, b)] = time.monotonic() + STANDOFF_COOLDOWN_S
        # Both cats calm down and wander away from each other.
        for pet, rival in ((a, b), (b, a)):
            away = pet.foot() - rival.foot()
            length = math.hypot(away.x(), away.y()) or 1
            pet._enter_wandering()
            pet._target_dir = QPointF(away.x() / length, away.y() / length)
            if nudge and not pet._dragging:
                pet.vel = QPointF(away.x() / length * 3, away.y() / length * 3)
        if timed_out and random.random() < FLEE_CHANCE:
            runner = random.choice((a, b))
            rival = b if runner is a else a
            away = runner.foot() - rival.foot()
            length = math.hypot(away.x(), away.y()) or 1
            runner.flee(QPointF(away.x() / length, away.y() / length))
            self.bubble.show_text(prefs.tr('溜了溜了～', "Nope, I'm out!"), 2000)
        else:
            self.bubble.show_text("Phew...", 1800)

    # --- Death and graves ---

    def kill_kitten(self, kitten: PetWidget, standoff: Standoff | None = None) -> None:
        if kitten not in self.extra_pets:
            return
        if standoff is not None and standoff in self.standoffs:
            self.standoffs.remove(standoff); standoff.close()
        foot = kitten.foot()
        for _ in range(3):
            self.particles.emit_angry(foot.x() + random.randint(-20, 20), foot.y() - 40)
        self._add_grave(foot.x(), foot.y(), kitten.breed, datetime.date.today().isoformat())
        self._near_pairs = {k for k in self._near_pairs if kitten not in k}
        self._pair_cooldown = {k: v for k, v in self._pair_cooldown.items() if kitten not in k}
        self.extra_pets.remove(kitten)
        surface.unregister(kitten)
        kitten.stop(); kitten.close(); kitten.deleteLater()
        self.bubble.show_text(prefs.tr('小猫被一巴掌拍没了……R.I.P', 'The kitten lost the fight… R.I.P'), 3500)
        self.save_state()

    def _add_grave(self, x: float, y: float, breed: str, date: str) -> GraveWidget:
        grave = GraveWidget(x, y, self, breed, date)
        grave.lower()
        self.graves.append(grave)
        return grave

    def remove_grave(self, grave: GraveWidget) -> None:
        if grave in self.graves:
            self.graves.remove(grave)
            surface.unregister(grave); grave.close(); grave.deleteLater()

    # --- Neutering ---

    def neuter(self, pet: PetWidget) -> None:
        if pet.neutered:
            return
        pet.neutered = True
        center = pet.frameGeometry().center()
        self.particles.emit_heart(center.x(), center.y() - 20)
        self.bubble.show_text(prefs.tr(f'{pet.breed_label()}绝育好啦～', f'{pet.breed_label()} is neutered~'), 2000)

    def neuter_all(self) -> None:
        for pet in self.all_pets:
            pet.neutered = True
        self.bubble.show_text(prefs.tr('全家都绝育啦，不会再有小猫了', 'Everyone is neutered — no more kittens'), 2500)

    # --- Adoption ---

    def _place_apart(self, pet: PetWidget) -> None:
        rect = surface.bounds()
        others = [p for p in self.all_pets if p is not pet]
        best, best_score = None, -1.0
        for _ in range(40):
            x = random.uniform(0, max(0, rect.width() - pet.width()))
            y = random.uniform(0, max(0, rect.height() - pet.height()))
            foot = QPointF(x + pet.width() * .5, y + pet.height() * .8)
            score = min((math.hypot(foot.x() - o.foot().x(), foot.y() - o.foot().y()) for o in others), default=1e9)
            if score > best_score:
                best, best_score = (x, y), score
        pet.place(*best)

    def adopt(self, breed: str | None = None) -> PetWidget | None:
        breed = breed if breed in ADOPTABLE else random.choice(ADOPTABLE)
        pet = PetWidget(self, breed=breed)
        self._place_apart(pet)
        self.extra_pets.append(pet)
        self._grace(pet)
        center = pet.frameGeometry().center()
        for _ in range(6):
            self.particles.emit_heart(center.x() + random.randint(-30, 30), center.y() + random.randint(-30, 20))
        self.bubble.show_text(prefs.tr(f'领养了一只{breed_name(breed, True)}！',
                                       f'Adopted a {breed_name(breed, False).lower()}!'), 3000)
        return pet

    def _grace(self, pet: PetWidget, seconds: float = 4.0) -> None:
        """A newcomer gets a moment before it can start a standoff."""
        until = time.monotonic() + seconds
        for other in self.all_pets:
            if other is not pet:
                self._pair_cooldown[self._pair_key(pet, other)] = until

    def rehome(self, pet: PetWidget) -> None:
        if pet not in self.extra_pets:
            return
        self.end_standoff(pet.standoff)
        self._near_pairs = {k for k in self._near_pairs if pet not in k}
        self._pair_cooldown = {k: v for k, v in self._pair_cooldown.items() if pet not in k}
        self.extra_pets.remove(pet)
        surface.unregister(pet)
        pet.stop(); pet.close(); pet.deleteLater()
        self.bubble.show_text(prefs.tr('它去新家啦，拜拜～', 'Off to a new home. Bye~'), 2500)

    def set_main_breed(self, breed: str) -> None:
        self.end_standoff(self.pet.standoff)
        self.pet.set_breed(breed)

    # --- Bubble follow ---

    def _update_bubble_pos(self) -> None:
        pos = self.pet.pos()
        self.bubble.follow(pos.x(), pos.y())

    # --- Persistence ---

    def _load_state(self) -> None:
        raw = load_json_safe(STATE_FILE, default={})
        if not isinstance(raw, dict) or not raw:
            return
        state = validate_state(raw)
        self.hunger = state["hunger"]
        self.xp = state["xp"]
        self.level = state["level"]
        self.total_eats = state["total_eats"]
        self.total_pets = state["total_pets"]
        self.star_eats = state["star_eats"]
        self.unlocked_achievements = set(state["achievements"])
        self.pet.scale_factor = state["scale_factor"]
        self.pet.apply_scale()
        import surface
        for pet in self.extra_pets:
            surface.unregister(pet); pet.stop(); pet.close()
        self.extra_pets.clear()
        companions = raw.get('companions', [])
        if isinstance(companions, list):
            for entry in companions:
                if not isinstance(entry, dict): continue
                breed = entry.get('breed') if entry.get('breed') in ADOPTABLE else 'calico'
                baby = PetWidget(self, is_baby=bool(entry.get('baby', True)), breed=breed)
                try: baby.scale_factor = max(.3, min(1.65, float(entry.get('scale', .6))))
                except (TypeError, ValueError): baby.scale_factor = .6
                baby.apply_scale(); surface.fit(baby)
                baby.neutered = bool(entry.get('neutered', False))
                self.extra_pets.append(baby)
                self._place_apart(baby)
        self.pet.neutered = bool(raw.get('main_neutered', False))
        for grave in self.graves[:]:
            surface.unregister(grave); grave.close(); self.graves.remove(grave)
        saved_graves = raw.get('graves', [])
        if isinstance(saved_graves, list):
            rect = surface.bounds()
            for entry in saved_graves:
                try:
                    gx, gy = float(entry['x']), float(entry['y'])
                except (TypeError, ValueError, KeyError):
                    continue
                if math.isfinite(gx) and math.isfinite(gy):
                    breed = entry.get('breed') if entry.get('breed') in ADOPTABLE else 'calico'
                    self._add_grave(max(0, min(1, gx)) * rect.width(), max(0, min(1, gy)) * rect.height(),
                                    breed, str(entry.get('date', ''))[:10])
        for poop in self.poops[:]:
            surface.unregister(poop); poop.close(); self.poops.remove(poop)
        saved_poops = raw.get('poops', [])
        if isinstance(saved_poops, list):
            rect = surface.bounds()
            for entry in saved_poops:
                try:
                    fx, fy = float(entry['x']), float(entry['y'])
                except (TypeError, ValueError, KeyError):
                    continue
                if math.isfinite(fx) and math.isfinite(fy):
                    self._add_poop(max(0, min(1, fx)) * rect.width(), max(0, min(1, fy)) * rect.height())

    def save_state(self) -> None:
        state = {
            "hunger": self.hunger,
            "xp": self.xp,
            "level": self.level,
            "total_eats": self.total_eats,
            "total_pets": self.total_pets,
            "star_eats": self.star_eats,
            "scale_factor": self.pet.scale_factor,
            "achievements": list(self.unlocked_achievements),
            "companions": [{'baby': pet.is_baby, 'scale': pet.scale_factor, 'breed': pet.breed, 'neutered': pet.neutered}
                           for pet in self.extra_pets],
            "main_neutered": self.pet.neutered,
            "poops": self._poop_fractions(),
            "graves": self._grave_records(),
        }
        save_json_safe(STATE_FILE, state)
        self._update_ranking()

    def _grave_records(self) -> list:
        rect = surface.bounds()
        width, height = max(1, rect.width()), max(1, rect.height())
        return [{'x': round((g.x() + g.width() / 2) / width, 4), 'y': round((g.y() + g.height() - 6) / height, 4),
                 'breed': g.breed, 'date': g.date} for g in self.graves]

    def _poop_fractions(self) -> list:
        rect = surface.bounds()
        width, height = max(1, rect.width()), max(1, rect.height())
        return [{'x': round(p.x() / width, 4), 'y': round(p.y() / height, 4)} for p in self.poops]

    def _update_ranking(self) -> None:
        ranking = load_json_safe(RANKING_FILE, default=[])
        if not isinstance(ranking, list):
            ranking = []
        # Drop our previous entry and any malformed (non-dict) rows.
        ranking = [
            e for e in ranking
            if isinstance(e, dict) and e.get("username") != self.username
        ]
        ranking.append({
            "username": self.username,
            "size": round(self.pet.scale_factor * 100, 1),
            "level": self.level,
        })
        save_json_safe(RANKING_FILE, ranking)
