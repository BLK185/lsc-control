"""macOS lifecycle and a user-only, activation-only single-instance channel."""
import hashlib
import json
from pathlib import Path
import secrets
import platform
import time
from PySide6.QtCore import QIODevice, QObject, QProcess, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from core import HOME, ControlError


class MacIntegration(QObject):
    external_change = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        from control_center import ControlsService
        self.controls = ControlsService(window.controller, self.external_change.emit)
        self.external_change.connect(self.refresh_external)
        self.control_signature = None
        self.reload_process = QProcess(self)
        self.last_reload = 0
        self.controls_available = int(platform.mac_ver()[0].split('.')[0] or '0') >= 26
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.activate)
        self.name = "lsc-control-" + hashlib.sha256(str(HOME.resolve()).encode()).hexdigest()[:24]
        menu = window.menuBar().addMenu("LSC Control")
        show = menu.addAction("Afficher LSC Control")
        show.triggered.connect(window.open_window)
        menu.addAction("Connexion LSC…", window.lsc_login)
        menu.addAction("Centre de contrôle…", self.configure_controls)
        menu.addSeparator()
        quit_action = QAction("Quitter LSC Control", window)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(window.quit)
        menu.addAction(quit_action)

    def claim_instance(self):
        probe = QLocalSocket(self)
        probe.connectToServer(self.name, QIODevice.OpenModeFlag.WriteOnly)
        if probe.waitForConnected(500):
            probe.write(b"activate")
            probe.waitForBytesWritten(500)
            probe.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            raise RuntimeError("Impossible de démarrer LSC Control pour cet utilisateur.")
        if self.controls_available:
            try:
                self.controls.restore()
            except Exception:
                self.window.message.setText("Ouvre Centre de contrôle… pour rétablir l’accès aux commandes.")
        return True

    def refresh_external(self):
        if not self.window.busy:
            self.window.refresh(observe=True)

    def updated(self):
        signature = [(device['slot'], device['name'], self.window.device_states.get(device['slot'], {}).get('power'))
                     for device in self.window.controller.devices()]
        if signature != self.control_signature:
            self.control_signature = signature
            self.reload_controls()

    def reload_controls(self):
        if not self.controls_available:
            return
        helper = Path(__file__).resolve().parent / 'native/LSCControlSignals'
        if not helper.is_file():
            return
        if time.monotonic() - self.last_reload < 2:
            QTimer.singleShot(2100, self.reload_controls)
            return
        if self.reload_process.state() == QProcess.ProcessState.NotRunning:
            self.last_reload = time.monotonic()
            self.reload_process.start(str(helper), [])

    def configure_controls(self):
        from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Centre de contrôle")
        dialog.setMinimumWidth(490)
        layout = QVBoxLayout(dialog)
        from theme import heading
        heading(layout, "Centre de contrôle", "Marche/arrêt individuel ou tous les éclairages.")
        if not self.controls_available:
            layout.addWidget(QLabel("Ces commandes nécessitent macOS 26 ou ultérieur."))
        else:
            try:
                token = self.controls.enable()
            except ControlError as error:
                layout.addWidget(QLabel(str(error)))
            else:
                instructions = QLabel("1. Copie le code ci-dessous.\n"
                    "2. Centre de contrôle → Modifier les commandes → LSC Control → Éclairage LSC.\n"
                    "3. Modifie la commande, colle le code puis choisis l’éclairage.\n\n"
                    "Les commandes suivantes peuvent réutiliser cette connexion.\n"
                    "Laisse LSC Control actif dans la barre des menus.")
                instructions.setWordWrap(True)
                layout.addWidget(instructions)
                code = QLineEdit(token)
                code.setReadOnly(True)
                layout.addWidget(code)
                copy = QPushButton("Copier le code de connexion")
                def copy_code():
                    QApplication.clipboard().setText(code.text())
                    copy.setText("Code copié")
                copy.clicked.connect(copy_code)
                layout.addWidget(copy)
                reset = QPushButton("Réinitialiser l’accès aux commandes")
                def rotate():
                    try:
                        code.setText(self.controls.enable(rotate=True))
                        copy.setText("Copier le nouveau code")
                    except ControlError as error:
                        instructions.setText(str(error))
                reset.clicked.connect(rotate)
                layout.addWidget(reset)
                caption = QLabel("Accès local aux commandes uniquement. Ta session LSC reste dans le Trousseau de l’app.")
                caption.setWordWrap(True)
                caption.setObjectName("muted")
                layout.addWidget(caption)
        close = QPushButton("Fermer")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def activate(self):
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            # This socket can only bring the app to the foreground. It never
            # accepts commands, account data, file paths, or arbitrary URLs.
            self.window.open_window()
            connection.close()
            connection.deleteLater()

    def close(self):
        self.controls.close()
        if self.reload_process.state() != QProcess.ProcessState.NotRunning:
            self.reload_process.waitForFinished(1000)
        self.server.close()


def smoke_check(window, report_path):
    """CI-only checks with demo bulbs and a disposable synthetic Keychain item."""
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    import keyring
    report = {"demo": window.controller.demo, "platform": QApplication.platformName()}
    name = "macos-ci-" + secrets.token_hex(12)
    stored = False
    try:
        if not window.controller.demo or report["platform"] != "cocoa":
            raise RuntimeError()
        report["menu_bar_available"] = QSystemTrayIcon.isSystemTrayAvailable() and window.tray.isVisible()
        window.tray.contextMenu().rebuild()
        report["light_count"] = len(window.cards)
        window.close()
        report["close_keeps_menu"] = not window.isVisible() and window.tray.isVisible()
        window.open_window()
        report["reopen_works"] = window.isVisible()
        secret = secrets.token_urlsafe(32)
        keyring.set_password("LSC Control CI", name, secret)
        stored = True
        report["keychain_roundtrip"] = keyring.get_password("LSC Control CI", name) == secret
        report["ok"] = all(report.get(key) is True for key in (
            "menu_bar_available", "close_keeps_menu", "reopen_works", "keychain_roundtrip"))
    except Exception:
        report["ok"] = False
    finally:
        if stored:
            keyring.delete_password("LSC Control CI", name)
        Path(report_path).write_text(json.dumps(report), encoding="utf-8")
        window.quit()
