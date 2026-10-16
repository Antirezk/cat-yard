"""Chubby picture-book cats in several breeds, rendered at continuous poses.

All geometry is original and drawn in code: stubby IK legs, a damped tail
chain, breathing, blinking, ear flicks and head tracking every frame. Sleeping
cats curl into a ball; frightened cats do the full meme "∩" arch.
"""
import math
import random
from dataclasses import dataclass
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient, QImage

TAU = math.tau

def blend(value, target, dt, rate=9):
    return value + (target - value) * (1 - math.exp(-rate * dt))

def clamp(value, low, high):
    return max(low, min(high, value))

# --------------------------------------------------------------------------- breeds
# fur: body gradient (top, mid, bottom). patches: body pattern shapes. stripes: tabby
# stripe colour. legs: (outline, top, bottom). tail: (outline, main, ring colour|None).
# face: gradient (top, bottom). face_marks: head pattern shapes. eyes: one (top, bottom)
# iris gradient per eye.
BREEDS = {
    'calico': dict(zh='三花猫', en='Calico', fur=('#fff9ef', '#f4eadb', '#d6c6b5'), outline='#6a584b',
        patches=[('rump', ('#d49956', '#be7540', '#a05b35')), ('shoulder', '#3d3936')], stripes=None,
        legs=('#8e7b67', '#ebe0ce', '#fff9ed'), legs_far=('#847468', '#c6b4a0', '#e6dbce'),
        paw=('#f7eee0', '#ddd0bf', '#9c8a78'), tail=('#675246', '#c78950', '#45403b'), tail_style='spots',
        face=('#fff9eb', '#e6d6c1'), face_marks=[('cal_left', '#c1874d'), ('cal_right', '#403b36')],
        ear=('#665248', '#e3c6a2', '#c99792'), eyes=(('#93712d', '#d4bd67'),) * 2,
        muzzle='#fff8eb', nose=('#b7807a', '#845c57'), mouth='#796252', whisker=(102, 90, 74, 140),
        sheen=(255, 248, 231)),
    'black': dict(zh='黑猫', en='Black cat', fur=('#3b373b', '#2a272a', '#1b191b'), outline='#0e0d0f',
        patches=[], stripes=None,
        legs=('#0e0d0f', '#2c292c', '#363236'), paw=('#353135', '#2a272a', '#0e0d0f'),
        tail=('#0e0d0f', '#2c292c', None), tail_style=None,
        face=('#3a363a', '#262326'), face_marks=[],
        ear=('#121012', '#2f2b2f', '#6b4f55'), eyes=(('#7fa43a', '#e1c94b'),) * 2,
        muzzle='#353135', nose=('#4c3d40', '#1a1618'), mouth='#121012', whisker=(225, 225, 230, 170),
        sheen=(150, 145, 160)),
    'white': dict(zh='白猫', en='White cat', fur=('#ffffff', '#f7f5f1', '#dedad3'), outline='#9a9088',
        patches=[], stripes=None,
        legs=('#a39a92', '#f1eee9', '#ffffff'), paw=('#fffdf9', '#ece8e2', '#aaa198'),
        tail=('#a39a92', '#f8f6f2', None), tail_style=None,
        face=('#ffffff', '#ece8e2'), face_marks=[],
        ear=('#a39a92', '#fbf8f4', '#efb3b3'), eyes=(('#3f7fd0', '#9fd0f7'), ('#b58a24', '#ead36a')),
        muzzle='#ffffff', nose=('#eda6a6', '#c27f7f'), mouth='#a08a86', whisker=(150, 140, 135, 150),
        sheen=(255, 255, 255)),
    'tabby': dict(zh='狸花猫', en='Li Hua tabby', fur=('#b9a487', '#a28c6c', '#7e6a50'), outline='#4a3c2e',
        patches=[('belly', '#e3d6c0')], stripes='#2f2820',
        legs=('#4a3c2e', '#a8926f', '#cdbb9e'), paw=('#d2c2a6', '#b4a283', '#5e4e3d'),
        tail=('#4a3c2e', '#a48e6c', '#2f2820'), tail_style='rings',
        face=('#b8a385', '#a08b6c'), face_marks=[('cap', '#7f6b52'), ('mstripes', '#2f2820')],
        ear=('#4a3c2e', '#a18b6b', '#c99792'), eyes=(('#6e8f2e', '#c6cf5a'),) * 2,
        muzzle='#eee4d1', nose=('#a86a62', '#6d4540'), mouth='#4a3c2e', whisker=(240, 236, 226, 150),
        sheen=(240, 228, 205)),
    'orange': dict(zh='橘猫', en='Orange cat', fur=('#f5b46d', '#e89b4f', '#c87633'), outline='#8a4f22',
        patches=[('belly', '#fff3e2'), ('chest', '#fff6ea')], stripes='#c0682a',
        legs=('#8a4f22', '#eba05a', '#fff3e2'), paw=('#fff6ea', '#f1e2cc', '#a0724e'),
        tail=('#8a4f22', '#ec9f55', '#c0682a'), tail_style='rings',
        face=('#f6b26b', '#e9984f'), face_marks=[('mstripes', '#c0682a'), ('chin', '#fff6ea')],
        ear=('#8a4f22', '#f3c591', '#e7a19a'), eyes=(('#b8741c', '#f0c64a'),) * 2,
        muzzle='#fff6ea', nose=('#de8f82', '#a85d52'), mouth='#8a4f22', whisker=(255, 250, 240, 170),
        sheen=(255, 232, 196)),
    'siamese': dict(zh='暹罗猫', en='Siamese', fur=('#f6ecdc', '#ead9bf', '#c9b090'), outline='#5b4636',
        patches=[('saddle', '#cdb592')], stripes=None,
        legs=('#2e211a', '#d9c3a3', '#4a3528'), legs_far=('#2a1e17', '#b8a080', '#3d2c22'),
        paw=('#4a3528', '#3b2a20', '#22170f'),
        tail=('#2e211a', '#4a3528', None), tail_style=None,
        face=('#f3e6d1', '#dcc6a6'), face_marks=[('mask', '#3f2d22')],
        ear=('#2e211a', '#4a3528', '#7a5b4b'), eyes=(('#2f6fd1', '#8cc8f5'),) * 2,
        muzzle='#5a4334', nose=('#3a2a22', '#20150f'), mouth='#20150f', whisker=(245, 238, 228, 160),
        sheen=(255, 248, 235)),
    'ragdoll': dict(zh='布偶猫', en='Ragdoll', fur=('#fffbf4', '#f5ece0', '#d8c9b6'), outline='#7f6c5e',
        patches=[('saddle', '#c9b4a1'), ('chest', '#fffdf8')], stripes=None, fluffy=True,
        legs=('#6e5a4c', '#e3d3c0', '#a68f7c'), legs_far=('#62503f', '#c7b5a2', '#927c69'),
        paw=('#fffdf8', '#efe7dc', '#9c8a78'),
        tail=('#5f4d40', '#8f7766', None), tail_style=None,
        face=('#fffaf2', '#ebdfcf'), face_marks=[('vmask', '#7d6656')],
        ear=('#5f4d40', '#8f7766', '#c99792'), eyes=(('#2d63c4', '#9dd2fb'),) * 2,
        muzzle='#fffdf8', nose=('#c58a87', '#8a5b58'), mouth='#7f6c5e', whisker=(120, 105, 95, 140),
        sheen=(255, 252, 245)),
}
ADOPTABLE = ['black', 'white', 'tabby', 'orange', 'siamese', 'ragdoll', 'calico']

