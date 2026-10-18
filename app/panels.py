"""Lamp controls inspired by the user's LSC mobile screenshots."""
import math
import time
from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSlider, QTabWidget, QVBoxLayout, QWidget,
)


class LightRing(QWidget):
    changed = Signal(float)
    released = Signal()
    powerClicked = Signal()

    def __init__(self, colour=False, parent=None):
        super().__init__(parent)
        self.colour = colour
        self.value = 0.0 if colour else 20.0
        self.saturation = 100.0
        self.brightness = 100.0
        self.power = False
        self.dragging = False
        self.setMinimumSize(245, 245)
        self.setMaximumHeight(300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def geometry_values(self):
        return QPointF(self.width() / 2, self.height() / 2), min(self.width(), self.height()) * .38

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        centre, radius = self.geometry_values()
        width = radius * .30
        bounds = QRectF(centre.x()-radius, centre.y()-radius, radius*2, radius*2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.colour:
            gradient = QConicalGradient(centre, 0)
            for i in range(13):
                gradient.setColorAt(i/12, QColor.fromHsvF((i/12) % 1, 1, 1))
            painter.setPen(QPen(gradient, width))
            painter.drawEllipse(bounds)
            angle = self.value
            fill = QColor.fromHsvF((self.value % 360)/360, self.saturation/100, max(.1, self.brightness/100))
        else:
            # Upper 270 degrees: warm at bottom left, cool at bottom right.
            for i in range(270):
                fraction = i/269
                warm, cool = QColor('#ffd474'), QColor('#d1efff')
                colour = QColor(*(round(a+(b-a)*fraction) for a, b in zip(warm.getRgb()[:3], cool.getRgb()[:3])))
                painter.setPen(QPen(colour, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawArc(bounds, round((225-i)*16), -17)
            angle = 225 - self.value * 2.7
            warm, cool = QColor('#ffc889'), QColor('#d1efff')
            fill = QColor(*(round(a+(b-a)*self.value/100) for a, b in zip(warm.getRgb()[:3], cool.getRgb()[:3])))
        handle = QPointF(centre.x()+radius*math.cos(math.radians(angle)), centre.y()-radius*math.sin(math.radians(angle)))
        painter.setPen(QPen(QColor('#ffffff'), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(handle, width*.47, width*.47)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill if self.power else QColor('#312539'))
        painter.drawEllipse(centre, radius*.48, radius*.48)
        painter.setBrush(QColor('#ffffff' if self.power else '#bba4ce'))
        painter.drawEllipse(QRectF(centre.x()-13, centre.y()-26, 26, 29))
        painter.drawRoundedRect(QRectF(centre.x()-7, centre.y()-3, 14, 13), 3, 3)
        painter.drawRoundedRect(QRectF(centre.x()-6, centre.y()+13, 12, 3), 1, 1)
        painter.end()

    def choose(self, position):
        centre, radius = self.geometry_values()
        dx, dy = position.x()-centre.x(), centre.y()-position.y()
        angle = math.degrees(math.atan2(dy, dx)) % 360
        if self.colour:
            self.value = angle
        else:
            distance = (225-angle) % 360
            # Clamp the bottom gap to the closest end of the white arc.
            if distance > 270:
                distance = 270 if distance < 315 else 0
            self.value = distance / 2.7
        self.update()
        self.changed.emit(self.value)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        centre, radius = self.geometry_values()
        distance = math.hypot(event.position().x()-centre.x(), event.position().y()-centre.y())
        if distance < radius*.48:
            self.powerClicked.emit()
        elif radius*.70 <= distance <= radius*1.22:
            self.dragging = True
            self.choose(event.position())

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.choose(event.position())

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.choose(event.position())
            self.released.emit()


class LampCard(QGroupBox):
    def __init__(self, device, window):
        super().__init__(device['name'])
        self.window, self.slot, self.rgb = window, device['slot'], device['rgb']
        from lighting import capabilities
        self.capabilities = caps = capabilities(device)
        self.power = None
        self.syncing = False
        self.countdown_raw = None
        self.countdown_read_at = 0
        layout = QVBoxLayout(self)
        description = [label for key, label in (('rgb', 'Couleurs'), ('temperature', 'Blanc chaud et froid'), ('brightness', 'Luminosité')) if caps[key]]
        subtitle = QLabel(' · '.join(description) or 'Éclairage')
        subtitle.setObjectName('subtitle')
        layout.addWidget(subtitle)
        self.status = QLabel('État inconnu · connexion requise')
        self.status.setObjectName('status')
        layout.addWidget(self.status)
        self.tabs = QTabWidget()
        self.white = QWidget(self)
        white_layout = QVBoxLayout(self.white)
        self.white_ring = LightRing()
        self.white_ring.changed.connect(lambda value: self.white_label.setText(f'Blanc chaud → froid · {round(value)} %'))
        self.white_ring.released.connect(self.send_white)
        self.white_ring.powerClicked.connect(self.toggle)
        white_layout.addWidget(self.white_ring)
        self.white_label = QLabel('Blanc chaud → froid · 20 %')
        self.white_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        white_layout.addWidget(self.white_label)
        self.white_brightness = self.slider(white_layout, '☀  Luminosité', 100, 1)
        self.white_brightness.sliderReleased.connect(self.send_white)
        self.white_ring.setVisible(caps['temperature'])
        self.white_label.setVisible(caps['temperature'])
        self.white_brightness.setVisible(caps['brightness'])
        self.white_brightness.caption.setVisible(caps['brightness'])
        if caps['white']:
            self.tabs.addTab(self.white, 'Blanc')
        else:
            self.white.hide()
        if self.rgb:
            self.colour = QWidget()
            colour_layout = QVBoxLayout(self.colour)
            self.colour_ring = LightRing(colour=True)
            self.colour_ring.released.connect(self.send_colour)
            self.colour_ring.powerClicked.connect(self.toggle)
            colour_layout.addWidget(self.colour_ring)
            self.colour_brightness = self.slider(colour_layout, '☀  Luminosité', 100, 1)
            self.saturation = self.slider(colour_layout, '◐  Saturation', 100, 0)
            self.colour_brightness.valueChanged.connect(self.update_colour_preview)
            self.saturation.valueChanged.connect(self.update_colour_preview)
            self.colour_brightness.sliderReleased.connect(self.send_colour)
            self.saturation.sliderReleased.connect(self.send_colour)
            self.tabs.addTab(self.colour, 'Couleur')
        from feature_panels import ScenesPanel
        self.scene_panel = ScenesPanel(self)
        if caps['scenes']:
            self.tabs.addTab(self.scene_panel, 'Scène')
        else:
            self.scene_panel.hide()
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tabs.setVisible(self.tabs.count() > 0)
        layout.addWidget(self.tabs)
        bottom = QHBoxLayout()
        countdown = QPushButton('Compte à rebours')
        countdown.clicked.connect(self.countdown)
        countdown.setVisible(caps['countdown'])
        self.power_button = QPushButton('⏻  Allumer')
        self.power_button.setObjectName('powerButton')
        self.power_button.clicked.connect(self.toggle)
        planning = QPushButton('Planning…')
        planning.clicked.connect(self.planning)
        planning.setVisible(caps['planning'])
        self.power_button.setEnabled(caps['power'])
        bottom.addWidget(countdown)
        bottom.addWidget(self.power_button)
        bottom.addWidget(planning)
        layout.addLayout(bottom)
        self.controls = [self.tabs, self.white_ring, self.white_brightness, self.power_button]
        if self.rgb:
            self.controls += [self.colour_ring, self.colour_brightness, self.saturation]

    def slider(self, layout, title, value, minimum):
        label = QLabel(f'{title} · {value} %')
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.caption = label
        slider.setRange(minimum, 100)
        slider.setValue(value)
        slider.valueChanged.connect(lambda n: label.setText(f'{title} · {n} %'))
        layout.addWidget(label)
        layout.addWidget(slider)
        return slider

    def toggle(self):
        self.window.command(self.slot, 'power', not bool(self.power))

    def update_colour_preview(self, *args):
        self.colour_ring.saturation = self.saturation.value()
        self.colour_ring.brightness = self.colour_brightness.value()
        self.colour_ring.update()

    def send_white(self):
        if self.syncing:
            return
        if self.capabilities['white']:
            self.window.command(self.slot,'white',{'temperature':self.white_ring.value,'brightness':self.white_brightness.value()})

    def send_colour(self):
        if self.syncing:
            return
        self.window.command(self.slot, 'hsv', {'h': self.colour_ring.value, 's': self.saturation.value(), 'v': self.colour_brightness.value()})

    def tab_changed(self, index):
        if not self.syncing:
            if self.tabs.widget(index) is self.white:
                self.send_white()
            elif self.rgb and self.tabs.widget(index) is self.colour:
                self.send_colour()

    def show_state(self, state):
        # Don't overwrite a user's unfinished drag with a background read.
        if self.white_ring.dragging or self.white_brightness.isSliderDown():
            return
        if self.rgb and (self.colour_ring.dragging or self.colour_brightness.isSliderDown() or self.saturation.isSliderDown()):
            return
        self.syncing = True
        try:
            self.power = state['power']
            mode = state.get('mode', 'white')
            self.power_button.setText('⏻  Éteindre' if self.power else '⏻  Allumer')
            self.status.setText(('Allumée' if self.power else 'Éteinte') + ' · ' + {'colour':'couleur','scene':'scène','white':'blanc'}.get(mode,mode) + (' · simulation' if state.get('demo') else ' · état lu'))
            if state.get('online') is False:
                self.status.setText('Hors ligne · dernier état : ' + ('allumée' if self.power else 'éteinte'))
            self.white_ring.power = self.power
            countdown=state.get('countdown')
            if countdown != self.countdown_raw:
                self.countdown_raw,self.countdown_read_at=countdown,time.monotonic()
            self.scene_panel.show_state(state)
            if state.get('temperature') is not None:
                self.white_ring.value = max(0, min(100, state['temperature']))
                self.white_label.setText(f'Blanc chaud → froid · {round(self.white_ring.value)} %')
            if mode != 'colour' and state.get('brightness') is not None:
                self.white_brightness.setValue(max(1, min(100, round(state['brightness']))))
            self.white_ring.update()
            if self.rgb:
                self.colour_ring.power = self.power
                hsv = state.get('hsv')
                if hsv is not None:
                    self.colour_ring.value = hsv['h']
                    self.saturation.setValue(round(hsv['s']))
                    self.colour_brightness.setValue(max(1, round(hsv['v'])))
                self.update_colour_preview()
                if self.tabs.currentWidget() in (self.white, self.colour) and mode in ('white', 'colour'):
                    target = self.colour if mode == 'colour' else self.white
                    if self.tabs.indexOf(target) >= 0:
                        self.tabs.setCurrentWidget(target)
        finally:
            self.syncing = False

    def countdown(self):
        from feature_panels import Countdown
        Countdown(self).exec()

    def planning(self):
        from lsc_planning import Planning
        Planning(self.window.controller, self.slot, self).exec()
