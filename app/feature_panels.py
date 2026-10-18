"""Scene and device countdown controls; no desktop scheduling loop."""
import math
import time
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QAbstractSpinBox, QDialog, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget)
from light_features import decode_scene, scene_options
from theme import heading, surface
from time_inputs import DurationInput


class ScenesPanel(QWidget):
    def __init__(self, card):
        super().__init__(card)
        self.card, self.signature, self.buttons = card, None, []
        layout = QVBoxLayout(self)
        self.current = QLabel("Choisis une ambiance")
        self.current.setWordWrap(True)
        layout.addWidget(self.current)
        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        self.note = QLabel("Scènes reçues de LSC et ambiances proposées.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch()
        self.show_state({})

    def show_state(self, state):
        scenes = state.get("scenes") or scene_options(self.card.rgb)
        signature = tuple((x["id"],x["name"],x["data"],x.get("received")) for x in scenes)
        if signature != self.signature:
            self.signature = signature
            while self.grid.count():
                old = self.grid.takeAt(0)
                if old.widget(): old.widget().deleteLater()
            self.buttons = []
            for index, scene in enumerate(scenes):
                button = QPushButton(scene["name"])
                button.setCheckable(True)
                button.setMinimumHeight(48)
                button.setToolTip("Derniers réglages reçus de LSC" if scene.get("received") else "Ambiance proposée")
                button.clicked.connect(lambda checked=False, raw=scene["data"]:
                    self.card.window.command(self.card.slot,"scene",raw))
                self.grid.addWidget(button,index//2,index%2)
                self.buttons.append((scene,button))
        active = decode_scene(state.get("scene_data")) if state.get("mode")=="scene" else None
        name = None
        for scene,button in self.buttons:
            selected = bool(active and scene["data"]==active["data"])
            button.setChecked(selected)
            if selected: name=scene["name"]
        self.current.setText("Scène active : " + name if name else "Choisis une ambiance")


class Countdown(QDialog):
    def __init__(self, card):
        super().__init__(card)
        self.card, self.ticks = card, 0
        self.awaiting = None
        self.setWindowTitle("Compte à rebours · " + card.title())
        self.setMinimumWidth(510)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,20)
        layout.setSpacing(16)
        heading(layout,"Compte à rebours","Jusqu’au changement d’état de l’ampoule.")
        display = surface(layout)
        self.status = QLabel()
        self.status.setObjectName("countdownValue")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display.addWidget(self.status)
        self.remaining_caption = QLabel()
        self.remaining_caption.setObjectName("muted")
        self.remaining_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display.addWidget(self.remaining_caption)
        fields = QHBoxLayout()
        fields.setSpacing(12)
        self.hours,self.minutes,self.seconds = DurationInput(),DurationInput(),DurationInput()
        for field,maximum,unit in ((self.hours,24,"h"),(self.minutes,59,"min"),(self.seconds,59,"s")):
            field.setRange(0,maximum)
            field.setObjectName("durationInput")
            field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            field.setAccessibleName({"h":"Heures","min":"Minutes","s":"Secondes"}[unit])
            column = QVBoxLayout()
            column.setSpacing(6)
            column.addWidget(field)
            label = QLabel(unit)
            label.setObjectName("fieldLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(label)
            fields.addLayout(column,1)
        self.minutes.setValue(15)
        layout.addLayout(fields)
        presets = QHBoxLayout()
        for minutes in (5,15,30,60):
            button = QPushButton(f"{minutes} min")
            button.setProperty("role","preset")
            button.clicked.connect(lambda checked=False,m=minutes:self.set_duration(m*60))
            presets.addWidget(button)
        layout.addLayout(presets)
        self.message = QLabel()
        self.message.setObjectName("muted")
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(20)
        layout.addWidget(self.message)
        footer = QHBoxLayout()
        close = QPushButton("Fermer")
        close.setProperty("role","ghost")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        footer.addStretch()
        cancel = QPushButton("Annuler le minuteur")
        cancel.clicked.connect(lambda:self.send(0))
        footer.addWidget(cancel)
        start = QPushButton("Démarrer")
        start.setProperty("role","primary")
        start.setDefault(True)
        start.clicked.connect(self.start)
        footer.addWidget(start)
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        if hasattr(card.window,"results"):
            card.window.results.ready.connect(self.complete)
        self.update_remaining()

    def set_duration(self, seconds):
        self.hours.setValue(seconds//3600)
        self.minutes.setValue(seconds//60%60)
        self.seconds.setValue(seconds%60)

    def start(self):
        value=self.hours.value()*3600+self.minutes.value()*60+self.seconds.value()
        if not 1<=value<=86400:
            self.message.setText("Durée : de 1 seconde à 24 heures.")
            return
        self.send(value)

    def send(self,value):
        self.awaiting=value
        self.card.window.command(self.card.slot,"countdown",value)
        self.message.setText("Annulation…" if value==0 else "Démarrage…")

    def complete(self,context,payload):
        if context != ("command",self.card.slot,"countdown") or self.awaiting is None:
            return
        states,error=payload
        if error:
            self.message.setText(error)
            self.awaiting=None
            return
        for state in states:
            raw=state.get("countdown")
            if state.get("slot")==self.card.slot and type(raw) is int:
                if self.awaiting==0 and raw==0:
                    self.message.setText("Compte à rebours annulé.")
                    self.awaiting=None
                elif self.awaiting>0 and 0<raw<=self.awaiting:
                    self.message.setText("Compte à rebours lancé.")
                    self.awaiting=None
        self.update_remaining()

    def update_remaining(self):
        raw = self.card.countdown_raw
        if raw is None:
            self.status.setText("--:--:--")
            self.remaining_caption.setText("Actualisation…")
        elif raw==0:
            self.status.setText("00:00:00")
            self.remaining_caption.setText("Aucun compte à rebours actif")
        else:
            left=max(0,math.ceil(raw-(time.monotonic()-self.card.countdown_read_at)))
            text=f"{left//3600:02d}:{left//60%60:02d}:{left%60:02d}"
            self.status.setText(text)
            self.remaining_caption.setText("Temps restant · estimé" if left else "Changement d’état en cours…")

    def tick(self):
        self.update_remaining()
        self.ticks+=1
        window=self.card.window
        if self.ticks%5==0 and hasattr(window,"refresh") and not window.busy:
            window.refresh(observe=True)

    def done(self,result):
        self.timer.stop()
        if hasattr(self.card.window,"results"):
            self.card.window.results.ready.disconnect(self.complete)
        super().done(result)