def breed_name(breed, zh=True):
    spec = BREEDS.get(breed, BREEDS['calico'])
    return spec['zh'] if zh else spec['en']

def smooth(x):
    x = clamp(x, 0, 1)
    return x * x * (3 - 2 * x)

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(int(lerp(a.red(), b.red(), t)), int(lerp(a.green(), b.green(), t)), int(lerp(a.blue(), b.blue(), t)))

def qc(color, alpha=None):
    c = QColor(color)
    if alpha is not None: c.setAlpha(alpha)
    return c

@dataclass
class Pose:
    clock: float = 0
    phase: float = 0
    gait: float = 0
    facing: float = 1
    sleep: float = 0
    eat: float = 0
    squat: float = 0
    cuddle: float = 0
    playful: float = 0
    held: float = 0
    affection: float = 0
    hiss: float = 0
    blink: float = 0
    look_x: float = 0
    look_y: float = 0

# Tail shoots straight up like a bottle brush in the meme pose.
HISS_TAIL = [-1.15, -1.45, -1.72, -2.15]
# Hiss styles, all real cat threat displays (exaggerated a little for comedy):
# 'arch'   Halloween ∩ arch on stiff tall legs, head low, side-eye glare
# 'crab'   sideways stiff-legged hop with the body tilted
# 'crouch' pressed flat to the ground, ears pinned, tail lashing low
# 'swipe'  leaning back with one front paw raised, claws out, swatting now and then
# A standoff picks one at random and keeps reshuffling every few seconds.
HISS_STYLES = ('arch', 'crab', 'crouch', 'swipe')
LOW_TAIL = [0.75, 0.35, -0.05, -0.55]
GROUND = 145

