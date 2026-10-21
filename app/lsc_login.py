"""Real QR authorization dialog. The server token is kept only in memory."""
import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, QFileDialog
from core import ControlError, HOME
from lsc_account import LSCAccount, connection_ready


def qr_pixmap(token):
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data("tuyaSmart--qrLogin?token=" + token)
    qr.make(fit=True)
    cells = qr.get_matrix()
    scale, size = 6, len(cells)
    image = QImage(size * scale, size * scale, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    for y, row in enumerate(cells):
        for x, active in enumerate(row):
            if active:
                painter.fillRect(x*scale, y*scale, scale, scale, QColor("black"))
    painter.end()
    return QPixmap.fromImage(image)


class LoginSignals(QObject):
    ready = Signal(str, object, object)
    progress = Signal(str)


class LSCLogin(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.account, self.token = store, None, None
        self.expires, self.busy, self.closed = 0, False, False
        self.restore_once = True
        self.cancel = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.signals = LoginSignals()
        self.signals.ready.connect(self.complete)
        self.setWindowTitle("Connexion à ton compte LSC")
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        instruction = QLabel("Sur ton téléphone : ouvre LSC Smart Connect → Moi → scanner en haut à droite.\nScanne ce QR code, puis confirme la connexion.\nLe téléphone peut afficher LSC Battletron comme client à autoriser.")
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        self.region = QComboBox()
        for name, value in (("Europe", "eu"), ("Amérique", "us"), ("Chine", "cn")):
            self.region.addItem(name, value)
        layout.addWidget(self.region)
        self.image = QLabel("Préparation de la connexion…")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumHeight(285)
        layout.addWidget(self.image)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_button = QPushButton("Nouveau QR code")
        self.refresh_button.clicked.connect(self.start)
        layout.addWidget(self.refresh_button)
        self.prepare_button = QPushButton("Préparer la connexion LSC")
        self.prepare_button.clicked.connect(self.prepare_connection)
        layout.addWidget(self.prepare_button)
        self.installer_button = QPushButton("Choisir le programme officiel déjà téléchargé…")
        self.installer_button.clicked.connect(self.choose_installer)
        layout.addWidget(self.installer_button)
        self.signals.progress.connect(self.status.setText)
        self.done_button = QPushButton("Fermer")
        self.done_button.clicked.connect(self.reject)
        layout.addWidget(self.done_button)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        QTimer.singleShot(0, self.start)

    def submit(self, kind, function):
        self.busy = True
        self.refresh_button.setEnabled(False)
        self.prepare_button.setEnabled(False)
        self.installer_button.setEnabled(False)
        self.region.setEnabled(False)
        future = self.executor.submit(function)
        def done(job):
            try:
                value, error = job.result(), None
            except Exception as exc:
                value, error = None, str(exc) if isinstance(exc, ControlError) else "Connexion impossible. Réessaie."
            if not self.closed:
                self.signals.ready.emit(kind, value, error)
        future.add_done_callback(done)

    def start(self):
        if self.busy:
            return
        ready = connection_ready()
        self.prepare_button.setVisible(not ready)
        self.installer_button.setVisible(not ready)
        self.refresh_button.setVisible(ready)
        self.image.setMinimumHeight(285 if ready else 80)
        if not ready:
            self.image.setText("Connecte ton compte LSC")
            self.status.setText("Prépare la connexion, puis scanne le QR code avec LSC Smart Connect.\n"
                                "Environ 64 Mo sont téléchargés depuis Action et 7-Zip, vérifiés et préparés sur cet ordinateur. Aucun installateur n’est lancé.")
            self.region.setEnabled(True)
            return
        self.token = None
        self.image.clear()
        self.image.setText("Demande d'un QR code au serveur LSC…")
        self.status.setText("Connexion non officielle · aucun mot de passe demandé.")
        if self.account:
            self.account.close()
        self.account = LSCAccount(self.store, self.region.currentData(), restore=self.restore_once)
        self.restore_once = False
        if self.account.connected:
            self.image.setText("Session LSC déjà connectée")
            self.status.setText("Synchronisation des éclairages du compte…")
            self.submit("devices", self.account.prepare_bulbs)
        else:
            self.submit("create", self.account.create_qr)

    def prepare_connection(self, installer=None):
        if self.busy:
            return
        from connection_setup import prepare
        self.image.setText("Préparation de la connexion…")
        self.status.setText("Téléchargement des composants officiels…")
        def progress(message):
            if not self.closed:
                self.signals.progress.emit(message)
        self.submit("prepare", lambda: prepare(HOME, progress, self.cancel, installer))

    def choose_installer(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Programme officiel LSC Battletron 2.0.17", "", "Programme officiel (*.exe)")
        if path:
            self.prepare_connection(path)

    def poll(self):
        if self.closed or self.busy or not self.token:
            return
        left = int(self.expires - time.monotonic())
        if left <= 0:
            self.token = None
            self.image.clear()
            self.image.setText("QR code expiré")
            self.status.setText("Clique sur Nouveau QR code pour réessayer.")
            self.region.setEnabled(True)
            return
        self.status.setText(f"En attente de validation sur ton téléphone · {left} s")
        self.submit("poll", lambda: self.account.poll_qr(self.token))

    def complete(self, kind, value, error):
        self.busy = False
        self.refresh_button.setEnabled(True)
        self.prepare_button.setEnabled(True)
        self.installer_button.setEnabled(True)
        if error:
            self.token = None
            self.image.clear()
            self.image.setText("Connexion interrompue")
            self.status.setText(error)
            self.region.setEnabled(True)
            return
        if kind == "prepare":
            self.start()
        elif kind == "create":
            self.token, self.expires = value, time.monotonic() + 180
            self.image.setPixmap(qr_pixmap(value))
            self.status.setText("Scanne ce QR code depuis LSC Smart Connect.")
        elif kind == "poll" and value:
            self.token = None
            self.image.clear()
            self.image.setText("Compte LSC connecté ✓")
            vault = "le Trousseau macOS" if sys.platform == "darwin" else "le coffre du système"
            self.status.setText(f"Session enregistrée dans {vault}. Lecture des appareils…")
            self.submit("devices", self.account.prepare_bulbs)
        elif kind == "devices":
            self.account.remember_devices(value)
            self.status.setText("Appareils reçus :\n" + "\n".join(str(d.get("name", "Appareil")) for d in value))
            self.refresh_button.setEnabled(False)
            self.done_button.setText("Continuer")
            self.done_button.clicked.disconnect()
            self.done_button.clicked.connect(self.accept)

    def done(self, code):
        self.closed = True
        self.cancel.set()
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        if self.account:
            self.account.close()
        super().done(code)
