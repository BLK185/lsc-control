"""Shared cloud schedule display, using the same timers as LSC mobile."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, QTime, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractSpinBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QWidget, QFrame,
                               QCheckBox, QComboBox, QLineEdit, QDialogButtonBox, QMessageBox)
from core import ControlError
from lsc_account import LSCAccount
from lsc_timers import save_timer, set_timer_status
from theme import heading, surface
from time_inputs import TimeInput


class PowerActionIcon(QWidget):
    def __init__(self, power, parent=None):
        super().__init__(parent)
        self.power = power
        self.setFixedSize(36,36)
        label = "Allumer" if power is True else "Éteindre" if power is False else "Réglages de l’ampoule"
        self.setToolTip(label)
        self.setAccessibleName(label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour, background = ("#4DD599","#18372D") if self.power is True else (("#F57586","#3C232C") if self.power is False else ("#AAA5B7","#292631"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(QRectF(0,0,36,36),10,10)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(colour),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(10,11,16,16),135*16,270*16)
        painter.drawLine(18,8,18,17)
        painter.end()


class TimerEditor(QDialog):
    def __init__(self, device, timer=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l’horaire" if timer else "Nouvel horaire")
        self.setMinimumWidth(550)
        timer = timer or {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,20)
        layout.setSpacing(18)
        heading(layout,"Modifier l’horaire" if timer else "Nouvel horaire",
                device.get("name","Ampoule") + " · synchronisé avec LSC")
        clock = surface(layout)
        label = QLabel("Heure")
        label.setObjectName("fieldLabel")
        clock.addWidget(label)
        clock_row = QHBoxLayout()
        self.time = TimeInput(QTime.fromString(timer.get("time", "06:00"), "HH:mm"))
        self.time.setDisplayFormat("HH:mm")
        self.time.setObjectName("timeInput")
        self.time.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time.setAccessibleName("Heure de l’horaire")
        clock_row.addWidget(self.time,1)
        self.power = QComboBox()
        self.power.addItem("Allumer", True)
        self.power.addItem("Éteindre", False)
        self.power.setAccessibleName("Action de l’ampoule")
        dps = timer.get("dps", {})
        if isinstance(dps, str):
            dps = json.loads(dps)
        switch = device["lsc_functions"]["switch_led"]["id"]
        self.power.setCurrentIndex(1 if dps.get(switch) is False else 0)
        clock_row.addWidget(self.power,1)
        clock.addLayout(clock_row)
        repetition = surface(layout)
        label = QLabel("Répéter")
        label.setObjectName("fieldLabel")
        repetition.addWidget(label)
        days = QHBoxLayout()
        days.setSpacing(7)
        self.days = {}
        loops = timer.get("loops", "0111110")
        for index, name in ((1,"Lun"),(2,"Mar"),(3,"Mer"),(4,"Jeu"),(5,"Ven"),(6,"Sam"),(0,"Dim")):
            box = QPushButton(name)
            box.setCheckable(True)
            box.setProperty("role","day")
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setAccessibleName({1:"Lundi",2:"Mardi",3:"Mercredi",4:"Jeudi",5:"Vendredi",6:"Samedi",0:"Dimanche"}[index])
            box.setChecked(len(loops)==7 and loops[index]=="1")
            self.days[index] = box
            days.addWidget(box,1)
        repetition.addLayout(days)
        hint = QLabel("Sans jour sélectionné : une seule fois.")
        hint.setObjectName("muted")
        repetition.addWidget(hint)
        options = surface(layout)
        self.alias = QLineEdit(timer.get("aliasName", ""))
        self.alias.setMaxLength(100)
        self.alias.setPlaceholderText("Remarque · facultatif")
        self.alias.setAccessibleName("Remarque facultative")
        options.addWidget(self.alias)
        self.notify = QCheckBox("Notification sur le téléphone")
        self.notify.setChecked(timer.get("isAppPush", True))
        options.addWidget(self.notify)
        self.enabled = QCheckBox("Horaire activé")
        self.enabled.setChecked(timer.get("status", 1)==1)
        options.addWidget(self.enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.button(QDialogButtonBox.StandardButton.Save).setProperty("role","primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setProperty("role","ghost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        loops = "".join("1" if self.days[index].isChecked() else "0" for index in range(7))
        return {"time":self.time.time().toString("HH:mm"), "loops":loops,
                "power":self.power.currentData(), "enabled":self.enabled.isChecked(),
                "notify":self.notify.isChecked(), "alias":self.alias.text()}


def timer_rows(groups):
    rows = []
    for category in groups:
        name = category.get("category", {}).get("category", "")
        enabled = category.get("category", {}).get("status", 1)
        for group in category.get("groups", []):
            for timer in group.get("timers", []):
                rows.append(dict(timer, group_id=group.get("id"), category=name, category_status=enabled))
    return sorted(rows, key=lambda row: (row.get("time", ""), str(row.get("timerId", ""))))


def repeat_label(loops):
    if loops in ("0", "0000000", ""):
        return "Une seule fois"
    if loops == "0111110":
        return "Du lundi au vendredi"
    if loops == "1111111":
        return "Tous les jours"
    if len(loops) != 7 or set(loops) - {"0", "1"}:
        return "Répétition inconnue"
    names = ("Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam")
    return ", ".join(name for name, active in zip(names, loops) if active == "1")


class PlanningSignals(QObject):
    ready = Signal(object, object)


class Planning(QDialog):
    def __init__(self, controller, slot, parent=None):
        super().__init__(parent)
        self.controller, self.slot = controller, slot
        self.closed, self.busy = False, False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.signals = PlanningSignals()
        self.signals.ready.connect(self.complete)
        self.setWindowTitle("Planning")
        self.resize(600, 580)
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        _, device = self.controller._device(slot)
        heading(titles,"Planning",device.get("name","Ampoule") + " · synchronisé avec LSC")
        header.addLayout(titles,1)
        self.add_button = QPushButton("+ Ajouter un horaire")
        self.add_button.setProperty("role","primary")
        self.add_button.clicked.connect(lambda: self.edit())
        header.addWidget(self.add_button)
        layout.addLayout(header)
        toolbar = QHBoxLayout()
        self.status = QLabel("Lecture du planning…")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        toolbar.addWidget(self.status,1)
        self.refresh_button = QPushButton("Actualiser")
        self.refresh_button.setProperty("role","ghost")
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName("scheduleContent")
        self.rows_layout = QVBoxLayout(self.content)
        self.rows_layout.setContentsMargins(0,0,4,0)
        self.rows_layout.setSpacing(12)
        scroll.setWidget(self.content)
        layout.addWidget(scroll)
        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("Fermer")
        close.setProperty("role","ghost")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.refresh()

    def refresh(self, mutation=None):
        if self.busy:
            return
        self.busy = True
        self.refresh_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.content.setEnabled(False)
        self.status.setText("Actualisation…")
        def work():
            config, item = self.controller._device(self.slot)
            if self.controller.demo or config["mode"] != "lsc":
                raise ControlError("Connecte ton compte LSC pour afficher le planning partagé.")
            account = LSCAccount(self.controller.store, config.get("lsc_region", "eu"))
            try:
                if mutation:
                    mutation(account, item)
                    # LSC caches closely repeated timer queries for two seconds.
                    # Read back after that interval so newly saved rows appear.
                    time.sleep(2.2)
                return timer_rows(account.timers(item))
            finally:
                account.close()
        future = self.executor.submit(work)
        def done(job):
            try:
                value, error = job.result(), None
            except Exception as exc:
                value, error = None, str(exc) if isinstance(exc, ControlError) else "Impossible de lire le planning LSC."
            if not self.closed:
                self.signals.ready.emit(value, error)
        future.add_done_callback(done)

    def complete(self, rows, error):
        self.busy = False
        self.refresh_button.setEnabled(True)
        self.add_button.setEnabled(True)
        self.content.setEnabled(True)
        if error:
            self.status.setText(error)
            return
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        config, device = self.controller._device(self.slot)
        switch = device["lsc_functions"].get("switch_led", {}).get("id")
        for timer in rows:
            box = QFrame()
            box.setObjectName("scheduleCard")
            sublayout = QVBoxLayout(box)
            sublayout.setContentsMargins(18,14,18,12)
            sublayout.setSpacing(8)
            dps = timer.get("dps", {})
            if isinstance(dps, str):
                try:
                    dps = json.loads(dps)
                except ValueError:
                    dps = {}
            power = dps.get(switch)
            action = "Allumer" if power is True else ("Éteindre" if power is False else "Réglages de l'ampoule")
            active = timer.get("status") == 1 and timer.get("category_status") == 1
            box.setProperty("active",active)
            title = QHBoxLayout()
            title.addWidget(PowerActionIcon(power))
            title.addSpacing(4)
            clock = QLabel(timer.get("time","--:--"))
            clock.setObjectName("scheduleTime")
            title.addWidget(clock)
            clock.setAccessibleName(timer.get("time","--:--") + " · " + action)
            title.addStretch()
            toggle = QPushButton("Activé" if active else "Désactivé")
            toggle.setProperty("role","toggle")
            toggle.setCheckable(True)
            toggle.setChecked(active)
            toggle.setAccessibleName(("Désactiver" if active else "Activer") + " l’horaire de " + timer.get("time",""))
            toggle.clicked.connect(lambda checked=False, row=timer, enabled=active, button=toggle:
                self.toggle_timer(row,enabled,button))
            title.addWidget(toggle)
            sublayout.addLayout(title)
            label = QLabel(repeat_label(timer.get("loops", "")))
            label.setObjectName("muted")
            sublayout.addWidget(label)
            if timer.get("aliasName"):
                alias = QLabel(timer["aliasName"])
                alias.setWordWrap(True)
                sublayout.addWidget(alias)
            buttons = QHBoxLayout()
            notification = QLabel("Notification mobile" if timer.get("isAppPush") else "Sans notification")
            notification.setObjectName("muted")
            buttons.addWidget(notification)
            buttons.addStretch()
            # Multi-action groups must not be rewritten as a single timer.
            edit = QPushButton("Modifier")
            edit.setProperty("role","ghost")
            edit.clicked.connect(lambda checked=False, row=timer: self.edit(row))
            buttons.addWidget(edit)
            delete = QPushButton("Supprimer")
            delete.setProperty("role","danger")
            delete.clicked.connect(lambda checked=False, row=timer: self.delete(row))
            buttons.addWidget(delete)
            sublayout.addLayout(buttons)
            self.rows_layout.addWidget(box)
        self.rows_layout.addStretch()
        if not rows:
            empty = QLabel("Aucun horaire pour cette ampoule.")
            empty.setObjectName("muted")
            self.rows_layout.insertWidget(0,empty)
        self.status.setText(f"{len(rows)} horaire" + ("s" if len(rows)!=1 else ""))

    def toggle_timer(self, timer, active, button):
        # Display the last confirmed state until the cloud readback succeeds.
        button.setChecked(active)
        self.refresh(lambda account,item: set_timer_status(account,item,timer['timerId'],0 if active else 1))

    def edit(self, timer=None):
        if self.busy:
            return
        config, device = self.controller._device(self.slot)
        if 'lsc_functions' not in device:
            self.status.setText("Connecte ton compte LSC avant d'ajouter un horaire.")
            return
        editor = TimerEditor(device,timer,self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            form = editor.values()
            self.refresh(lambda account,item: save_timer(account,item,form,timer))

    def delete(self, timer):
        if self.busy:
            return
        if QMessageBox.question(self,"Supprimer cet horaire LSC", "Supprimer l'horaire de " + timer.get('time','') + " du compte LSC et du téléphone ?") == QMessageBox.StandardButton.Yes:
            self.refresh(lambda account,item:set_timer_status(account,item,timer['timerId'],2))

    def done(self, result):
        self.closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().done(result)
