"""Shared constants, configuration, and utility functions for the Kirby desktop pet."""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt5.QtCore import QRect

__version__ = "2.4.0"

logger = logging.getLogger(__name__)

# --- File paths ---
STATE_FILE = "cat_state.json"
RANKING_FILE = "cat_records.json"

# --- UI constants ---
MOOD_EMOJIS = {
    "happy": "😊",
    "hungry": "😫",
    "sleeping": "💤",
    "excited": "🤩",
}

# --- Food definitions: (emoji, name, hunger_restore, xp_reward) ---
FOODS = [
    ('🐟', 'Fish', 18, 10), ('🍗', 'Chicken', 25, 15), ('🥣', 'Kibble', 28, 20),
    ('🐠', 'Tuna', 24, 25), ('🍣', 'Salmon', 22, 30), ('🦴', 'Cat Treat', 10, 12),
    ('⭐', 'Star Treat', 8, 50),
]

# --- Achievement definitions ---
ACHIEVEMENTS = [
    {"id": "first_bite", "name": "First Bite", "desc": "Eat your first food", "eats_req": 1},
    {"id": "hungry_boy", "name": "Hungry Boy", "desc": "Eat 10 foods", "eats_req": 10},
    {"id": "level5", "name": "Growing Up", "desc": "Reach level 5", "level_req": 5},
    {"id": "level10", "name": "Big Cat", "desc": "Reach level 10", "level_req": 10},
    {"id": "level25", "name": "Cat Royalty", "desc": "Reach level 25", "level_req": 25},
    {"id": "glutton", "name": "Glutton", "desc": "Eat 50 foods", "eats_req": 50},
    {"id": "legend", "name": "Legend", "desc": "Eat 200 foods", "eats_req": 200},
    {"id": "pet_lover", "name": "Pet Lover", "desc": "Pet Kirby 20 times", "pets_req": 20},
    {"id": "star_hunter", "name": "Star Hunter", "desc": "Eat 10 Star Candies", "star_req": 10},
]

# --- Gameplay constants ---
EATS_UNTIL_POOP = 3
POOP_SPAWN_CHANCE = 0.4
RANDOM_EVENT_CHANCE = 0.3
CPU_HIGH_THRESHOLD = 80
MAX_KIRBYS = 6
BREEDING_DISTANCE = 50
BREED_COOLDOWN_FRAMES = 60
POOP_CLEAN_XP = 5
BREED_XP = 30
STAR_FIND_XP = 10
MAX_HUNGER = 100
HUNGER_SLEEP_THRESHOLD = 60
HUNGER_HUNGRY_THRESHOLD = 80
HUNGER_EXCITED_THRESHOLD = 30
HUNGER_AUTO_FEED_THRESHOLD = 90
HUNGER_STARVING_THRESHOLD = 95
MAX_POOPS = 60
MAX_SNACKS = 10
MAX_PARTICLES = 500
MAX_LEVELUPS_PER_TICK = 50  # safety guard against XP-driven infinite loops

# --- Physics constants ---
PARTICLE_GRAVITY = 0.08
PARTICLE_DECAY_RANGE = (0.015, 0.035)
PARTICLE_TICK_MS = 16
PARTICLE_SPEED_RANGE = (1.5, 4.0)  # initial random speed of a burst particle
PARTICLE_UPWARD_BOOST = 2.0  # extra upward velocity so particles arc up first
PARTICLE_MIN_LIFE = 0.001  # below this a particle is considered dead

# --- Timer intervals (ms) ---
HUNGER_TICK_MS = 1000
HUNGER_RATE = 0.08
AUTO_SAVE_MS = 30_000
MOOD_TICK_MS = 2000
SLEEP_THRESHOLD_S = 60
TRAY_REFRESH_MS = 1000
EVENT_TICK_MS = 15_000
CPU_TICK_MS = 5000
BREED_CHECK_MS = 500
BUBBLE_TICK_MS = 16
FADE_TICK_MS = 30

