"""Loopback-only authenticated bridge for the native macOS client."""
import argparse
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import Controller, ControlError, HOME

def create_server(controller, token, port=47831):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            # No browser origins; the native clients carry the bearer token.
            if self.headers.get("Origin") or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.reply(401, {"error": "Accès refusé."})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            try:
                parts = self.path.strip("/").split("/")
                if len(parts) != 2 or parts[0] != "status":
                    self.reply(404, {"error": "Route inconnue."})
                    return
                self.reply(200, controller.status(parts[1]))
            except ControlError as exc:
                self.reply(409, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "Erreur interne du moteur."})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/command":
                self.reply(404, {"error": "Route inconnue."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError()
                payload = json.loads(self.rfile.read(length))
                self.reply(200, controller.command(payload["slot"], payload["action"], payload["value"]))
            except (ValueError, KeyError, TypeError):
                self.reply(400, {"error": "Requête invalide."})
            except ControlError as exc:
                self.reply(409, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "Erreur interne du moteur."})
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    controller = Controller(demo=args.demo)
    token = secrets.token_urlsafe(32)
    server = create_server(controller, token)
    descriptor = HOME / "bridge.json"
    descriptor.write_text(json.dumps({"url": "http://127.0.0.1:47831", "token": token}), encoding="utf-8")
    descriptor.chmod(0o600)
    print("Moteur local démarré. Dans l'app Mac, importer ~/.lsc-control/bridge.json.", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        descriptor.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
