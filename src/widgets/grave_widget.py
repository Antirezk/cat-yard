"""A little gravestone left where a kitten lost a fight. Stays until removed."""
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen, QFont, QLinearGradient
from PyQt5.QtWidgets import QWidget, QMenu
import surface
from preferences import tr


class GraveWidget(QWidget):
    def __init__(self, x, y, controller, breed='calico', date=''):
        super().__init__()
        self.controller, self.breed, self.date = controller, breed, date
        surface.configure(self, 'grave')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(54, 64)
        self.move(int(x - self.width() / 2), int(y - self.height() + 6))
        self.setToolTip(self._label())
        self.show(); surface.fit(self); surface.finish(self)

    def _label(self):
        from cat_art import breed_name
        name = tr(breed_name(self.breed, True), breed_name(self.breed, False))
        return tr(f'{name}小猫长眠于此 {self.date}', f'Here lies a little {name.lower()} {self.date}')

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # Ground mound.
        p.setPen(Qt.NoPen); p.setBrush(QColor(120, 98, 70, 90)); p.drawEllipse(QRectF(3, h - 14, w - 6, 12))
        # Stone.
        stone = QPainterPath(QPointF(10, h - 8))
        stone.lineTo(10, 22); stone.cubicTo(10, 4, w - 10, 4, w - 10, 22); stone.lineTo(w - 10, h - 8); stone.closeSubpath()
        grad = QLinearGradient(0, 4, 0, h); grad.setColorAt(0, QColor('#c9c6c0')); grad.setColorAt(1, QColor('#8f8b84'))
        p.setPen(QPen(QColor('#5e5b56'), 1.4)); p.setBrush(grad); p.drawPath(stone)
        # Tiny cat ears on top of the stone.
        p.setBrush(QColor('#b4b0aa'))
        for x in (17, w - 17):
            ear = QPainterPath(QPointF(x - 5, 12)); ear.lineTo(x, 3); ear.lineTo(x + 5, 12); ear.closeSubpath()
            p.drawPath(ear)
        p.setPen(QColor('#4a4743')); f = QFont('Arial', 7); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(10, 20, w - 20, 12), Qt.AlignCenter, 'R.I.P')
        p.setPen(QPen(QColor('#5e5b56'), 1.2))
        p.drawLine(QPointF(w / 2, 34), QPointF(w / 2, 44)); p.drawLine(QPointF(w / 2 - 4, 37), QPointF(w / 2 + 4, 37))
        # A small flower.
        p.setPen(QPen(QColor('#5c8a4a'), 1.2)); p.drawLine(QPointF(w - 9, h - 8), QPointF(w - 7, h - 18))
        p.setPen(Qt.NoPen); p.setBrush(QColor('#f2a3b3'))
        for dx, dy in ((0, -3), (3, 0), (0, 3), (-3, 0)):
            p.drawEllipse(QRectF(w - 9.5 + dx, h - 21.5 + dy, 4, 4))
        p.setBrush(QColor('#ffd75e')); p.drawEllipse(QRectF(w - 8.5, h - 20.5, 3, 3))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.controller.bubble.show_text(self._label(), 2500)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        title = menu.addAction(self._label()); title.setEnabled(False)
        menu.addSeparator()
        menu.addAction(tr('移走墓碑', 'Remove gravestone'), lambda: self.controller.remove_grave(self))
        menu.exec_(event.globalPos())
