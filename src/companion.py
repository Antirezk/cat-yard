"""猫猫小院 — bilingual Windows app around the cat game controller.

Layout: a stats bar on top, the yard (play arena) on the left with an action
bar under it, and a sidebar with three tabs: cats roster, settings, journal.
"""
import logging
import os
from pathlib import Path
import sys
from PyQt5.QtCore import Qt, QTimer, QLockFile, QSize, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFont, QPainter, QColor, QDesktopServices
from PyQt5.QtWidgets import (QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QToolButton, QComboBox, QSpinBox, QFormLayout, QLineEdit, QCheckBox, QSlider,
    QSystemTrayIcon, QMenu, QMessageBox, QScrollArea, QStackedWidget, QButtonGroup, QProgressBar,
    QSizePolicy)
import preferences as prefs
from preferences import tr
import surface
from cat_art import ADOPTABLE, BREEDS, CatRig, breed_name

FEEDBACK_EMAIL = 'antirezk@gmail.com'
BREED_ORDER = ['calico', 'black', 'white', 'tabby', 'orange', 'siamese', 'ragdoll']
MODES = ['window', 'desktop', 'top']
POOP_MODES = ['food', 'timer', 'off']
STATUS = {'walk': ('漫步中', 'Roaming'), 'sleep': ('睡觉 Zzz', 'Sleeping'), 'standoff': ('⚠ 应激对峙中', '⚠ Standoff!'),
          'held': ('被拎着', 'Held'), 'flee': ('逃跑中！', 'Running away!'), 'eat': ('吃饭中', 'Eating'),
          'poop': ('拉屎中', 'Pooping'), 'pet': ('被摸摸', 'Being petted')}

STYLE = '''
QWidget { color: #4a3b30; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 9pt; }
QWidget#root { background: #f7f1e8; }
QFrame#header { background: #fffaf3; border: 1px solid #eadfce; border-radius: 12px; }
QLabel#title { font-size: 15pt; font-weight: bold; color: #b9602c; }
QLabel[class="chip"] { background: #f4e9da; border-radius: 9px; padding: 3px 9px; color: #6b5444; }
QLabel#alert { background: #fde4d6; color: #a2421c; border-radius: 9px; padding: 5px 10px; font-weight: bold; }
QLabel#tip { color: #9a8a7a; font-size: 8pt; }
QFrame#arena { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f2f6ec, stop:1 #e3ecd8);
               border: 1px solid #d5dfc8; border-radius: 14px; }
QFrame#side, QFrame#card { background: #fffaf3; border: 1px solid #eadfce; border-radius: 12px; }
QFrame#row { background: #ffffff; border: 1px solid #efe4d4; border-radius: 10px; }
QFrame#row[alert="true"] { background: #fff1ea; border: 1px solid #f2b79a; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #e3d5c2; border-radius: 9px; padding: 7px 12px; }
QPushButton:hover, QToolButton:hover { background: #fff1e4; border-color: #e7b48f; }
QPushButton#primary, QToolButton#primary { background: #e98a4f; color: white; border: 1px solid #d6743a; font-weight: bold; }
QPushButton#primary:hover, QToolButton#primary:hover { background: #f09a62; }
QPushButton#tab { background: transparent; border: none; border-radius: 8px; padding: 6px 4px; color: #8a7462; }
QPushButton#tab:checked { background: #f4e2cf; color: #b9602c; font-weight: bold; }
QPushButton#mini { padding: 3px 8px; border-radius: 7px; font-size: 8pt; }
QComboBox, QSpinBox, QLineEdit { background: white; border: 1px solid #e3d5c2; border-radius: 7px; padding: 4px 6px; }
QLabel[class="section"] { font-weight: bold; color: #b9602c; padding-top: 6px; }
QProgressBar { background: #f1e6d7; border: none; border-radius: 5px; height: 10px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #e98a4f; border-radius: 5px; }
QSlider::groove:horizontal { height: 6px; background: #f1e6d7; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #e98a4f; border-radius: 3px; }
QSlider::handle:horizontal { background: white; border: 1px solid #d6743a; width: 14px; margin: -5px 0; border-radius: 7px; }
QScrollArea { border: none; background: transparent; }
'''

_avatars = {}

