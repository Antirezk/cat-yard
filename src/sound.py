"""Looping standoff sound. Every active standoff gets its own looping copy, so
several hissing pairs overlap. Volume and on/off come from preferences.

The bundled sounds/standoff.wav can be replaced by putting a file with the same
name in a ``sounds`` folder next to the EXE.
"""
import logging
import sys
from pathlib import Path

import preferences as prefs

try:
    from PyQt5.QtCore import QUrl
    from PyQt5.QtMultimedia import QSoundEffect
except Exception:  # QtMultimedia missing: run silently
    logging.warning('QtMultimedia unavailable; standoff sound disabled', exc_info=True)
    QSoundEffect = None

_loops = []

def _find(name):
    roots = [Path.cwd(), Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))]
    for root in roots:
        path = root / 'sounds' / name
        if path.is_file():
            return path
    return None

def _volume():
    return max(0, min(100, prefs.values.get('volume', 70))) / 100

class Loop:
    """One looping playback; call stop() when the standoff ends."""

    def __init__(self, path):
        self.effect = QSoundEffect()
        self.effect.setSource(QUrl.fromLocalFile(str(path)))
        self.effect.setLoopCount(QSoundEffect.Infinite)
        self.effect.setVolume(_volume())
        self.effect.play()
        _loops.append(self)
        logging.info('standoff sound loop started (%d playing)', len(_loops))

    def stop(self):
        if self in _loops:
            _loops.remove(self)
        try:
            self.effect.stop()
            self.effect.deleteLater()
        except RuntimeError:
            pass

def start_standoff_loop():
    """Start a looping standoff sound, or return None when muted/unavailable."""
    if QSoundEffect is None or not prefs.values.get('sound', True):
        return None
    path = _find('standoff.wav')
    if path is None:
        return None
    try:
        return Loop(path)
    except Exception:
        logging.exception('Could not play %s', path)
        return None

def apply_volume():
    for loop in list(_loops):
        loop.effect.setVolume(_volume())

def stop_all():
    for loop in list(_loops):
        loop.stop()