# --- Pet physics ---
PET_FPS = 60
PET_MAX_SPEED = 2.2
PET_CHASE_MAX_SPEED = 4.0
PET_ACCELERATION = 0.08
PET_FRICTION = 0.96
PET_THROW_FRICTION = 0.985
PET_THROW_GRAVITY = 0.15
PET_FLIP_SPEED_THRESHOLD = 0.3
PET_THROW_STOP_SPEED = 0.5
PET_MAX_THROW_SPEED = 18.0
PET_MIN_THROW_SPEED = 2.0
PET_WANDER_NUDGE_CHANCE = 0.02
PET_REST_SWAY_CHANCE = 0.03
PET_CHASE_ACCEL_MULTIPLIER = 1.8
PET_CHASE_STEERING = 0.12
PET_BOUNCE_FACTOR_NORMAL = 0.5
PET_BOUNCE_FACTOR_THROWN = 0.6
PET_MAX_THROW_BOUNCES = 3
PET_SLEEP_FRICTION = 0.92
PET_REST_FRICTION = 0.94
PET_WANDER_NUDGE_SIGMA = 0.3  # gaussian spread of a wander course-correction
PET_REST_SWAY_SIGMA = 0.05  # gaussian spread of a resting sway
PET_THROW_VELOCITY_SCALE = 16.0  # drag pixels/ms -> throw velocity multiplier
PET_CLICK_THRESHOLD_PX = 5  # drag shorter than this counts as a click (pet)
PET_DRAG_HISTORY_LEN = 6  # mouse samples kept to estimate throw velocity

# Growth formula: growth = base / (1 + (level - 1) * diminish)
PET_GROWTH_BASE = 0.012
PET_GROWTH_DIMINISH = 0.05

# Scale factors
ADULT_SCALE = 1.0
BABY_SCALE = 0.5

# Baby overrides
BABY_MAX_SPEED = 3.0
BABY_CHASE_MAX_SPEED = 5.0
BABY_ACCELERATION = 0.12
BABY_SPAWN_MARGIN = 50  # keep a newborn this far from the screen edge
BABY_SPAWN_VX_RANGE = (-3.0, 3.0)  # horizontal launch velocity at birth
BABY_SPAWN_VY = -4.0  # upward launch velocity at birth

# State timers (frames)
WANDER_DURATION = (150, 420)
IDLE_DURATION = (30, 120)
REST_DURATION = (90, 240)
INIT_WANDER_DURATION = (120, 360)

# --- Snack ---
SNACK_SPAWN_MARGIN = 60
PET_INIT_MARGIN = 100

# --- Ranking board ---
RANKING_WINDOW_SIZE = (420, 500)
RANKING_REFRESH_MS = 5000
RANKING_ROW_HEIGHT = 44

# --- Username ---
MAX_USERNAME_LENGTH = 20

# --- Menu-bar tray icon ---
TRAY_ICON_SIZE = 22  # logical px
TRAY_ICON_RETINA_SCALE = 2  # render at 2x for retina crispness
TRAY_ICON_FONT_SIZE = 14  # emoji point size

# --- Random-event impulse velocities (px/frame) ---
EVENT_TRIP_HOP = -3.0  # upward hop when Kirby trips
EVENT_DANCE_HSPEED = 4.0  # horizontal speed of a dance step
EVENT_DANCE_HOP = -2.0  # upward hop of a dance step
EVENT_SNEEZE_PUSH = 3.0  # recoil speed from a sneeze
EVENT_SNEEZE_HOP = -1.0  # upward hop from a sneeze
EVENT_HICCUP_HOP = -2.5  # upward hop from a hiccup


def xp_for_level(level: int) -> int:
    """Return XP required to reach the next level.

    Args:
        level: The current level (0-based indexing supported).

    Returns:
        Positive integer XP threshold, scaling exponentially.
    """
    return int(50 * (1.3 ** level))