def avatar(breed, size=QSize(64, 48)):
    """A tiny standing portrait of a breed, rendered with the real cat rig."""
    key = (breed, size.width())
    if key not in _avatars:
        pixmap = QPixmap(size * 2); pixmap.setDevicePixelRatio(2); pixmap.fill(Qt.transparent)
        rig = CatRig(breed)
        for _ in range(30): rig.advance(1 / 60, 0, 1, 'idle')
        rig.pose.blink = 0
        painter = QPainter(pixmap); rig.paint(painter, size.width(), size.height(), shadow=False); painter.end()
        _avatars[key] = pixmap
    return _avatars[key]


class Arena(QFrame):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        surface.resize_arena()


class CatRow(QFrame):
    """One cat in the roster: portrait, name, live status and actions."""

    def __init__(self, window, pet, index):
        super().__init__()
        self.setObjectName('row')
        self.window, self.pet = window, pet
        layout = QHBoxLayout(self); layout.setContentsMargins(6, 4, 6, 4); layout.setSpacing(6)
        self.portrait = QLabel(); self.portrait.setFixedSize(64, 48)
        layout.addWidget(self.portrait)
        text = QVBoxLayout(); text.setSpacing(0)
        self.name = QLabel(); self.name.setStyleSheet('font-weight: bold;')
        self.state = QLabel(); self.state.setStyleSheet('color: #8a7462; font-size: 8pt;')
        text.addWidget(self.name); text.addWidget(self.state)
        layout.addLayout(text, 1)
        self.pet_button = QPushButton(); self.pet_button.setObjectName('mini')
        self.pet_button.clicked.connect(lambda: window.ctrl.pet_kirby(pet))
        layout.addWidget(self.pet_button)
        self.neuter_button = QPushButton('✂'); self.neuter_button.setObjectName('mini'); self.neuter_button.setFixedWidth(30)
        self.neuter_button.clicked.connect(lambda: (window.ctrl.neuter(pet), self.refresh()))
        layout.addWidget(self.neuter_button)
        self.extra = QPushButton(); self.extra.setObjectName('mini')
        self.extra.clicked.connect(self.extra_action)
        layout.addWidget(self.extra)
        self.index = index
        self.refresh(force=True)

    def extra_action(self):
        ctrl = self.window.ctrl
        if self.pet.standoff is not None:
            ctrl.end_standoff(self.pet.standoff, nudge=True)
        elif self.pet is not ctrl.pet:
            ctrl.rehome(self.pet)
        self.window.refresh_roster()

    def refresh(self, force=False):
        pet, ctrl = self.pet, self.window.ctrl
        if force or self.portrait.property('breed') != pet.breed:
            self.portrait.setPixmap(avatar(pet.breed)); self.portrait.setProperty('breed', pet.breed)
        role = tr('主猫', 'Main') if pet is ctrl.pet else (tr('小猫', 'Kitten') if pet.is_baby else f'#{self.index}')
        self.name.setText(f'{pet.breed_label()} · {role}')
        status = pet.status()
        state = tr(*STATUS.get(status, STATUS['walk']))
        if pet.neutered: state += tr(' · 已绝育', ' · neutered')
        self.state.setText(state)
        self.neuter_button.setVisible(not pet.neutered)
        self.neuter_button.setToolTip(tr('绝育：以后不会再生小猫', 'Neuter: no more kittens'))
        alert = status == 'standoff'
        if self.property('alert') != alert:
            self.setProperty('alert', alert); self.style().unpolish(self); self.style().polish(self)
        self.pet_button.setText(tr('摸摸', 'Pet'))
        if alert:
            self.extra.setText(tr('拉开', 'Split')); self.extra.show()
        elif pet is not ctrl.pet:
            self.extra.setText(tr('送养', 'Rehome')); self.extra.show()
        else:
            self.extra.hide()


class ControlWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ctrl = None
        self._texts = []
        self._rows = []
        self.setObjectName('root')
        self.setWindowIcon(QIcon(resource('images/cat.png')))
        self.setFont(QFont('Microsoft YaHei UI', 9))
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self); outer.setContentsMargins(14, 12, 14, 12); outer.setSpacing(10)

        # ---- header: title + live chips
        header = QFrame(); header.setObjectName('header')
        header.setFixedHeight(56)
        hl = QHBoxLayout(header); hl.setContentsMargins(14, 8, 10, 8); hl.setSpacing(8)
        self.title = QLabel(); self.title.setObjectName('title'); self.title.setFixedHeight(34); hl.addWidget(self.title)
        hl.addSpacing(6)
        self.level_label = QLabel(); hl.addWidget(self.level_label)
        self.xp_bar = QProgressBar(); self.xp_bar.setFixedWidth(110); self.xp_bar.setFixedHeight(10); hl.addWidget(self.xp_bar)
        hl.addStretch(1)
        self.chips = {}
        for key in ('hunger', 'poop', 'cats'):
            chip = QLabel(); chip.setProperty('class', 'chip'); chip.setFixedHeight(26)
            hl.addWidget(chip); self.chips[key] = chip
        self.feedback = QPushButton(); self.feedback.setFixedHeight(32)
        self.feedback.clicked.connect(self.show_feedback); hl.addWidget(self.feedback)
        self.mute = QToolButton(); self.mute.setFixedSize(40, 32); self.mute.setCheckable(True); self.mute.setChecked(not prefs.values['sound'])
        self.mute.toggled.connect(self.mute_toggled); hl.addWidget(self.mute)
        outer.addWidget(header)

        body = QHBoxLayout(); body.setSpacing(12)
        outer.addLayout(body, 1)

        # ---- left: yard + action bar + alert
        left = QVBoxLayout(); left.setSpacing(8)
        self.arena = Arena(); self.arena.setObjectName('arena'); self.arena.setFixedSize(600, 380)
        surface.arena = self.arena
        left.addWidget(self.arena)
        actions = QHBoxLayout(); actions.setSpacing(6)
        self.feed = QPushButton(); self.feed.setObjectName('primary')
        self.adopt_button = QToolButton(); self.adopt_button.setObjectName('primary')
        self.adopt_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.adopt_menu = QMenu(self); self.adopt_button.setMenu(self.adopt_menu)
        self.clean = QPushButton(); self.split = QPushButton(); self.hide_button = QPushButton()
        self.neuter_all = QPushButton()
        for w in (self.feed, self.adopt_button, self.clean, self.split, self.neuter_all): actions.addWidget(w)
        actions.addStretch(1); actions.addWidget(self.hide_button)
        left.addLayout(actions)
        self.alert = QLabel(); self.alert.setObjectName('alert'); self.alert.setWordWrap(True); self.alert.hide()
        left.addWidget(self.alert)
        self.tip = QLabel(); self.tip.setObjectName('tip'); self.tip.setWordWrap(True); left.addWidget(self.tip)
        left.addStretch(1)
        body.addLayout(left)

        # ---- right: sidebar with tabs
        side = QFrame(); side.setObjectName('side'); side.setFixedWidth(300)
        sl = QVBoxLayout(side); sl.setContentsMargins(10, 10, 10, 10); sl.setSpacing(8)
        tabs = QHBoxLayout(); tabs.setSpacing(4)
        self.tab_group = QButtonGroup(self); self.tab_buttons = []
        for i in range(3):
            b = QPushButton(); b.setObjectName('tab'); b.setCheckable(True)
            self.tab_group.addButton(b, i); tabs.addWidget(b); self.tab_buttons.append(b)
        sl.addLayout(tabs)
        self.pages = QStackedWidget(); sl.addWidget(self.pages, 1)
        self.tab_group.buttonClicked[int].connect(self.pages.setCurrentIndex)
        self.tab_buttons[0].setChecked(True)
        self.pages.addWidget(self._build_roster())
        self.pages.addWidget(self._build_settings())
        self.pages.addWidget(self._build_journal())
        body.addWidget(side)

        # ---- wiring
        self.feed.clicked.connect(lambda: self.ctrl.spawn_snack())
        self.adopt_button.clicked.connect(self.adopt)
        self.clean.clicked.connect(self.clean_all)
        self.split.clicked.connect(self.split_all)
        self.neuter_all.clicked.connect(lambda: (self.ctrl.neuter_all(), self.refresh_roster(force=True)))
        self.hide_button.clicked.connect(self.hide)
        self.translate()

    # ------------------------------------------------------------ pages
    def _scroll(self, inner):
        area = QScrollArea(); area.setWidgetResizable(True); area.setWidget(inner)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner.setStyleSheet('background: transparent;')
        return area

    def _build_roster(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        self.roster_hint = QLabel(); self.roster_hint.setObjectName('tip'); self.roster_hint.setWordWrap(True)
        layout.addWidget(self.roster_hint)
        self.roster_box = QWidget(); self.roster = QVBoxLayout(self.roster_box)
        self.roster.setContentsMargins(0, 0, 4, 0); self.roster.setSpacing(6); self.roster.addStretch(1)
        layout.addWidget(self._scroll(self.roster_box), 1)
        return page

    def _section(self, form, key):
        label = QLabel(); label.setProperty('class', 'section'); form.addRow(label)
        self._texts.append((label, key))

    def _row(self, form, widget, key):
        label = QLabel(); label.setWordWrap(True); form.addRow(label, widget)
        self._texts.append((label, key))

    def _build_settings(self):
        inner = QWidget(); form = QFormLayout(inner); form.setContentsMargins(2, 0, 6, 0)
        form.setVerticalSpacing(7); form.setLabelAlignment(Qt.AlignLeft)
        p = prefs.values
        self.name = QLineEdit(p['username']); self.name.setMaxLength(32)
        self.breed = QComboBox()
        self.modes = QComboBox(); self.lang = QComboBox(); self.lang.addItems(['简体中文', 'English'])
        self.sound_on = QCheckBox(); self.sound_on.setChecked(p['sound'])
        self.volume = QSlider(Qt.Horizontal); self.volume.setRange(0, 100); self.volume.setValue(p['volume'])
        self.volume_label = QLabel(f"{p['volume']}%"); self.volume_label.setFixedWidth(34)
        volume_row = QWidget(); vr = QHBoxLayout(volume_row); vr.setContentsMargins(0, 0, 0, 0)
        vr.addWidget(self.volume, 1); vr.addWidget(self.volume_label)
        self.sleep_minutes = QSpinBox(); self.sleep_minutes.setRange(1, 240); self.sleep_minutes.setValue(p['sleep_minutes'])
        self.standoff_min = QSpinBox(); self.standoff_min.setRange(5, 600); self.standoff_min.setValue(p['standoff_min'])
        self.poop = QComboBox()
        self.meals = QSpinBox(); self.meals.setRange(1, 100); self.meals.setValue(p['meals'])
        self.chance = QSpinBox(); self.chance.setRange(0, 100); self.chance.setValue(p['chance'])
        self.minutes = QSpinBox(); self.minutes.setRange(1, 1440); self.minutes.setValue(p['minutes'])
        self._section(form, ('猫咪', 'Cats'))
        self._row(form, self.name, ('昵称', 'Your name'))
        self._row(form, self.breed, ('主猫品种', 'Main cat breed'))
        self._section(form, ('显示', 'Display'))
        self._row(form, self.modes, ('显示模式', 'Where cats live'))
        self._row(form, self.lang, ('语言', 'Language'))
        self._section(form, ('声音', 'Sound'))
        self._row(form, self.sound_on, ('对峙音效', 'Standoff sound'))
        self._row(form, volume_row, ('音量', 'Volume'))
        self._section(form, ('行为', 'Behaviour'))
        self._row(form, self.sleep_minutes, ('鼠标不动几分钟后睡觉', 'Sleep after mouse idle (min)'))
        self._row(form, self.standoff_min, ('对峙至少持续（秒）', 'Standoff lasts at least (s)'))
        self._section(form, ('便便', 'Poop'))
        self._row(form, self.poop, ('拉屎方式', 'Poop rule'))
        self._row(form, self.meals, ('吃几次后尝试', 'Meals per try'))
        self._row(form, self.chance, ('每次尝试概率 %', 'Chance per try %'))
        self._row(form, self.minutes, ('间隔（分钟）', 'Interval (min)'))
        self.lang.setCurrentIndex(0 if p['language'] == 'zh' else 1)
        self.lang.currentIndexChanged.connect(self.language_changed)
        self.modes.currentIndexChanged.connect(self.mode_changed)
        self.breed.currentIndexChanged.connect(self.breed_changed)
        self.sound_on.toggled.connect(self.sound_changed)
        self.volume.valueChanged.connect(self.sound_changed)
        self.poop.currentIndexChanged.connect(self.settings_changed)
        for field in (self.meals, self.chance, self.minutes, self.sleep_minutes, self.standoff_min):
            field.valueChanged.connect(self.settings_changed)
        self.name.editingFinished.connect(self.settings_changed)
        return self._scroll(inner)

    def _build_journal(self):
        inner = QWidget(); layout = QVBoxLayout(inner); layout.setContentsMargins(2, 0, 6, 0); layout.setSpacing(6)
        self.stats_label = QLabel(); self.stats_label.setWordWrap(True); layout.addWidget(self.stats_label)
        self.ach_title = QLabel(); self.ach_title.setProperty('class', 'section'); layout.addWidget(self.ach_title)
        self.ach_label = QLabel(); self.ach_label.setWordWrap(True); layout.addWidget(self.ach_label)
        self.quit_button = QPushButton(); self.quit_button.clicked.connect(QApplication.instance().quit)
        layout.addStretch(1); layout.addWidget(self.quit_button)
        return self._scroll(inner)

    # ------------------------------------------------------------ text
    def translate(self):
        self.setWindowTitle(tr('猫猫小院', 'Cat Yard'))
        self.title.setText(tr('🐾 猫猫小院', '🐾 Cat Yard'))
        for button, zh, en in [(self.feed, '🍖 喂食', '🍖 Feed'), (self.clean, '🧹 清理便便', '🧹 Clean poop'),
                               (self.split, '✋ 劝架', '✋ Break up'), (self.hide_button, '收起', 'Hide'),
                               (self.neuter_all, '✂ 全部绝育', '✂ Neuter all'), (self.feedback, '💌 意见反馈', '💌 Feedback'),
                               (self.quit_button, '退出程序', 'Quit')]:
            button.setText(tr(zh, en))
        self.adopt_button.setText(tr('🐱 领养', '🐱 Adopt'))
        self.adopt_menu.clear()
        self.adopt_menu.addAction(tr('随机品种', 'Random breed'), self.adopt)
        self.adopt_menu.addSeparator()
        for b in BREED_ORDER:
            self.adopt_menu.addAction(QIcon(avatar(b)), tr(breed_name(b, True), breed_name(b, False)),
                                      lambda b=b: self.adopt(b))
        for button, (zh, en) in zip(self.tab_buttons, [('猫咪', 'Cats'), ('设置', 'Settings'), ('档案', 'Journal')]):
            button.setText(tr(zh, en))
        for label, (zh, en) in self._texts:
            label.setText(tr(zh, en))
        for combo, labels in [(self.breed, [(breed_name(b, True), breed_name(b, False)) for b in BREED_ORDER]),
                              (self.modes, [('小窗口里的小院', 'Inside this window'), ('桌面（图标层）', 'On the desktop'),
                                            ('桌面最前面', 'Always on top')]),
                              (self.poop, [('按进食次数', 'After eating'), ('定时', 'On a timer'), ('关闭', 'Off')])]:
            index = combo.currentIndex(); combo.blockSignals(True); combo.clear()
            combo.addItems([tr(*pair) for pair in labels]); combo.setCurrentIndex(max(0, index)); combo.blockSignals(False)
        if self.breed.currentIndex() <= 0 or not self.ctrl:
            self.breed.blockSignals(True); self.breed.setCurrentIndex(BREED_ORDER.index(prefs.values['breed'])); self.breed.blockSignals(False)
            self.modes.blockSignals(True); self.modes.setCurrentIndex(MODES.index(prefs.values['mode'])); self.modes.blockSignals(False)
            self.poop.blockSignals(True); self.poop.setCurrentIndex(POOP_MODES.index(prefs.values['poop_mode'])); self.poop.blockSignals(False)
        self.sound_on.setText(tr('播放', 'On'))
        self.roster_hint.setText(tr('不同品种碰面会应激对峙：拖走其中一只或点“拉开”。小猫和大猫对峙可能被一巴掌拍没。同品种碰面会生小猫，点 ✂ 绝育就不会了。',
                                    'Different breeds hiss when they meet — drag one away or press Split. Kittens can lose a fight with a grown cat. Same breeds have kittens unless neutered (✂).'))
        self.tip.setText(tr('按住 Ctrl + Alt 变成逗猫棒 · 点猫摸摸，拖动拎起 · 右键猫咪有更多选项 · 便便不清理会一直留着',
                            'Hold Ctrl + Alt for the feather wand · click to pet, drag to carry · right-click a cat for more · poop stays until cleaned'))
        self.ach_title.setText(tr('成就', 'Achievements'))
        self.update_enabled()
        self.update_status()
        if self.ctrl:
            self.refresh_roster(force=True)
            self.ctrl.tray.rebuild()

    # ------------------------------------------------------------ actions
    def adopt(self, breed=None):
        pet = self.ctrl.adopt(breed if isinstance(breed, str) else None)
        self.refresh_roster()
        return pet

    def split_all(self):
        for standoff in self.ctrl.standoffs[:]:
            self.ctrl.end_standoff(standoff, nudge=True)

    def clean_all(self):
        for poop in self.ctrl.poops[:]:
            self.ctrl.clean_poop(poop)

    def show_feedback(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr('意见反馈', 'Feedback'))
        box.setIcon(QMessageBox.Information)
        box.setText(tr(f'有想法、发现 bug，欢迎发邮件给我：<br><br><b style="font-size:12pt">{FEEDBACK_EMAIL}</b>',
                       f'Ideas or bugs? Send me an email:<br><br><b style="font-size:12pt">{FEEDBACK_EMAIL}</b>'))
        box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        copy = box.addButton(tr('复制邮箱', 'Copy address'), QMessageBox.ActionRole)
        mail = box.addButton(tr('写邮件', 'Write email'), QMessageBox.ActionRole)
        box.addButton(tr('关闭', 'Close'), QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is copy:
            QApplication.clipboard().setText(FEEDBACK_EMAIL)
            if self.ctrl: self.ctrl.bubble.show_text(tr('邮箱已复制', 'Email copied'), 1500)
        elif box.clickedButton() is mail:
            QDesktopServices.openUrl(QUrl(f'mailto:{FEEDBACK_EMAIL}?subject=' + tr('猫猫小院 意见反馈', 'Cat Yard feedback')))

    def mute_toggled(self, muted):
        self.sound_on.setChecked(not muted)

    def sound_changed(self):
        prefs.values['sound'] = self.sound_on.isChecked()
        prefs.values['volume'] = self.volume.value()
        self.volume_label.setText(f'{self.volume.value()}%')
        self.mute.blockSignals(True); self.mute.setChecked(not prefs.values['sound']); self.mute.blockSignals(False)
        self.mute.setText('🔇' if not prefs.values['sound'] else ('🔈' if prefs.values['volume'] < 40 else '🔊'))
        prefs.save()
        if self.ctrl: self.ctrl.refresh_sound()

    def language_changed(self):
        prefs.values['language'] = 'zh' if self.lang.currentIndex() == 0 else 'en'
        prefs.save(); self.translate()
        if self.ctrl: self.ctrl.bubble._text = ''

    def breed_changed(self):
        prefs.values['breed'] = BREED_ORDER[self.breed.currentIndex()]
        prefs.save()
        if self.ctrl:
            self.ctrl.set_main_breed(prefs.values['breed'])
            self.refresh_roster(force=True)

    def mode_changed(self):
        new_mode = MODES[self.modes.currentIndex()]
        old_mode = surface.mode
        try:
            surface.switch(new_mode)
        except Exception as exc:
            logging.exception('Could not change display mode')
            surface.switch(old_mode)
            prefs.values['mode'] = old_mode; prefs.save()
            self.modes.blockSignals(True); self.modes.setCurrentIndex(MODES.index(old_mode)); self.modes.blockSignals(False)
            QMessageBox.warning(self, tr('无法切换', 'Display error'), str(exc)); return
        prefs.values['mode'] = new_mode; prefs.save()
        self.arena.setVisible(new_mode == 'window'); self.adjustSize()

    def settings_changed(self):
        prefs.values.update(username=self.name.text().strip() or 'Player',
            poop_mode=POOP_MODES[self.poop.currentIndex()],
            meals=self.meals.value(), chance=self.chance.value(), minutes=self.minutes.value(),
            sleep_minutes=self.sleep_minutes.value(), standoff_min=self.standoff_min.value())
        prefs.save()
        if self.ctrl:
            self.ctrl.username = prefs.values['username']; self.ctrl._eats_since_poop = 0
            self.poop_timer.stop()
            if prefs.values['poop_mode'] == 'timer': self.poop_timer.start(prefs.values['minutes'] * 60000)
        self.update_enabled()

    def update_enabled(self):
        food = prefs.values['poop_mode'] == 'food'
        self.meals.setEnabled(food); self.chance.setEnabled(food)
        self.minutes.setEnabled(prefs.values['poop_mode'] == 'timer')
        self.volume.setEnabled(prefs.values['sound'])
        self.mute.setText('🔇' if not prefs.values['sound'] else ('🔈' if prefs.values['volume'] < 40 else '🔊'))
        self.mute.setToolTip(tr('对峙音效开关', 'Standoff sound on/off'))

    def bind(self, ctrl):
        self.ctrl = ctrl
        self.poop_timer = QTimer(self); self.poop_timer.timeout.connect(ctrl._spawn_poop)
        if prefs.values['poop_mode'] == 'timer': self.poop_timer.start(prefs.values['minutes'] * 60000)
        self.refresh = QTimer(self); self.refresh.timeout.connect(self.update_status); self.refresh.start(400)
        self.mode_changed()
        self.translate()

    # ------------------------------------------------------------ live state
    def refresh_roster(self, force=False):
        if not self.ctrl: return
        pets = self.ctrl.all_pets
        if force or [row.pet for row in self._rows] != pets:
            for row in self._rows:
                self.roster.removeWidget(row); row.deleteLater()
            self._rows = []
            for index, pet in enumerate(pets):
                row = CatRow(self, pet, index)
                self.roster.insertWidget(self.roster.count() - 1, row); self._rows.append(row)
        else:
            for row in self._rows: row.refresh()

    def update_status(self):
        c = self.ctrl
        if not c: return
        self.level_label.setText(tr(f'Lv.{c.level}', f'Lv.{c.level}'))
        self.xp_bar.setMaximum(max(1, c.xp_for_next_level)); self.xp_bar.setValue(min(c.xp, c.xp_for_next_level))
        self.chips['hunger'].setText(tr(f'饥饿 {int(c.hunger)}%', f'Hunger {int(c.hunger)}%'))
        self.chips['poop'].setText(f'💩 {len(c.poops)}')
        self.chips['cats'].setText(f'🐱 {len(c.all_pets)}')
        self.clean.setText(tr(f'🧹 清理便便 ({len(c.poops)})', f'🧹 Clean poop ({len(c.poops)})'))
        self.split.setEnabled(bool(c.standoffs))
        if c.standoffs:
            self.alert.setText(tr(f'⚠ {len(c.standoffs)} 对猫咪在应激对峙！拖走其中一只，或点“劝架”。',
                                  f'⚠ {len(c.standoffs)} standoff(s)! Drag one cat away or press “Break up fights”.'))
            self.alert.show()
        elif c.mood == 'sleeping':
            self.alert.setText(tr('😴 鼠标太久没动，猫咪们睡着了。动一下鼠标叫醒它们。', '😴 The mouse sat still, so the cats fell asleep. Move it to wake them.'))
            self.alert.show()
        else:
            self.alert.hide()
        self.refresh_roster()
        if self.pages.currentIndex() == 2:
            self.update_journal()

    def update_journal(self):
        from utils.utils import ACHIEVEMENTS, load_json_safe, RANKING_FILE
        from language import ACH
        c = self.ctrl
        counts = {}
        for pet in c.all_pets: counts[pet.breed_label()] = counts.get(pet.breed_label(), 0) + 1
        family = '、'.join(f'{name}×{n}' for name, n in counts.items()) if prefs.values['language'] == 'zh' else ', '.join(f'{name} ×{n}' for name, n in counts.items())
        self.stats_label.setText(tr(
            f'<b>等级</b> {c.level}　经验 {c.xp}/{c.xp_for_next_level}<br><b>进食</b> {c.total_eats} 次　<b>抚摸</b> {c.total_pets} 次<br>'
            f'<b>便便</b> 场上 {len(c.poops)} 坨　<b>墓碑</b> {len(c.graves)} 座<br><b>家庭成员</b> {family}<br>'
            f'<b>已绝育</b> {sum(p.neutered for p in c.all_pets)}/{len(c.all_pets)}<br><b>CPU</b> {c.cpu_percent:.0f}%',
            f'<b>Level</b> {c.level}  XP {c.xp}/{c.xp_for_next_level}<br><b>Meals</b> {c.total_eats}  <b>Pets</b> {c.total_pets}<br>'
            f'<b>Poop</b> {len(c.poops)} on screen  <b>Graves</b> {len(c.graves)}<br><b>Family</b> {family}<br>'
            f'<b>Neutered</b> {sum(p.neutered for p in c.all_pets)}/{len(c.all_pets)}<br><b>CPU</b> {c.cpu_percent:.0f}%'))
        lines = []
        for ach in ACHIEVEMENTS:
            name, desc = ACH[ach['id']] if prefs.values['language'] == 'zh' else (ach['name'], ach['desc'])
            done = ach['id'] in c.unlocked_achievements
            lines.append(('✅ ' if done else '⬜ ') + f'<b>{name}</b> <span style="color:#9a8a7a">{desc}</span>')
        self.ach_label.setText('<br>'.join(lines))

    def closeEvent(self, event):
        self.hide(); event.ignore()

    def reopen(self):
        self.showNormal(); self.raise_(); self.activateWindow()


class Tray:
    def __init__(self, ctrl, app):
        self.ctrl, self.app = ctrl, app
        self.tray = QSystemTrayIcon(QIcon(resource('images/cat.png')), app)
        self.tray.activated.connect(self.activated)
        self.rebuild(); self.tray.show()

    def rebuild(self):
        old = getattr(self, 'menu', None)
        self.menu = QMenu()
        for label, action in [(tr('打开猫猫小院', 'Open Cat Yard'), window.reopen),
                              (tr('喂食', 'Feed'), self.ctrl.spawn_snack),
                              (tr('领养（随机）', 'Adopt (random)'), window.adopt),
                              (tr('劝架', 'Break up fights'), window.split_all),
                              (tr('意见反馈', 'Feedback'), window.show_feedback),
                              (tr('清理全部便便', 'Clean all poop'), window.clean_all),
                              (tr('音效开/关', 'Sound on/off'), lambda: window.mute.toggle()),
                              (tr('退出', 'Quit'), self.app.quit)]:
            self.menu.addAction(label, action)
        self.tray.setContextMenu(self.menu)
        if old: old.deleteLater()

    def refresh(self):
        c = self.ctrl
        self.tray.setToolTip(tr(f'猫猫小院 · {len(c.all_pets)} 只猫 · 便便 {len(c.poops)}',
                                f'Cat Yard · {len(c.all_pets)} cats · {len(c.poops)} poop'))

    def activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick: window.reopen()
        elif reason == QSystemTrayIcon.Trigger: self.ctrl.spawn_snack()


def resource(relative):
    return str(Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / relative)


def main():
    global window
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    if '--data-dir' in sys.argv:
        root = Path(sys.argv[sys.argv.index('--data-dir') + 1]).resolve()
    root.mkdir(parents=True, exist_ok=True); os.chdir(root)
    prefs.load()
    logging.basicConfig(filename='cat.log', level=logging.INFO, encoding='utf-8')
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('JianzhouCat')
    lock = QLockFile(str(root / 'cat.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, 'Cat', tr('猫咪已经在运行，请双击托盘图标打开。', 'Cat is already running. Double-click its tray icon.')); return
    surface.mode = 'window'
    window = ControlWindow()
    from core.main_controller import MainController
    MainController._ask_username = staticmethod(lambda: prefs.values['username'])
    MainController._setup_tray = lambda self: setattr(self, 'tray', Tray(self, app))
    import wand
    wand.current = wand.Wand(app, root)
    ctrl = MainController(app)
    window.bind(ctrl)
    window.show()
    def shutdown():
        wand.current.close()
        prefs.save(); ctrl.save_state(); ctrl.stop_all_timers()
        window.poop_timer.stop(); ctrl.tray.tray.hide()
    app.aboutToQuit.connect(shutdown)
    if '--verify' in sys.argv:
        from verify_app import schedule_checks
        schedule_checks(app, window, ctrl, root)
    sys.exit(app.exec_())


if __name__ == '__main__':
    if '--cursor-guard' in sys.argv:
        from wand import guard_loop
        index = sys.argv.index('--cursor-guard')
        guard_loop(sys.argv[index + 1], sys.argv[index + 2])
    else:
        main()
