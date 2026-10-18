"""Windows desktop and notification-area client. Also usable on macOS."""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)
from core import Controller, ControlError, DEFAULTS, Store

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

class Settings(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Connexion avancée aux ampoules")
        self.resize(540, 580)
        config = store.load()
        layout = QVBoxLayout(self)
        info = QLabel("Mode local : IP, identifiant et clé locale.\nMode cloud : API développeur Tuya — ce n’est pas une connexion au compte LSC.\nLes champs secrets laissés vides conservent les valeurs enregistrées.")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["lsc", "local", "cloud"])
        self.mode.setCurrentText(config["mode"])
        form.addRow("Connexion", self.mode)
        self.region = QComboBox()
        self.region.addItems(["eu", "eu-w", "us", "us-e", "cn", "in", "sg"])
        self.region.setCurrentText(config.get("region", "eu"))
        form.addRow("Centre de données Tuya", self.region)
        self.access = QLineEdit()
        self.access.setPlaceholderText("Access ID du projet — vide pour conserver")
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setPlaceholderText("Access Secret — vide pour conserver")
        form.addRow("Access ID", self.access)
        form.addRow("Access Secret", self.secret)
        layout.addLayout(form)
        self.fields = {}
        for device in config["devices"]:
            box = QGroupBox(device["name"])
            subform = QFormLayout(box)
            fields = {}
            for key, label in (("device_id", "Identifiant"), ("ip", "Adresse IP"), ("version", "Protocole"), ("local_key", "Clé locale")):
                if key == "version":
                    field = QComboBox()
                    field.addItems(["3.1", "3.2", "3.3", "3.4", "3.5"])
                    field.setCurrentText(str(device.get(key, "3.3")))
                else:
                    field = QLineEdit(device.get(key, "") if key != "local_key" else "")
                    if key == "local_key":
                        field.setEchoMode(QLineEdit.EchoMode.Password)
                        field.setPlaceholderText("16 octets — vide pour conserver")
                subform.addRow(label, field)
                fields[key] = field
            self.fields[device["slot"]] = fields
            layout.addWidget(box)
        button = QPushButton("Importer un devices.json de TinyTuya…")
        button.clicked.connect(self.import_devices)
        layout.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def import_devices(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir devices.json", "", "JSON (*.json)")
        if not path:
            return
        try:
            devices = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(devices, list) or not devices:
                raise ValueError()
            labels = [str(d.get("name", "Appareil")) + " — " + str(d.get("id", "")) for d in devices]
            for target in DEFAULTS:
                label, ok = QInputDialog.getItem(self, "Associer les appareils", "Quel appareil correspond à " + target["name"] + " ?", labels, editable=False)
                if not ok:
                    return
                device = devices[labels.index(label)]
                fields = self.fields[target["slot"]]
                fields["device_id"].setText(str(device.get("id", "")))
                fields["local_key"].setText(str(device.get("key", "")))
                fields["ip"].setText(str(device.get("ip", "")))
                version = str(device.get("version", "3.3"))
                if version in ("3.1", "3.2", "3.3", "3.4", "3.5"):
                    fields["version"].setCurrentText(version)
        except Exception:
            QMessageBox.warning(self, "Import impossible", "Ce fichier n'est pas une liste devices.json reconnue.")

    def save(self):
        try:
            config = self.store.load()
            config["mode"], config["region"] = self.mode.currentText(), self.region.currentText()
            for device in config["devices"]:
                fields = self.fields[device["slot"]]
                key = fields["local_key"].text()
                if key and len(key.encode()) != 16:
                    raise ControlError("Une clé locale doit contenir 16 octets.")
                for name in ("device_id", "ip"):
                    device[name] = fields[name].text().strip()
                device["version"] = fields["version"].currentText()
                self.store.set_secret("local:" + device["slot"], key)
            self.store.set_secret("cloud_id", self.access.text().strip())
            self.store.set_secret("cloud_secret", self.secret.text().strip())
            self.store.save(config)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Enregistrement impossible",
                                str(exc) if isinstance(exc, ControlError) else "Impossible d'enregistrer la configuration ou d'accéder au coffre système.")

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
        self.resize(900, 710)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        heading = QLabel("Tes lumières, à portée de main")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        self.message = QLabel("Mode démonstration : aucune ampoule réelle n'est commandée." if controller.demo else "Connecte ton compte avec Connexion LSC… pour lire tes appareils.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.cards = {}
        for device in controller.store.load()["devices"]:
            card = LampCard(device, self)
            self.cards[device["slot"]] = card
            row.addWidget(card)
        layout.addLayout(row)
        actions = QHBoxLayout()
        for label, callback in (
            ("Tout allumer", lambda: self.group(True)),
            ("Tout éteindre", lambda: self.group(False)),
            ("Actualiser", self.refresh),
            ("Connexion LSC…", self.lsc_login),
            ("Réglages avancés…", self.settings),
            ("Détecter…", self.scan),
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
        if self.pending_commands:
            (slot, action), value = self.pending_commands.popitem(last=False)
            QTimer.singleShot(0, lambda: self.command(slot, action, value))
        for card in self.cards.values():
            for control in card.controls:
                control.setEnabled(True)
        if error:
            self.message.setText(error)
            if not self.isVisible():
                self.tray.showMessage("Commande LSC impossible", error, QSystemTrayIcon.MessageIcon.Warning)
            return
        if context == "scan":
            text = "\n".join(f"{d['ip']} · {d['device_id']} · protocole {d['version']}" for d in values)
            QMessageBox.information(self, "Appareils détectés", text or "Aucun appareil trouvé. Vérifie le réseau et le pare-feu.")
            self.message.setText("Les ampoules du compte LSC trouvées sur ce réseau utilisent désormais le contrôle local rapide." if self.controller.store.load()["mode"] == "lsc" else "La détection ne fournit pas la clé locale.")
            return
        errors = []
        for state in values:
            self.device_states[state["slot"]] = state
            if "error" in state:
                self.cards[state["slot"]].status.setText("Non joignable")
                errors.append(state["error"])
                continue
            slot = state["slot"]
            for device in self.controller.store.load()["devices"]:
                if device["slot"] == slot:
                    self.cards[slot].setTitle(device["name"])
            previous = self.last_states.get(slot)
            if context == "observe" and self.notifications.isChecked() and previous is not None and previous != state["power"]:
                self.tray.showMessage("LSC Control", self.cards[slot].title() + (" s'est allumée." if state["power"] else " s'est éteinte."))
            self.last_states[slot] = state["power"]
            self.cards[slot].show_state(state)
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
        if self.controller.demo or any(d.get("device_id") for d in config["devices"]):
            self.refresh(observe=True)

    def command(self, slot, action, value):
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

    def refresh(self, observe=False):
        def work():
            result = []
            for slot in self.cards:
                try:
                    result.append(self.controller.status(slot))
                except ControlError as exc:
                    result.append({"slot": slot, "error": str(exc)})
            return result
        self.submit(work, "observe" if observe else "refresh")

    def settings(self):
        if self.busy:
            return
        if Settings(self.controller.store, self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def lsc_login(self):
        if self.busy:
            return
        from lsc_login import LSCLogin
        dialog = LSCLogin(self.controller.store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.message.setText("Compte LSC connecté. Lecture des ampoules…")
            self.controller.demo = False
            self.refresh()

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
    args = parser.parse_args()
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