class CatRig:
    def __init__(self, breed='calico', hiss_style=None):
        self.pose = Pose()
        self.rng = random.Random()
        self.blink_at = self.rng.uniform(2.0, 5.0)
        self.tail = [-1.4, -0.9, -0.3, 0.3]
        self.tail_velocity = [0.0] * 4
        self.fixed_style = hiss_style if hiss_style in HISS_STYLES else None
        self.style = self.fixed_style or self.rng.choice(HISS_STYLES)
        self.style_weights = {name: float(name == self.style) for name in HISS_STYLES}
        self._style_until = 0.0
        self._hissing = False
        self.neutered = False
        self.set_breed(breed)

    def set_breed(self, breed):
        self.breed = breed if breed in BREEDS else 'calico'
        self.look = BREEDS[self.breed]

    # ------------------------------------------------------------------ motion
    def advance(self, dt, speed=0, facing=1, action='idle', look=(0, 0)):
        dt = clamp(dt, 0, .05)
        p = self.pose
        p.clock += dt
        p.gait = blend(p.gait, clamp(speed / 105, 0, 1), dt, 8)
        p.phase += dt * (2.0 + speed * .065) * p.gait
        p.facing = blend(p.facing, facing, dt, 10)
        for name, target in [('sleep', action == 'sleep'), ('eat', action == 'eat'),
                             ('squat', action == 'poop'), ('cuddle', action == 'cuddle'),
                             ('playful', action in ('chase', 'pounce', 'cuddle')),
                             ('held', action == 'held'), ('affection', action == 'pet'),
                             ('hiss', action == 'hiss')]:
            rate = 6 if name == 'sleep' else (8 if name == 'hiss' else 10)
            setattr(p, name, blend(getattr(p, name), float(target), dt, rate))
        self._update_style(action)
        for name in HISS_STYLES:
            self.style_weights[name] = blend(self.style_weights[name], float(name == self.style), dt, 5)
        p.look_x = blend(p.look_x, clamp(look[0], -1, 1), dt, 7)
        p.look_y = blend(p.look_y, clamp(look[1], -1, 1), dt, 7)
        if p.clock >= self.blink_at:
            elapsed = p.clock - self.blink_at
            p.blink = math.sin(min(1, elapsed / .19) * math.pi)
            if elapsed >= .19:
                self.blink_at = p.clock + self.rng.uniform(2.7, 6.5) * (1 + p.hiss * 3)
                p.blink = 0
        else:
            p.blink = 0
        for i in range(4):
            target = (-1.45 + i * .40 + math.sin(p.clock * 1.6 - i * .55) * .22
                      - p.playful * .3 + p.sleep * .7 - p.squat * .65)
            low = self.style_weights['crouch']
            hiss_target = lerp(HISS_TAIL[i] + math.sin(p.clock * 11 - i) * .05,
                               LOW_TAIL[i] + math.sin(p.clock * 5 - i * .8) * (.15 + i * .1), low)
            target += (hiss_target - target) * p.hiss
            self.tail_velocity[i] += ((target - self.tail[i]) * 45 - self.tail_velocity[i] * 11) * dt
            self.tail[i] += self.tail_velocity[i] * dt

    def _update_style(self, action):
        p = self.pose
        if action == 'hiss':
            if not self._hissing:
                self._hissing = True
                if p.hiss < .1 and not self.fixed_style:
                    self.style = self.rng.choice(HISS_STYLES)
                    self.style_weights = {name: float(name == self.style) for name in HISS_STYLES}
                self._style_until = p.clock + self.rng.uniform(4.5, 8)
            elif p.clock > self._style_until and not self.fixed_style:
                self.style = self.rng.choice([s for s in HISS_STYLES if s != self.style])
                self._style_until = p.clock + self.rng.uniform(4.5, 8)
        else:
            self._hissing = False

    def striking(self):
        """True during the instant a raised paw lands its swat (swipe pose only)."""
        if self.w('swipe') < .7:
            return False
        beat = (self.pose.clock * .85) % 1
        return .06 < beat < .14

    def force_style(self, style):
        if style in HISS_STYLES and not self.fixed_style:
            self.style = style
            self._style_until = self.pose.clock + self.rng.uniform(6, 9)

    def w(self, name):
        """How strongly a hiss style is showing right now (0..1)."""
        return self.pose.hiss * self.style_weights[name]

    def _breath(self):
        p = self.pose
        return math.sin(p.clock * 2.6) * (1.2 + p.sleep * 1.1) * (1 - p.hiss * .6)

    def _lift(self):
        return self.w('arch') * 36 + self.w('crab') * 6 + self._hop()

    def _hop(self):
        return abs(math.sin(self.pose.clock * 8.5)) * 13 * self.w('crab')

    def _stand_head(self):
        p = self.pose
        A, C, Q, S = self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe')
        hx = 166 + p.look_x * 3 + p.cuddle * 6 + p.eat * 6 + A * 16 + C * 6 + Q * 12 - S * 14
        hy = 70 + p.eat * 38 + p.squat * 5 - p.held * 4 + self._breath() * .45 - self._lift()
        hy += A * 60 + C * 22 + Q * 40 - S * 8
        hy += p.eat * math.sin(p.clock * 15) * 1.5 + p.cuddle * math.sin(p.clock * 18) * 1.2
        hy += math.cos(p.phase * 2) * 1.6 * p.gait
        return hx, hy

    def head_xy(self):
        """Face centre in rig space (before the body tilt/turn transform)."""
        s = smooth((self.pose.sleep - .2) / .6)
        hx, hy = self._stand_head()
        return lerp(hx, 160, s), lerp(hy, 116 + self._breath() * .4, s)

    def head_angle(self):
        p = self.pose
        A, C, Q, S = self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe')
        stand = p.look_y * 6 + p.eat * 22 - p.playful * 7 + A * 24 + C * (18 + math.sin(p.clock * 8.5) * 6) + Q * 8 - S * 10
        return lerp(stand, 12, smooth((p.sleep - .2) / .6))

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def path(points):
        path = QPainterPath(QPointF(*points[0]))
        for group in points[1:]:
            if len(group) == 6: path.cubicTo(*group)
            elif len(group) == 4: path.quadTo(*group)
            else: path.lineTo(*group)
        return path

    @staticmethod
    def fill(painter, path, color, outline=None, width=1.6):
        painter.setPen(QPen(qc(outline), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin) if outline else Qt.NoPen)
        painter.setBrush(color if not isinstance(color, str) else QColor(color))
        painter.drawPath(path)

    @staticmethod
    def brush(spec, x0, y0, x1, y1):
        if isinstance(spec, str): return QColor(spec)
        gradient = QLinearGradient(x0, y0, x1, y1)
        for i, color in enumerate(spec): gradient.setColorAt(i / (len(spec) - 1), QColor(color))
        return gradient

    def _stroke(self, painter, path, outline, color, width):
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(outline), width + 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); painter.drawPath(path)
        painter.setPen(QPen(color if not isinstance(color, str) else QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

    # ------------------------------------------------------------------ painting
    def paint(self, painter, width, height, shadow=True):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        sx, sy = width / 240, height / 180
        painter.scale(sx, sy)
        p = self.pose
        if shadow:
            gradient = QRadialGradient(118, 148, 70)
            gradient.setColorAt(0, QColor(53, 44, 34, 40)); gradient.setColorAt(1, QColor(53, 44, 34, 0))
            painter.setPen(Qt.NoPen); painter.setBrush(gradient)
            spread = 1 + p.hiss * .25 - smooth((p.sleep - .2) / .6) * .15
            painter.drawEllipse(QRectF(118 - 78 * spread, 139, 156 * spread, 18))
        s = smooth((p.sleep - .2) / .6)
        if s <= .01:
            self._paint_standing(painter)
        elif s >= .99:
            self._paint_curled(painter)
        else:
            # Cross-fade through offscreen layers so overlapping parts never ghost.
            scale = max(1.0, sx, sy) * 1.5
            for draw, alpha in ((self._paint_standing, 1 - s), (self._paint_curled, s)):
                layer = QImage(int(240 * scale), int(180 * scale), QImage.Format_ARGB32_Premultiplied)
                layer.fill(Qt.transparent)
                lp = QPainter(layer); lp.setRenderHint(QPainter.Antialiasing); lp.scale(scale, scale)
                draw(lp); lp.end()
                painter.setOpacity(alpha)
                painter.drawImage(QRectF(0, 0, 240, 180), layer)
            painter.setOpacity(1)
        painter.restore()

    def _turn(self, painter, pivot_x=120, pivot_y=126, tilt=0.0):
        p = self.pose
        painter.translate(pivot_x, pivot_y)
        painter.rotate(tilt)
        painter.scale(.30 + .70 * abs(p.facing), 1)
        if p.facing < 0: painter.scale(-1, 1)
        painter.translate(-pivot_x, -pivot_y)

    def _body_geometry(self):
        """Key body coordinates: rear x, front x, back top, belly, rear end y, front end y."""
        p = self.pose
        A, C, Q, S = self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe')
        a = min(1, A + C * .6 + S * .15)
        breath = self._breath()
        lift = self._lift()
        bob = math.cos(p.phase * 2) * 1.6 * p.gait
        rx, fx = 66 - a * 4 - Q * 4, 168 + a * 4 + Q * 4
        top = 70 - breath + p.squat * 6 - a * 42 - lift + bob + A * 8 + Q * 34 + S * 6
        belly = 128 - a * 30 - lift + bob + p.squat * 3 + A * 6 + Q * 12 + S * 4
        end_r = 100 + a * 6 - lift + bob + p.squat * 6 + Q * 22 + S * 16
        end_f = 94 + a * 12 - lift + bob + Q * 22 - S * 10
        return rx, fx, top, belly, end_r, end_f

    def _body_points(self):
        rx, fx, top, belly, end_r, end_f = self._body_geometry()
        A, C, S = self.w('arch'), self.w('crab'), self.w('swipe')
        a = min(1, A + C * .6 + S * .15)
        mid = (rx + fx) / 2
        bean = [(rx, end_r),
            (rx, lerp(74, end_r - 30, a), lerp(rx + 18, rx + 14, a), top, mid, top),
            (lerp(fx - 18, fx - 14, a), top, fx, lerp(68, end_f - 34, a), fx, end_f),
            (fx, lerp(122, end_f + 26, a), lerp(fx - 16, fx - 12, a), belly, mid, belly),
            (lerp(rx + 18, rx + 14, a), belly, rx, lerp(126, end_r + 26, a), rx, end_r)]
        return bean

    def _body_path(self):
        return self.path(self._body_points())

    def _paint_standing(self, painter):
        p, L = self.pose, self.look
        A, C, Q, S = self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe')
        painter.save()
        tilt = p.cuddle * (-16 + math.sin(p.clock * 13) * 2.5) + p.held * math.sin(p.clock * 4) * 5
        tilt += C * (-17 + math.sin(p.clock * 8.5) * 4)
        self._turn(painter, tilt=tilt)
        # Shrink a little for the tall poses so the silhouette stays in frame.
        shrink = 1 - .16 * A
        painter.translate(120, GROUND); painter.scale(shrink, shrink); painter.translate(-120, -GROUND)
        # Comic full-body tremble while hissing; the crab also scuttles sideways.
        painter.translate(math.sin(p.clock * 53) * 1.1 * p.hiss + math.sin(p.clock * 4.25) * 9 * C,
                          math.sin(p.clock * 41) * .6 * p.hiss)
        self._tail(painter)
        rx, fx, top, belly, end_r, end_f = self._body_geometry()
        for front, phase in [(False, math.pi), (True, 0)]:
            self._leg(painter, front, phase, far=True)
        body = self._body_path()
        self.fill(painter, body, self.brush(L['fur'], 90, top, 110, belly + 6), L['outline'])
        painter.save(); painter.setClipPath(body)
        self._patterns(painter, rx, fx, top, belly)
        painter.restore()
        if p.hiss > .05:
            light, dark = QColor(L['fur'][0]), qc(L['outline'])
            self._bristle(painter, body, 2 + 7 * p.hiss * (1 - .6 * Q), light, dark, .03, .5)
        self._leg(painter, False, 0, far=False)
        paw_in_front = S > .3
        if not paw_in_front:
            self._leg(painter, True, math.pi, far=False)
        hx, hy = self._stand_head()
        if A > .05:
            self._neck(painter, QPointF(fx - 12, end_f - 6), hx, hy, A, 10)
        if L.get('fluffy'):
            self._ruff(painter)
        self._head(painter, hx, hy, self.head_angle(), counter_turn=True)
        if paw_in_front:
            self._leg(painter, True, math.pi, far=False)
        painter.restore()

    def _neck(self, painter, base, hx, hy, amount, bow):
        L = self.look
        head = QPointF(hx - 4, hy - 4)
        neck = QPainterPath(base)
        neck.cubicTo(QPointF(base.x() + 18, base.y() - bow), QPointF(head.x() - 30, head.y() + bow), head)
        width = 22 * min(1, amount * 1.6)
        self._stroke(painter, neck, L['outline'], QColor(L['fur'][1]), width)
        if L['stripes']:
            painter.setPen(QPen(qc(L['stripes'], 170), 3.4, Qt.SolidLine, Qt.FlatCap))
            for t in (.3, .5, .7):
                pt = neck.pointAtPercent(t); angle = math.radians(neck.angleAtPercent(t))
                nx, ny = -math.sin(angle) * width * .45, -math.cos(angle) * width * .45
                painter.drawLine(QPointF(pt.x() - nx, pt.y() - ny), QPointF(pt.x(), pt.y()))

    def _patterns(self, painter, rx, fx, top, belly):
        """Breed coat patterns, already clipped to the body or ball outline."""
        L = self.look
        h = belly - top
        for shape, color in L['patches']:
            if shape == 'rump':
                self.fill(painter, self.path([(rx - 10, top + h * .1), (rx + 20, top - 12, rx + 52, top - 6, rx + 50, top + h * .45),
                          (rx + 48, top + h * .8, rx + 20, top + h * .95, rx - 10, top + h * .8)]),
                          self.brush(color, rx, top, rx + 50, belly), None)
            elif shape == 'shoulder':
                self.fill(painter, self.path([(rx + 58, top - 6), (rx + 82, top - 10, fx + 4, top + 4, fx - 6, top + h * .4),
                          (fx - 16, top + h * .62, rx + 74, top + h * .55, rx + 66, top + h * .3), (rx + 62, top + h * .15, rx + 56, top + 4, rx + 58, top - 6)]),
                          self.brush(color, 0, top, 0, belly), None)
            elif shape == 'belly':
                self.fill(painter, self.path([(rx - 20, belly + 20), (rx - 20, belly - h * .25), (rx + 30, belly - h * .42, fx - 30, belly - h * .42, fx + 20, belly - h * .3), (fx + 20, belly + 20)]), QColor(color), None)
            elif shape == 'chest':
                painter.setPen(Qt.NoPen); painter.setBrush(QColor(color))
                painter.drawEllipse(QRectF(fx - 34, top + h * .32, 40, h * .8))
            elif shape == 'saddle':
                soft = QLinearGradient(0, top - 4, 0, top + h * .65)
                soft.setColorAt(0, qc(color)); soft.setColorAt(1, qc(color, 0))
                painter.setPen(Qt.NoPen); painter.setBrush(soft)
                painter.drawRect(QRectF(rx - 20, top - 20, fx - rx + 40, h + 40))
        if L['stripes']:
            stripe = qc(L['stripes'], 175)
            painter.setBrush(Qt.NoBrush)
            for k in range(7):
                x = rx + 14 + k * (fx - rx - 28) / 6
                painter.setPen(QPen(stripe, 4.5 + (k % 3) * .8, Qt.SolidLine, Qt.RoundCap))
                painter.drawPath(self.path([(x + 3, top - 8), (x - 4, top + h * .25, x + 1, top + h * .42 + (k % 2) * 4)]))
        sr, sg, sb = L['sheen']
        painter.setPen(QPen(QColor(sr, sg, sb, 70), 2.2, Qt.SolidLine, Qt.RoundCap)); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path([(rx + 22, top + 9), (rx + 45, top + 1, rx + 70, top + 2)]))

    def _bristle(self, painter, contour, length, light, dark, start=.04, end=.98):
        p = self.pose
        count = 30
        for i in range(count):
            t = start + (end - start) * i / (count - 1)
            pt = contour.pointAtPercent(t); angle = math.radians(contour.angleAtPercent(t))
            nx, ny = -math.sin(angle), -math.cos(angle)
            spike = length * (.65 + .35 * math.sin(i * 2.7 + p.clock * 29))
            tip = QPointF(pt.x() + nx * spike, pt.y() + ny * spike)
            tri = QPainterPath(QPointF(pt.x() - math.cos(angle) * 3, pt.y() + math.sin(angle) * 3))
            tri.lineTo(tip); tri.lineTo(QPointF(pt.x() + math.cos(angle) * 3, pt.y() - math.sin(angle) * 3))
            self.fill(painter, tri, light, dark.name(), 1.1)

    def _fluff(self, painter, body):
        L = self.look
        painter.setPen(QPen(qc(L['outline'], 120), .9)); painter.setBrush(QColor(L['fur'][2]).lighter(106))
        for i in range(7):
            pt = body.pointAtPercent(.6 + i * .03)
            painter.drawEllipse(QRectF(pt.x() - 5, pt.y() - 5, 10, 9 + (i % 2) * 2))

    def _ruff(self, painter):
        L = self.look
        p = self.pose
        hx, hy = self._stand_head()
        cx, cy = hx - 8, hy + 24
        painter.setPen(QPen(qc(L['outline'], 110), .9)); painter.setBrush(QColor('#fffdf8'))
        for dx, dy, r in [(-10, 0, 9), (8, 0, 9), (-5, 8, 9), (5, 9, 9), (0, 15, 7)]:
            painter.drawEllipse(QRectF(cx + dx - r, cy + dy - r, r * 2, r * 2))
        painter.setPen(Qt.NoPen); painter.drawEllipse(QRectF(cx - 13, cy - 7, 26, 22))

    def _tail(self, painter):
        p, L = self.pose, self.look
        rx, fx, top, belly, end_r, end_f = self._body_geometry()
        Q = self.w('crouch')
        points = [(rx + 8 + p.hiss * 4, lerp(end_r - 4, end_r - 14, p.hiss) + Q * 10)]
        seg = 17 * (1 - .3 * p.hiss + .3 * Q)
        for angle in self.tail:
            previous = points[-1]
            points.append((previous[0] - math.cos(angle) * seg, previous[1] + math.sin(angle) * seg))
        path = QPainterPath(QPointF(*points[0]))
        for i in range(1, len(points)):
            previous, point = points[i - 1], points[i]
            path.quadTo(previous[0], previous[1], (previous[0] + point[0]) / 2, (previous[1] + point[1]) / 2)
        path.lineTo(*points[-1])
        puff = 1 + p.hiss * 1.1 * (1 - .6 * Q) + (.4 if L.get('fluffy') else 0)
        outline, main, ring = L['tail']
        if p.hiss > .05:
            self._bristle(painter, path, 4 + 6 * p.hiss, QColor(main), qc(outline), .1, .98)
            mirror = QPainterPath(path)
            self._bristle(painter, mirror.toReversed(), 4 + 6 * p.hiss, QColor(main), qc(outline), .02, .9)
        self._stroke(painter, path, outline, main, 11 * puff)
        if ring:
            painter.setPen(QPen(QColor(ring), 4 * puff if L.get('tail_style') == 'rings' else 7, Qt.SolidLine, Qt.RoundCap))
            stops = (.3, .5, .7, .88) if L.get('tail_style') == 'rings' else (.45, .9)
            for t in stops:
                pt = path.pointAtPercent(t); angle = math.radians(path.angleAtPercent(t))
                n = 4.6 * puff if L.get('tail_style') == 'rings' else 1.5
                nx, ny = -math.sin(angle) * n, -math.cos(angle) * n
                painter.drawLine(QPointF(pt.x() - nx, pt.y() - ny), QPointF(pt.x() + nx, pt.y() + ny))

    def _leg(self, painter, front, offset, far=False):
        p, L = self.pose, self.look
        rx, fx, top, belly, end_r, end_f = self._body_geometry()
        phase = p.phase + offset
        hip_x = fx - 22 if front else rx + 22
        hip_y = (end_f + 18 if front else end_r + 14) + p.squat * (2 if front else 6)
        A, C, Q, S = self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe')
        if p.hiss: hip_y = lerp(hip_y, (end_f + 14) if front else (end_r + 12), p.hiss)
        hip_y = min(hip_y, GROUND - 14)
        # Lifted (swing) paw travels forward, planted (stance) paw slides back.
        toe_x = hip_x - math.cos(phase) * 14 * p.gait + (4 if front else -2)
        toe_y = GROUND - max(0, math.sin(phase)) * 13 * p.gait
        toe_x += p.hiss * (12 if front else -12) + C * (14 if front else -14) + A * (6 if front else -6) + Q * (10 if front else -2) - S * (4 if front else 8)
        toe_y -= self._hop()
        if front:
            toe_x = blend(toe_x, fx + 18 + (4 if far else -6) + math.sin(p.clock * 17) * 1.5, p.cuddle, 6)
            toe_y = blend(toe_y, 88 + (6 if far else 0), p.cuddle, 6)
            toe_x = lerp(toe_x, hip_x + 16, p.eat * .5)
        else:
            toe_x += p.cuddle * (10 + math.sin(p.clock * 15 + offset) * 5)
            toe_y -= p.cuddle * 14
        if p.held:
            # Dangle: paws swing loosely under the hips.
            toe_x = lerp(toe_x, hip_x + math.sin(p.clock * 4 + offset) * 4, p.held)
            toe_y = lerp(toe_y, hip_y + 36, p.held)
        raised = S if (front and not far) else 0
        if raised > .01:
            # Paw up and cocked; every so often a quick swat forward.
            beat = (p.clock * .85) % 1
            strike = math.sin(beat / .2 * math.pi) if beat < .2 else 0
            toe_x = lerp(toe_x, hip_x + 40 + strike * 16, raised)
            toe_y = lerp(toe_y, hip_y - 6 - strike * 8 + math.sin(p.clock * 6) * 1.5, raised)
        if far: hip_x += 9; toe_x += 8; toe_y -= 3
        dx, dy = toe_x - hip_x, toe_y - hip_y
        distance = max(1, math.hypot(dx, dy))
        segment = 18 + p.hiss * 6 + A * 18
        reach = min(segment * 1.98, distance)
        mid_x, mid_y = hip_x + dx * .5, hip_y + dy * .5
        height = math.sqrt(max(0, segment * segment - (reach * .5) ** 2))
        bend = -.4 if front else -1
        knee_x = mid_x + dy / distance * height * bend
        knee_y = mid_y - dx / distance * height * bend
        path = self.path([(hip_x, hip_y), (knee_x, knee_y, toe_x, toe_y)])
        if far and 'legs_far' in L:
            outline, top_c, bottom_c = L['legs_far']
        else:
            outline, top_c, bottom_c = L['legs']
            if far: top_c, bottom_c = QColor(top_c).darker(118).name(), QColor(bottom_c).darker(112).name()
        gradient = QLinearGradient(hip_x, hip_y, toe_x, toe_y)
        gradient.setColorAt(0, QColor(top_c)); gradient.setColorAt(1, QColor(bottom_c))
        self._stroke(painter, path, outline, gradient, 13)
        if L['stripes']:
            painter.setPen(QPen(qc(L['stripes'], 170), 3, Qt.SolidLine, Qt.FlatCap))
            for t in (.4, .62):
                pt = path.pointAtPercent(t); angle = math.radians(path.angleAtPercent(t))
                nx, ny = -math.sin(angle) * 6, -math.cos(angle) * 6
                painter.drawLine(QPointF(pt.x() - nx, pt.y() - ny), QPointF(pt.x() + nx, pt.y() + ny))
        near_paw, far_paw, paw_line = L['paw']
        self.fill(painter, self.path([(toe_x - 8, toe_y + 3), (toe_x - 9, toe_y - 6, toe_x + 9, toe_y - 7, toe_x + 10, toe_y + 3), (toe_x - 8, toe_y + 3)]),
                  far_paw if far else near_paw, paw_line, 1.3)
        painter.setPen(QPen(qc(paw_line, 150), .9))
        for n in (-2.5, 2.5):
            painter.drawLine(QPointF(toe_x + n + 1, toe_y + 3), QPointF(toe_x + n + 1, toe_y))
        if raised > .3:
            painter.setPen(QPen(QColor(255, 255, 250, int(255 * raised)), 1.4, Qt.SolidLine, Qt.RoundCap))
            for n in (-3, 0, 3):
                painter.drawLine(QPointF(toe_x + 9, toe_y + n), QPointF(toe_x + 13, toe_y + n - 1.5))
            painter.setPen(QPen(qc(paw_line, int(200 * raised)), .6))
            for n in (-3, 0, 3):
                painter.drawLine(QPointF(toe_x + 9, toe_y + n), QPointF(toe_x + 13, toe_y + n - 1.5))

    # ------------------------------------------------------------------ curled sleep
    def _paint_curled(self, painter):
        p, L = self.pose, self.look
        painter.save()
        self._turn(painter, 118, 130)
        breath = self._breath()
        cx, cy, rx, ry = 116, 117 - breath * .5, 60 + breath * .4, 31 + breath * .7
        ball = QPainterPath(); ball.addEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
        outline, main, ring = L['tail']
        self.fill(painter, ball, self.brush(L['fur'], 100, cy - ry, 110, cy + ry), L['outline'])
        painter.save(); painter.setClipPath(ball)
        self._patterns(painter, cx - rx + 4, cx + rx - 4, cy - ry, cy + ry)
        painter.restore()
        # Front paw tucked under the chin.
        near_paw, far_paw, paw_line = L['paw']
        self.fill(painter, self.path([(146, 141), (146, 132, 166, 131, 168, 140), (158, 145, 150, 145, 146, 141)]), near_paw, paw_line, 1.3)
        # Tail wraps around the front of the ball.
        tail = self.path([(cx - rx + 6, cy + 8), (cx - rx + 4, cy + ry + 6, cx + 10, cy + ry + 4, cx + 40, cy + ry - 2),
                          (cx + 56, cy + ry - 6, cx + 64, cy + ry - 14, cx + 58, cy + ry - 20)])
        self._stroke(painter, tail, outline, main, 12 + (5 if L.get('fluffy') else 0))
        if ring:
            painter.setPen(QPen(QColor(ring), 4, Qt.SolidLine, Qt.RoundCap))
            stops = (.25, .45, .65, .85) if L.get('tail_style') == 'rings' else (.95,)
            for t in stops:
                pt = tail.pointAtPercent(t); angle = math.radians(tail.angleAtPercent(t))
                nx, ny = -math.sin(angle) * 5, -math.cos(angle) * 5
                painter.drawLine(QPointF(pt.x() - nx, pt.y() - ny), QPointF(pt.x() + nx, pt.y() + ny))
        self._head(painter, 160, 116 + breath * .4, 12, counter_turn=True, asleep=True)
        painter.restore()

    # ------------------------------------------------------------------ head
    def _face_mark(self, painter, shape, color):
        if shape == 'cal_left':
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color)); painter.drawEllipse(QRectF(-44, -40, 40, 40))
        elif shape == 'cal_right':
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color)); painter.drawEllipse(QRectF(3, -42, 40, 36))
        elif shape == 'cap':
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color)); painter.drawEllipse(QRectF(-42, -52, 84, 40))
        elif shape == 'chin':
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color)); painter.drawEllipse(QRectF(-16, 4, 32, 26))
        elif shape == 'mstripes':
            painter.setBrush(Qt.NoBrush); painter.setPen(QPen(QColor(color), 3, Qt.SolidLine, Qt.RoundCap))
            for x in (-8, 0, 8):
                painter.drawLine(QPointF(x, -27), QPointF(x * 1.1, -17 + abs(x) * .3))
            for side in (-1, 1):
                for i in range(2):
                    painter.drawPath(self.path([(side * 36, -2 + i * 7), (side * 30, -4 + i * 7, side * 25, 0 + i * 7)]))
        elif shape == 'mask':
            gradient = QRadialGradient(0, 8, 28)
            gradient.setColorAt(0, qc(color)); gradient.setColorAt(.55, qc(color, 210)); gradient.setColorAt(1, qc(color, 0))
            painter.setPen(Qt.NoPen); painter.setBrush(gradient); painter.drawEllipse(QRectF(-32, -20, 64, 56))
        elif shape == 'vmask':
            gradient = QRadialGradient(0, -8, 36)
            gradient.setColorAt(0, qc(color)); gradient.setColorAt(.7, qc(color, 160)); gradient.setColorAt(1, qc(color, 40))
            painter.setPen(Qt.NoPen); painter.setBrush(gradient); painter.drawEllipse(QRectF(-40, -44, 80, 62))
            self.fill(painter, self.path([(0, -20), (-3, -8, -16, 10, -24, 32), (24, 32), (16, 10, 3, -8, 0, -20)]), '#fffaf3')

    def _head(self, painter, hx, hy, angle, counter_turn=True, asleep=False):
        p, L = self.pose, self.look
        painter.save()
        painter.translate(hx, hy)
        if counter_turn:
            projection = (.30 + .70 * abs(p.facing)) * (1 if p.facing >= 0 else -1)
            painter.scale(1 / projection, 1)
        painter.rotate(angle)
        outline = L['outline']
        ear_outer, ear_fur, ear_pink = L['ear']
        hiss = 0 if asleep else p.hiss
        flick = (math.sin(p.clock * 2.1) * 1.5 + max(0, math.sin(p.clock * 1.13)) ** 22 * 10) * (1 - hiss)
        for side in (-1, 1):
            painter.save()
            painter.translate(side * 19, -19)
            # Airplane ears: flat out to the sides when frightened.
            painter.rotate(side * (flick + p.playful * 4 + hiss * 62 + (14 if asleep else 0)))
            painter.scale(1, 1 - hiss * .25)
            ear = self.path([(-12, 6), (-12, -8, -7, -22, -2, -25), (3, -22, 12, -8, 12, 6), (-12, 6)])
            notch = self.neutered and side == -1
            if notch:
                # TNR ear tip: neutered cats have the tip of one ear flattened.
                painter.setClipRect(QRectF(-20, -17, 40, 40))
            self.fill(painter, ear, ear_outer, outline)
            self.fill(painter, self.path([(-7, 3), (-7, -7, -4, -16, -2, -18), (1, -16, 7, -7, 7, 3), (-7, 3)]), ear_pink)
            if notch:
                painter.setClipping(False)
                painter.setPen(QPen(qc(outline), 1.6, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(QPointF(-9.6, -17), QPointF(7.6, -17))
            painter.restore()
        face = self.path([(0, -28), (21, -28, 35, -17, 36, -1), (37, 15, 22, 26, 0, 26),
                          (-22, 26, -37, 15, -36, -1), (-35, -17, -21, -28, 0, -28)])
        if L.get('fluffy'):
            painter.setPen(QPen(qc(outline), 1.2)); painter.setBrush(QColor(L['face'][1]))
            for side in (-1, 1):
                painter.drawPath(self.path([(side * 30, 2), (side * 43, 10, side * 38, 15), (side * 43, 21, side * 28, 22), (side * 24, 12)]))
        self.fill(painter, face, self.brush(L['face'], 0, -28, 0, 26), outline)
        painter.save(); painter.setClipPath(face)
        for shape, color in L['face_marks']:
            self._face_mark(painter, shape, color)
        painter.restore()
        # Blush.
        A, C, Q, S = (0, 0, 0, 0) if asleep else (self.w('arch'), self.w('crab'), self.w('crouch'), self.w('swipe'))
        blush = (45 if self.breed == 'black' else 75) * (1 - hiss)
        if blush > 2:
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(255, 120, 130, int(blush)))
            for side in (-1, 1): painter.drawEllipse(QRectF(side * 22 - 6, 7, 12, 6))
        if hiss > .05:
            # Angry wrinkles on the nose bridge.
            painter.setPen(QPen(qc(outline, int(200 * hiss)), 1.2, Qt.SolidLine, Qt.RoundCap)); painter.setBrush(Qt.NoBrush)
            for i in range(3):
                painter.drawPath(self.path([(-5 + i * .5, -1 + i * 2.2), (0, -2.5 + i * 2.2, 5 - i * .5, -1 + i * 2.2)]))
        closed = 1 if asleep else clamp(max(p.blink, p.affection), 0, 1) * (1 - hiss)
        happy = (not asleep) and p.affection > .5
        for index, (ex, (iris_top, iris_bottom)) in enumerate(zip((-13, 13), L['eyes'])):
            if closed > .8:
                painter.setPen(QPen(qc(outline), 2, Qt.SolidLine, Qt.RoundCap)); painter.setBrush(Qt.NoBrush)
                if happy:
                    painter.drawPath(self.path([(ex - 6, 2), (ex, -4, ex + 6, 2)]))
                else:
                    painter.drawPath(self.path([(ex - 6, -1), (ex, 4, ex + 6, -1)]))
                continue
            open_y = 1 - closed
            # Crab: one eye wide open, the other squinting.
            size = 1 + C * (.2 if index == 1 else -.1)
            painter.save(); painter.translate(ex, -1); painter.scale(size, open_y * size * (1 - C * (.4 if index == 0 else 0)))
            eye = QPainterPath(); eye.addEllipse(QRectF(-6.5, -8, 13, 16))
            # Irises fade to bloodshot white: tiny-pupil psycho stare.
            iris = QLinearGradient(0, -8, 0, 8)
            iris.setColorAt(0, lerp_color(iris_top, '#fbf7ef', hiss * .85)); iris.setColorAt(1, lerp_color(iris_bottom, '#f3e3dc', hiss * .85))
            self.fill(painter, eye, iris, '#2a2522', 1.3 / size)
            painter.save(); painter.setClipPath(eye)
            if hiss > .3:
                painter.setPen(QPen(QColor(220, 70, 70, int(150 * hiss)), .5))
                for k in range(3):
                    painter.drawLine(QPointF(-6 + k, 3 - k * 3), QPointF(-2 + k, 1 - k * 2))
            pw = lerp(7 + p.playful * 2, 2.2, hiss); ph = lerp(11, 2.2, hiss)
            jitter = math.sin(p.clock * 37 + index * 2) * .8 * C
            px = p.look_x * 1.8 + hiss * 3.4 + jitter
            py = p.look_y * 1.5 - hiss * 1 + jitter * .5
            painter.setPen(Qt.NoPen); painter.setBrush(QColor('#1d1d22'))
            painter.drawEllipse(QRectF(px - pw / 2, py - ph / 2, pw, ph))
            painter.setBrush(QColor(255, 255, 255, int(235 * (1 - hiss))))
            painter.drawEllipse(QRectF(-3.6, -5.2, 4, 4)); painter.drawEllipse(QRectF(1.4, 1.5, 2, 2))
            lid_amount = hiss * (1 - C * .6)
            if lid_amount > .05:
                # Flat, slanted lids: the infamous side-eye.
                lid_color = QColor(L['face'][0])
                inner = 1 if ex < 0 else -1
                y_out, y_in = lerp(-10, -1 - inner * 2.5, lid_amount), lerp(-10, -1 + inner * 2.5, lid_amount)
                lid = self.path([(-9, -10), (9, -10), (9, y_out), (-9, y_in), (-9, -10)])
                self.fill(painter, lid, lid_color)
                painter.setPen(QPen(qc(outline), 1.8)); painter.drawLine(QPointF(-9, y_in), QPointF(9, y_out))
            painter.restore(); painter.restore()
        if hiss > .05:
            painter.setPen(QPen(qc(outline), 1 + 2.2 * hiss, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(-21, -11), QPointF(-6, -5 - hiss * 2)); painter.drawLine(QPointF(21, -11), QPointF(6, -5 - hiss * 2))
        # Muzzle, nose, mouth.
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(L['muzzle']))
        painter.drawEllipse(QRectF(-10, 6, 11, 10)); painter.drawEllipse(QRectF(-1, 6, 11, 10))
        self.fill(painter, self.path([(-4, 6), (0, 5, 4, 5, 4, 6), (2, 9.5, -2, 9.5, -4, 6)]), L['nose'][0], L['nose'][1], 1)
        jaw = 0 if asleep else (math.sin(p.clock * 20) + 1) * (p.cuddle * 1.6 + p.eat * 2.2)
        mouth_pen = QPen(qc(L['mouth']), 1.4, Qt.SolidLine, Qt.RoundCap)
        if hiss > .15:
            gape = 4 + 7 * hiss + 3 * A + 2 * Q + 3 * S + math.sin(p.clock * 7) * 1
            painter.setPen(mouth_pen); painter.setBrush(QColor('#6b2f35'))
            painter.drawPath(self.path([(-8, 11), (-6, 11 + gape * 1.2, 6, 11 + gape * 1.2, 8, 11), (0, 10, -8, 11)]))
            painter.setPen(Qt.NoPen); painter.setBrush(QColor('#e48d96'))
            painter.drawEllipse(QRectF(-3, 11 + gape * .55, 6, gape * .5))
            painter.setBrush(QColor('#fffdf6'))
            for fx in (-5, 5):
                painter.drawPath(self.path([(fx - 1.8, 11), (fx + 1.8, 11), (fx, 11 + 3.6 * hiss), (fx - 1.8, 11)]))
        else:
            painter.setPen(mouth_pen); painter.setBrush(QColor('#c9858a'))
            if jaw > .5: painter.drawEllipse(QRectF(-2.5, 11, 5, 1 + jaw))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.path([(0, 9), (0, 12), (-2, 14, -5, 13.5, -6, 11.5)]))
            painter.drawPath(self.path([(0, 12), (2, 14, 5, 13.5, 6, 11.5)]))
        wr, wg, wb, wa = L['whisker']
        painter.setPen(QPen(QColor(wr, wg, wb, wa), .9, Qt.SolidLine, Qt.RoundCap)); painter.setBrush(Qt.NoBrush)
        for side in (-1, 1):
            for i in range(3):
                droop = hiss * 3
                painter.drawPath(self.path([(side * 12, 9 + i * 2.5), (side * 26, 7 + i * 4 + droop, side * 40, 5 + i * 6 + droop * 1.5)]))
        painter.restore()
