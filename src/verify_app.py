"""Opt-in real Windows integration checks; all test state uses --data-dir."""
import json
import math
import statistics
import time
import traceback
from pathlib import Path
from PyQt5.QtCore import QTimer, Qt, QPoint, QPointF, QEvent
from PyQt5.QtTest import QTest
from PyQt5.QtGui import QImage, QPainter, QMouseEvent
import preferences as prefs
import surface
import wand
from cat_art import CatRig

def schedule_checks(app, window, ctrl, root):
    results = []
    original = prefs.values.copy()
    def check(name, condition):
        if not condition: raise AssertionError(name)
        results.append(name)
    def finish(error=None):
        wand.current.override = (False, QPoint())
        wand.current.restore()
        prefs.values.update(original); prefs.save()
        (root / 'verification.json').write_text(json.dumps(dict(ok=error is None, checks=results, error=error), ensure_ascii=False, indent=2), encoding='utf-8')
        app.exit(1 if error else 0)
    def run():
        try:
            for timer in ctrl._timers: timer.stop()
            ctrl.pet._tick_timer.stop()
            wand.current.timer.stop()
            check('cat rig is active', isinstance(ctrl.pet.rig, CatRig))
            check('pet is embedded', ctrl.pet.parentWidget() is window.arena)
            check('no Kirby sprite is loaded', not hasattr(ctrl.pet, '_right_movie'))
            window.poop.setCurrentIndex(0); window.meals.setValue(2); window.chance.setValue(100)
            ctrl.spawn_snack(); ctrl._eat(ctrl.snacks[-1])
            check('meal threshold respected', not ctrl.poops and not getattr(ctrl, '_poop_pending', False))
            ctrl.spawn_snack(); ctrl._eat(ctrl.snacks[-1])
            check('squat animation precedes poop', ctrl._poop_pending and ctrl.pet._action == 'poop')
            QTimer.singleShot(1650, after_poop)
        except Exception: finish(traceback.format_exc())
    def after_poop():
        try:
            check('poop deposited after squat', len(ctrl.poops) == 1)
            window.clean_all()
            check('poop cleanup and registry removal', not ctrl.poops and not any(v == 'poop' for v in surface.widgets.values()))
            window.chance.setValue(0)
            for _ in range(4): ctrl.spawn_snack(); ctrl._eat(ctrl.snacks[-1])
            check('zero chance produces no poop', not ctrl._poop_pending)
            window.poop.setCurrentIndex(2)
            for _ in range(4): ctrl.spawn_snack(); ctrl._eat(ctrl.snacks[-1])
            check('off mode disables automatic poop', not ctrl._poop_pending)
            window.lang.setCurrentIndex(1); ctrl.bubble.show_text('Caught you! Nom nom~')
            check('English thoughts and UI', ctrl.bubble._text == 'Caught you! Nom nom~' and 'Feed' in window.feed.text())
            window.lang.setCurrentIndex(0); ctrl.bubble.show_text('Caught you! Nom nom~')
            check('Chinese thoughts and UI', ctrl.bubble._text == '抓到啦！抱住啃啃～' and '喂食' in window.feed.text())
            for i, name in [(2, 'top'), (1, 'desktop'), (0, 'window')]:
                ctrl.spawn_snack(); ctrl._deposit_poop()
                window.modes.setCurrentIndex(i)
                check(name + ' mode selected', surface.mode == name)
                objects = [ctrl.pet, ctrl.bubble, ctrl.particles] + ctrl.snacks + ctrl.poops
                if name == 'top': check('all game objects topmost', all(w.windowFlags() & Qt.WindowStaysOnTopHint for w in objects))
                elif name == 'desktop':
                    user, host = surface._api(), surface.desktop_host()
                    check('all game objects on Explorer desktop', all(user.GetParent(int(w.winId())) == host for w in objects))
                else: check('all game objects back in arena', all(w.parentWidget() is window.arena for w in objects))
            window.clean_all()
            for snack in ctrl.snacks[:]: ctrl._remove_snack(snack)
            ctrl.pet._action_until = 0
            ctrl.pet.pos_f = QPointF(70, 55); ctrl.pet.move(70, 55)
            target = window.arena.mapToGlobal((ctrl.pet.pos_f + ctrl.pet.mouth_anchor()).toPoint())
            wand.current.override = (True, target)
            wand.current.poll()
            check('Ctrl+Alt state activates feather cursor', wand.current.active and wand.current.marker.exists())
            check('cursor crash-recovery helper started', wand.current.guard is not None)
            ctrl.pet._tick()
            check('cat catches and hugs pointer', ctrl.pet._hugging)
            for _ in range(60): ctrl.pet.rig.advance(1/60, 0, 1, 'cuddle', (0, 0))
            check('hug pose eases in continuously', ctrl.pet.rig.pose.cuddle > .98)
            wand.current.override = (False, target); wand.current.poll()
            check('release restores cursor and removes marker', not wand.current.active and not wand.current.marker.exists())
            ctrl.pet._tick()
            check('release exits hugging', not ctrl.pet._hugging)
            pets = ctrl.total_pets
            QTest.mouseClick(ctrl.pet, Qt.LeftButton)
            check('click still pets cat', ctrl.total_pets == pets + 1)
            friend = ctrl.adopt('black' if ctrl.pet.breed != 'black' else 'white')
            check('adoption adds companion cat', len(ctrl.extra_pets) == 1 and friend.breed != ctrl.pet.breed)
            standoff = ctrl.start_standoff(ctrl.pet, friend)
            for _ in range(40): ctrl.pet._tick(); friend._tick()
            check('different breeds enter hissing standoff', ctrl.pet.rig.pose.hiss > .5 and friend.rig.pose.hiss > .5)
            check('standoff holds without user action', ctrl.standoffs == [standoff])
            middle = QPoint(friend.width() // 2, friend.height() // 2)
            for kind, offset, button, buttons in [(QEvent.MouseButtonPress, 0, Qt.LeftButton, Qt.LeftButton),
                                                  (QEvent.MouseMove, 20, Qt.NoButton, Qt.LeftButton),
                                                  (QEvent.MouseMove, 60, Qt.NoButton, Qt.LeftButton),
                                                  (QEvent.MouseButtonRelease, 60, Qt.LeftButton, Qt.NoButton)]:
                point = middle + QPoint(offset, 0)
                app.sendEvent(friend, QMouseEvent(kind, QPointF(point), QPointF(friend.mapToGlobal(point)), button, buttons, Qt.NoModifier))
            check('dragging one cat ends the standoff', not ctrl.standoffs and ctrl.pet.standoff is None and friend.standoff is None)
            ctrl.set_main_breed(friend.breed)
            ctrl._breed(ctrl.pet, ctrl.extra_pets[0])
            check('inherited breeding adds kitten', len(ctrl.extra_pets) == 2 and ctrl.extra_pets[-1].is_baby)
            ctrl._cpu_tick(); check('CPU reactions remain available', isinstance(ctrl.cpu_percent, (int, float)))
            ctrl._deposit_poop(); ctrl._deposit_poop()
            ctrl.save_state(); ctrl._load_state(); check('cat save and journal written', (root / 'cat_state.json').exists() and (root / 'cat_records.json').exists())
            check('uncleaned poop survives save and reload', len(ctrl.poops) == 2)
            check('companion breeds survive reload', [p.breed for p in ctrl.extra_pets] == [e['breed'] for e in json.loads((root / 'cat_state.json').read_text(encoding='utf-8'))['companions']])
            window.clean_all()
            ctrl.set_main_breed(prefs.values['breed'])
            # All actions must produce distinct, valid frames with low paint cost.
            timings, signatures = [], []
            for action in ['idle', 'chase', 'eat', 'poop', 'sleep', 'cuddle', 'held', 'hiss']:
                rig = CatRig()
                image = QImage(240, 180, QImage.Format_ARGB32)
                for _ in range(30):
                    rig.advance(1/60, 140 if action == 'chase' else 0, 1, action)
                    image.fill(Qt.transparent); painter = QPainter(image)
                    start = time.perf_counter(); rig.paint(painter, 240, 180); painter.end()
                    timings.append((time.perf_counter() - start) * 1000)
                signatures.append(bytes(image.bits().asstring(image.byteCount())))
            check('eight distinct articulated animation states', len(set(signatures)) == 8)
            median = statistics.median(timings)
            check('single-cat paint budget below 16ms', median < 16)
            (root / 'performance.json').write_text(json.dumps(dict(median_paint_ms=median, p95_paint_ms=sorted(timings)[int(len(timings)*.95)], target_fps=60), indent=2))
            for pet in ctrl.extra_pets:
                surface.unregister(pet); pet.stop(); pet.close()
            ctrl.extra_pets.clear()
            ctrl.pet.rig = CatRig()
            ctrl.pet.pos_f = QPointF(85, 50); ctrl.pet.move(85, 50)
            ctrl.particles._particles.clear(); ctrl.bubble._text = ''; ctrl.bubble._opacity = 0
            window.grab().save(str(root / 'preview-compact.png'))
            window.tab_buttons[1].click(); app.processEvents()
            window.grab().save(str(root / 'preview-zh.png'))
            window.lang.setCurrentIndex(1); app.processEvents()
            window.grab().save(str(root / 'preview-en.png'))
            window.poop.setCurrentIndex(1)
            check('configured minute interval is applied', window.poop_timer.interval() == window.minutes.value() * 60000)
            window.poop_timer.setSingleShot(True); window.poop_timer.start(50)
            QTimer.singleShot(1750, finish_timer)
        except Exception: finish(traceback.format_exc())
    def finish_timer():
        try:
            check('interval mode deposits poop', len(ctrl.poops) > 0)
            window.clean_all()
            prefs.save(); recorded = prefs.values.copy(); prefs.values.update(prefs.DEFAULTS); prefs.load()
            check('preferences survive reload', prefs.values == recorded)
            finish()
        except Exception: finish(traceback.format_exc())
    QTimer.singleShot(400, run)
