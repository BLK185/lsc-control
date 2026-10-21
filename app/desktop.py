"""Windows desktop and notification-area client. Also usable on macOS."""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer, Qt, QEvent
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
    QScrollArea, QGridLayout,
)
from core import Controller, ControlError, Store

def bulb_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#f6d365"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(14, 5, 36, 39)
    painter.drawRoundedRect(23, 38, 18, 14, 4, 4)
    painter.setBrush(QColor("#c4cad6"))
    painter.drawRoundedRect(24, 53, 16, 6, 3, 3)
    painter.end()
    return QIcon(pixmap)

class Results(QObject):
    ready = Signal(object, object)

from panels import LampCard

class Window(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.busy = False
        self.exiting = False
        self.last_states = {}
        self.device_states = {}
        self.pending_commands = OrderedDict()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.results = Results()
        self.results.ready.connect(self.complete)
        self.setWindowTitle("LSC Control" + (" — démonstration" if controller.demo else ""))
        self.setWindowIcon(bulb_icon())
        self.resize(900, 790)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        heading = QLabel("Tes lumières, à portée de main")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        self.message = QLabel("Mode démonstration : aucune ampoule réelle n'est commandée." if controller.demo else "Connecte ton compte avec Connexion LSC… pour lire tes appareils.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.cards = {}
        self.card_signatures = {}
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.card_container = QWidget()
        self.card_grid = QGridLayout(self.card_container)
        self.card_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty = QLabel("Aucun éclairage. Ajoute-le dans LSC Smart Connect sur ton téléphone ; il apparaîtra ici automatiquement.")
        self.empty.setWordWrap(True)
        self.scroll.setWidget(self.card_container)
        layout.addWidget(self.scroll, 1)
        self.reconcile_cards(controller.devices())
        actions = QHBoxLayout()
        for label, callback in (
            ("Tout allumer", lambda: self.group(True)),
            ("Tout éteindre", lambda: self.group(False)),
            ("Synchroniser", lambda: self.refresh(force=True)),
            ("Connexion LSC…", self.lsc_login),
            ("Connexion locale rapide", self.scan),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.notifications = QCheckBox("Notifier les changements marche/arrêt observés")
        self.notifications.setToolTip("Ne distingue pas une programmation d'une commande manuelle. Les notifications du téléphone restent gérées par LSC.")
        layout.addWidget(self.notifications)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("LSC Control")
        from tray_menu import TrayMenu
        menu = TrayMenu(self)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.open_window() if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_state)
        self.timer.start(3000)
        if controller.demo or controller.store.load()["mode"] == "lsc":
            QTimer.singleShot(50, self.refresh)

    def submit(self, work, context="command"):
        if self.busy:
            self.message.setText("Une opération est en cours.")
            return
        self.busy = True
        self.message.setText("Connexion…" if context != "scan" else "Recherche sur le réseau local…")
        future = self.executor.submit(work)
        def finished(result):
            try:
                self.results.ready.emit(context, (result.result(), None))
            except Exception as exc:
                self.results.ready.emit(context, (None, str(exc) if isinstance(exc, ControlError) else "Opération impossible. Vérifie la configuration."))
        future.add_done_callback(finished)

    def complete(self, context, payload):
        values, error = payload
        self.busy = False
        # Snapshot before dequeuing: this result predates those user adjustments.
        waiting_adjustments = {slot for slot, action in self.pending_commands
                               if action in ("white", "brightness", "temperature", "hsv", "colour")}
        if self.pending_commands:
            (slot, action), value = self.pending_commands.popitem(last=False)
            QTimer.singleShot(0, lambda s=slot, a=action, v=value: self.command(s, a, v))
        for card in self.cards.values():
            for control in card.controls:
                control.setEnabled(True)
        if error:
            self.message.setText(error)
            if not self.isVisible():
                self.tray.showMessage("Commande LSC impossible", error, QSystemTrayIcon.MessageIcon.Warning)
            return
        if context == "scan":
            known = {d.get("device_id") for d in self.controller.devices()}
            count = sum(d.get("device_id") in known for d in values)
            self.message.setText(f"Connexion locale disponible pour {count} éclairage(s)." if count else
                                 "Aucun éclairage retrouvé sur ce réseau. Le contrôle LSC reste disponible.")
            return
        sync_error = None
        if isinstance(values, dict):
            self.reconcile_cards(values["devices"])
            sync_error = values.get("sync_error")
            values = values["states"]
        errors = [sync_error] if sync_error else []
        for state in values:
            if state["slot"] not in self.cards:
                continue
            self.device_states[state["slot"]] = state
            if "error" in state:
                self.cards[state["slot"]].status.setText("Non joignable")
                errors.append(state["error"])
                continue
            slot = state["slot"]
            for device in self.controller.devices():
                if device["slot"] == slot:
                    self.cards[slot].setTitle(device["name"])
            previous = self.last_states.get(slot)
            if context == "observe" and self.notifications.isChecked() and previous is not None and previous != state["power"]:
                self.tray.showMessage("LSC Control", self.cards[slot].title() + (" s'est allumée." if state["power"] else " s'est éteinte."))
            self.last_states[slot] = state["power"]
            self.cards[slot].show_state(state, preserve_controls=slot in waiting_adjustments)
        from tray_menu import state_label
        self.tray.setToolTip("LSC Control\n" + "\n".join(
            card.title() + " : " + state_label(self.device_states.get(slot))
            for slot, card in self.cards.items()))
        from datetime import datetime
        text = "Simulation · aucune ampoule réelle commandée." if self.controller.demo else "État lu à " + datetime.now().strftime("%H:%M:%S")
        self.message.setText(" · ".join(errors) if errors else text)

    def poll_state(self):
        if self.busy or QApplication.activeModalWidget() is not None:
            return
        config = self.controller.store.load()
        interval = 20000 if config["mode"] == "cloud" else (5000 if config["mode"] == "lsc" else 3000)
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        if self.controller.demo or config["mode"] == "lsc" or any(d.get("device_id") for d in config["devices"]):
            self.refresh(observe=True)

    def command(self, slot, action, value):
        if slot not in self.cards:
            return
        if self.busy:
            key = (slot, action)
            self.pending_commands[key] = value
            self.pending_commands.move_to_end(key)
            self.message.setText("Commande en attente…")
            return
        self.submit(lambda: [self.controller.command(slot, action, value)],("command",slot,action))

    def group(self, power):
        for slot in self.cards:
            self.command(slot, "power", power)

    def reconcile_cards(self, devices):
        import json
        wanted = {d["slot"] for d in devices}
        for slot in list(self.cards):
            if slot not in wanted:
                self.card_grid.removeWidget(self.cards[slot])
                self.cards.pop(slot).deleteLater()
                self.card_signatures.pop(slot, None)
                self.device_states.pop(slot, None)
                self.last_states.pop(slot, None)
        self.pending_commands = OrderedDict((key, value) for key, value in self.pending_commands.items() if key[0] in wanted)
        for device in devices:
            slot = device["slot"]
            signature = json.dumps([device.get("rgb"), device.get("lsc_functions")], sort_keys=True)
            if slot not in self.cards or self.card_signatures.get(slot) != signature:
                if slot in self.cards:
                    self.card_grid.removeWidget(self.cards[slot])
                    self.cards.pop(slot).deleteLater()
                self.cards[slot] = LampCard(device, self)
                self.cards[slot].setMinimumWidth(340)
                self.card_signatures[slot] = signature
            self.cards[slot].setTitle(device["name"])
        self.card_order = [d["slot"] for d in devices]
        self.layout_cards()

    def layout_cards(self):
        if not hasattr(self, "card_grid"):
            return
        for card in self.cards.values():
            self.card_grid.removeWidget(card)
        self.card_grid.removeWidget(self.empty)
        columns = max(1, min(3, self.scroll.viewport().width() // 370))
        for index, slot in enumerate(self.card_order):
            self.card_grid.addWidget(self.cards[slot], index // columns, index % columns)
        self.empty.setVisible(not self.cards)
        if not self.cards:
            self.card_grid.addWidget(self.empty, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_cards()

    def eventFilter(self, watched, event):
        if hasattr(self, "scroll") and watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self.layout_cards()
        return super().eventFilter(watched, event)

    def refresh(self, observe=False, force=False):
        def work():
            sync_error = None
            try:
                self.controller.synchronize_lights(force=force)
            except ControlError as exc:
                sync_error = "Synchronisation : " + str(exc)
            devices = self.controller.devices()
            result = []
            for device in devices:
                slot = device["slot"]
                try:
                    result.append(self.controller.status(slot))
                except ControlError as exc:
                    result.append({"slot": slot, "error": str(exc)})
            return {"devices": devices, "states": result, "sync_error": sync_error}
        self.submit(work, "observe" if observe else "refresh")

    def lsc_login(self):
        if self.busy:
            return
        from lsc_login import LSCLogin
        dialog = LSCLogin(self.controller.store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.message.setText("Compte LSC connecté. Lecture des ampoules…")
            self.controller.demo = False
            self.refresh(force=True)

    def scan(self):
        self.submit(self.controller.scan, "scan")

    def open_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not self.exiting and self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()

    def quit(self):
        self.exiting = True
        self.timer.stop()
        self.tray.hide()
        self.executor.shutdown(wait=False, cancel_futures=True)
        QApplication.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--screenshot")
    parser.add_argument("--lsc-login", action="store_true")
    parser.add_argument("--diagnostic", help="Écrire un diagnostic de connexion sans données secrètes")
    parser.add_argument("--check-login", help="Vérifier la création d’un QR sans utiliser de session enregistrée")
    args = parser.parse_args()
    if args.check_login:
        from lsc_account import LSCAccount
        store = Store()
        account = LSCAccount(store, store.load().get("lsc_region", "eu"), restore=False)
        report = {"saved_session_used": False}
        try:
            token = account.create_qr()
            report.update(ok=bool(token), native_runtime_used=account.portable is None)
        except ControlError as exc:
            report.update(ok=False, error=str(exc))
        finally:
            account.close()
        Path(args.check_login).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["ok"] else 1
    if args.diagnostic:
        from lsc_account import LSCAccount, portable_identity_path
        store = Store()
        report = {"portable_identity_present":portable_identity_path() is not None,"devices":[]}
        try:
            config=store.load()
            account=LSCAccount(store,config.get("lsc_region","eu"))
            try:
                report["account_names"]=[str(d.get("name","")).strip() for d in account.devices()]
                report["portable_account_read"]=account.portable is not None
            finally:
                account.close()
            controller=Controller(store)
            for device in config["devices"]:
                state=controller.status(device["slot"])
                report["devices"].append({"name":device["name"],"transport":state.get("transport"),
                    "online":state.get("online"),"scene_count":len(state.get("scenes",[])),
                    "countdown_readable":type(state.get("countdown")) is int})
            report["ok"]=True
        except Exception as exc:
            report["ok"]=False
            report["error"]=str(exc) if isinstance(exc,ControlError) else "Diagnostic indisponible."
        Path(args.diagnostic).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return 0 if report["ok"] else 1
    app = QApplication(sys.argv[:1])
    app.setApplicationName("LSC Control")
    from theme import apply_theme
    apply_theme(app)
    window = Window(Controller(demo=args.demo))
    window.show()
    if args.lsc_login:
        QTimer.singleShot(100, window.lsc_login)
    if args.screenshot:
        def capture():
            window.grab().save(args.screenshot)
            window.quit()
        QTimer.singleShot(600, capture)
    app.aboutToQuit.connect(lambda: window.executor.shutdown(wait=False, cancel_futures=True))
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