def _coerce_int(value: Any, default: int = 0) -> int:
    """Coerce *value* to ``int``, falling back to *default* on bad input.

    Unlike a bare ``int(value)`` this never raises, so a corrupted or
    hand-edited save file (e.g. ``{"hunger": "abc"}``) cannot crash state
    loading.

    Args:
        value: Any value to coerce.
        default: Returned when *value* cannot be converted.

    Returns:
        The integer value, or *default*.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_achievement_met(
    ach: dict[str, Any],
    *,
    total_eats: int = 0,
    level: int = 0,
    total_pets: int = 0,
    star_eats: int = 0,
) -> bool:
    """Check whether an achievement's requirements are satisfied.

    Args:
        ach: Achievement definition dict with optional ``*_req`` keys.
        total_eats: Lifetime food count.
        level: Current player level.
        total_pets: Lifetime pet-interaction count.
        star_eats: Lifetime Star Candy count.

    Returns:
        ``True`` if every requirement in *ach* is met.
    """
    if ach.get("eats_req", 0) > 0 and total_eats < ach["eats_req"]:
        return False
    if ach.get("level_req", 0) > 0 and level < ach["level_req"]:
        return False
    if ach.get("pets_req", 0) > 0 and total_pets < ach["pets_req"]:
        return False
    if ach.get("star_req", 0) > 0 and star_eats < ach["star_req"]:
        return False
    return True


def validate_state(state: Any) -> dict[str, Any]:
    """Validate and sanitize loaded game state.

    Coerces types, clamps numeric ranges, filters invalid achievements,
    and handles ``NaN`` / ``Inf`` scale factors gracefully.

    Args:
        state: Raw dict loaded from JSON (or any other value).

    Returns:
        Cleaned dict with guaranteed-valid fields, or ``{}`` if
        *state* is not a dict.
    """
    if not isinstance(state, dict):
        return {}

    cleaned: dict[str, Any] = {}
    cleaned["hunger"] = max(0, min(MAX_HUNGER, _coerce_int(state.get("hunger", 0))))
    cleaned["xp"] = max(0, _coerce_int(state.get("xp", 0)))
    cleaned["level"] = max(1, _coerce_int(state.get("level", 1), default=1))
    cleaned["total_eats"] = max(0, _coerce_int(state.get("total_eats", 0)))
    cleaned["total_pets"] = max(0, _coerce_int(state.get("total_pets", 0)))
    cleaned["star_eats"] = max(0, _coerce_int(state.get("star_eats", 0)))

    try:
        scale = float(state.get("scale_factor", 1.0))
        if not math.isfinite(scale):
            scale = 1.0
    except (TypeError, ValueError):
        scale = 1.0
    cleaned["scale_factor"] = max(0.1, min(10.0, scale))

    achievements = state.get("achievements", [])
    if not isinstance(achievements, list):
        achievements = []
    valid_ids = {a["id"] for a in ACHIEVEMENTS}
    cleaned["achievements"] = [
        a for a in achievements if isinstance(a, str) and a in valid_ids
    ]
    return cleaned


def screen_geometry() -> "QRect":
    """Return the primary screen's geometry.

    Wraps ``QApplication.primaryScreen()``, which is typed as optional and
    can be ``None`` when no display is attached. In that case a zero-sized
    ``QRect`` is returned so callers never crash on ``None.geometry()``.

    Returns:
        The primary screen geometry, or an empty ``QRect`` if unavailable.
    """
    import surface
    return surface.bounds()


def resource_path(relative_path: str) -> str:
    """Return absolute path to a bundled resource.

    Works for both development (source tree) and PyInstaller one-file
    builds (``sys._MEIPASS``).

    Args:
        relative_path: Path relative to the project root (e.g.
            ``"images/Y3il.gif"``).

    Returns:
        Absolute filesystem path. Logs a warning if the file does not exist.
    """
    base_path: str | None = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    full_path = os.path.join(base_path, relative_path)
    if not os.path.exists(full_path):
        logger.warning("Resource not found: %s", full_path)
    return full_path


def load_json_safe(filepath: str, default: Any = None) -> Any:
    """Load a JSON file with error handling.

    Args:
        filepath: Path to the JSON file.
        default: Value returned when the file is missing or corrupt.
            Defaults to ``{}``.

    Returns:
        Parsed JSON data, or *default* on any failure.
    """
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.error("Failed to load %s: %s", filepath, exc)
        return default


def save_json_safe(filepath: str, data: Any) -> None:
    """Write *data* to a JSON file atomically.

    Writes to a temporary file first, then renames to avoid corruption
    on crash. Cleans up the temp file on failure.

    Args:
        filepath: Destination JSON file path.
        data: JSON-serializable data to persist.
    """
    tmp_path = filepath + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, filepath)
    except (OSError, TypeError, ValueError) as exc:
        # OSError: disk/permission failure. TypeError/ValueError: data was
        # not JSON-serializable. Either way, log and clean up the temp file.
        logger.error("Failed to save %s: %s", filepath, exc)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
