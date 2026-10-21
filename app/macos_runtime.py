"""macOS lifecycle and a user-only, activation-only single-instance channel."""
import hashlib
import json
from pathlib import Path
import secrets
from PySide6.QtCore import QIODevice, QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from core import HOME


class MacIntegration(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.activate)
        self.name = "lsc-control-" + hashlib.sha256(str(HOME.resolve()).encode()).hexdigest()[:24]
        menu = window.menuBar().addMenu("LSC Control")
        show = menu.addAction("Afficher LSC Control")
        show.triggered.connect(window.open_window)
        menu.addAction("Connexion LSC…", window.lsc_login)
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
        return True

    def activate(self):
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            # This socket can only bring the app to the foreground. It never
            # accepts commands, account data, file paths, or arbitrary URLs.
            self.window.open_window()
            connection.close()
            connection.deleteLater()

    def close(self):
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
