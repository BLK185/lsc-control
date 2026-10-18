"""Real QR authorization dialog. The server token is kept only in memory."""
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, QFileDialog
from core import ControlError, HOME
from lsc_account import LSCAccount, portable_identity_path


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


class LSCLogin(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.account, self.token = store, None, None
        self.expires, self.busy, self.closed = 0, False, False
        self.restore_once = True
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
        self.import_button = QPushButton("Importer le module de connexion…")
        self.import_button.setToolTip("Le module reste sur cet ordinateur. Il ne doit contenir aucune donnée de compte.")
        self.import_button.clicked.connect(self.import_module)
        layout.addWidget(self.import_button)
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
        self.import_button.setEnabled(False)
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
        if portable_identity_path() is None:
            self.image.setText("Module de connexion requis")
            self.status.setText("Importe ton module local pour activer la connexion par QR code.")
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
            self.status.setText("Lecture et association des deux ampoules…")
            self.submit("devices", self.account.prepare_bulbs)
        else:
            self.submit("create", self.account.create_qr)

    def import_module(self):
        if self.busy:
            return
        path,_ = QFileDialog.getOpenFileName(self,"Module de connexion LSC","","Module JSON (*.json)")
        if not path:
            return
        from lsc_identity import import_identity
        try:
            import_identity(path,HOME)
        except ControlError as exc:
            self.status.setText(str(exc))
            return
        self.restore_once = True
        self.start()

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
        self.import_button.setEnabled(True)
        if error:
            self.token = None
            self.image.clear()
            self.image.setText("Connexion interrompue")
            self.status.setText(error)
            self.region.setEnabled(True)
            return
        if kind == "create":
            self.token, self.expires = value, time.monotonic() + 180
            self.image.setPixmap(qr_pixmap(value))
            self.status.setText("Scanne ce QR code depuis LSC Smart Connect.")
        elif kind == "poll" and value:
            self.token = None
            self.image.clear()
            self.image.setText("Compte LSC connecté ✓")
            self.status.setText("Session enregistrée dans le coffre Windows. Lecture des appareils…")
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
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        if self.account:
            self.account.close()
        super().done(code)
