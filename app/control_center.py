"""Narrow authenticated loopback API for macOS Control Center.

The extension receives its own capability. This interface never returns LSC
sessions, device keys, raw device records, or access to scheduling APIs.
"""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import secrets
import threading

from core import ControlError

PORT = 47832
TOKEN_NAME = "macos_control_center"


def valid_token(token):
    return isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token) is not None


def create_server(controller, token, port=PORT, changed=lambda: None):
    if not valid_token(token):
        raise ValueError("Invalid Control Center capability")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value):
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self):
            supplied = self.headers.get("Authorization", "").encode("utf-8")
            if (self.headers.get("Origin") or self.headers.get("Referer")
                    or self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"
                    or not hmac.compare_digest(supplied, ("Bearer " + token).encode("ascii"))):
                self.server.metrics['refused'] += 1
                self.reply(401, {"error": "Accès aux commandes refusé."})
                return False
            self.server.metrics['accepted'] += 1
            return True

        def targets(self, identifier):
            devices = controller.devices()
            slots = [device["slot"] for device in devices]
            if identifier == "all":
                if not slots:
                    raise ControlError("Aucun éclairage connecté.")
                return slots
            if identifier not in slots:
                raise ControlError("Cet éclairage n’est plus dans le compte.")
            return [identifier]

        def do_GET(self):
            if not self.authorized():
                return
            try:
                if self.path == "/lights":
                    self.reply(200, {"lights": [{"id": device["slot"], "name": device["name"]}
                                                for device in controller.devices()]})
                elif self.path.startswith("/power/"):
                    slots = self.targets(self.path[len("/power/"):])
                    # Read every target, including when the first one is off.
                    states = [controller.recent_status(slot) or controller.status(slot) for slot in slots]
                    self.reply(200, {"power": all(state["power"] for state in states)})
                else:
                    self.reply(404, {"error": "Commande inconnue."})
            except ControlError as error:
                self.reply(409, {"error": str(error)})
            except Exception:
                self.reply(500, {"error": "État indisponible."})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/power":
                self.reply(404, {"error": "Commande inconnue."})
                return
            try:
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                    raise ValueError()
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    raise ValueError()
                data = json.loads(self.rfile.read(size))
                if (not isinstance(data, dict) or set(data) != {"id", "value"}
                        or not isinstance(data["id"], str) or type(data["value"]) is not bool):
                    raise ValueError()
                slots = self.targets(data["id"])
                failures = []
                states = []
                for slot in slots:
                    try:
                        states.append(controller.command(slot, "power", data["value"]))
                    except ControlError:
                        failures.append(slot)
                changed()
                if failures:
                    raise ControlError("Certains éclairages n’ont pas répondu. Actualise leur état dans LSC Control.")
                self.reply(200, {"power": all(state["power"] for state in states)})
            except (ValueError, KeyError, TypeError):
                self.reply(400, {"error": "Commande invalide."})
            except ControlError as error:
                self.reply(409, {"error": str(error)})
            except Exception:
                self.reply(500, {"error": "Commande indisponible."})

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(8)
            return connection, address

    server = Server(("127.0.0.1", port), Handler)
    server.metrics = {'accepted': 0, 'refused': 0}
    return server


class ControlsService:
    def __init__(self, controller, changed=lambda: None):
        self.controller, self.changed = controller, changed
        self.server = self.thread = None
        self.token = ""

    def restore(self):
        token = self.controller.store.secret(TOKEN_NAME)
        if valid_token(token):
            self.start(token)

    def enable(self, rotate=False):
        if self.server and not rotate:
            return self.token
        if rotate:
            self.close()
        token = secrets.token_urlsafe(32)
        self.start(token)
        try:
            self.controller.store.set_secret(TOKEN_NAME, token)
        except Exception:
            self.close()
            raise ControlError("Impossible d’enregistrer l’accès dans le Trousseau.") from None
        return token

    def start(self, token):
        try:
            self.server = create_server(self.controller, token, changed=self.changed)
        except OSError:
            raise ControlError("Le port des commandes LSC est occupé. Ferme les autres copies de LSC Control.") from None
        self.token = token
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
        self.server = self.thread = None
        self.token = ""
