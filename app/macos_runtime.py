"""macOS lifecycle and a user-only, activation-only single-instance channel."""
import hashlib
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
