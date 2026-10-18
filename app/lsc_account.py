"""Personal LSC QR session, using the separately supplied Windows client.

Passwords are never requested. Session data stays in the operating-system
credential vault; helper stdout is protocol-only and is never logged.
"""
import json
import hashlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from core import ControlError, HOME


def schema_functions(raw):
    try:
        schema = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(schema, list):
            raise ValueError()
        return {entry["code"]:{"id":str(entry["id"]), "mode":entry.get("mode", ""),
                "values":entry.get("property", {})} for entry in schema
                if isinstance(entry, dict) and entry.get("code") and str(entry.get("id", "")).isdigit()}
    except (ValueError, TypeError, KeyError):
        raise ControlError("Schéma des fonctions LSC non reconnu.") from None


def runtime_root():
    configured = os.environ.get("LSC_BATTLETRON_HOME")
    candidates = [Path(configured)] if configured else []
    for origin in (Path(__file__).resolve(), Path(sys.executable).resolve()):
        candidates.extend(parent / "tools/battletron" for parent in origin.parents)
    for root in candidates:
        if ((root / "app/LSC_Battletron.exe").is_file()
                and (root / "interop/client-identity.json").is_file()):
            return root.resolve()
    raise ControlError("Le module LSC Windows n'est pas présent. La connexion sur Mac reste à préparer.")


def portable_identity_path():
    configured = os.environ.get("LSC_IDENTITY_FILE")
    candidates = [Path(configured)] if configured else []
    candidates.append(HOME / "private/portable-identity.json")
    candidates.append(Path(__file__).resolve().parent / "private/portable-identity.json")
    for origin in (Path(__file__).resolve(), Path(sys.executable).resolve()):
        candidates.extend(parent / "tools/battletron/interop/portable-identity.json" for parent in origin.parents)
    return next((path for path in candidates if path.is_file()), None)


def friendly_error(code):
    if code in ("NETWORK", "TIMEOUT"):
        return "Connexion au serveur LSC impossible. Vérifie Internet et réessaie."
    if code in ("SERVER_USER_SESSION_INVALID", "SERVER_USER_SESSION_LOSS"):
        return "La session LSC a expiré. Reconnecte-toi avec le QR code."
    if "TOKEN" in code and any(word in code for word in ("EXPIRE", "INVALID", "NOT_EXIST")):
        return "Ce QR code a expiré. Clique sur Nouveau QR code."
    if code.startswith("SERVER_"):
        return "Le serveur LSC a refusé la demande (" + code[7:80] + ")."
    return "Le module de connexion LSC a échoué (" + code[:80] + ")."


class LSCAccount:
    def __init__(self, store, region="eu", restore=True, use_portable=True):
        if region not in ("eu", "us", "cn"):
            raise ControlError("Région LSC invalide.")
        self.store, self.region = store, region
        self.session = {}
        self.process = None
        self.lock = threading.Lock()
        self.sequence = 0
        self.use_portable = use_portable
        self.portable = None
        if restore:
            saved = store.secret("lsc_session:" + region)
            if saved:
                self.session = json.loads(saved)

    @property
    def connected(self):
        return bool(self.session.get("sid") and self.session.get("ecode"))

    def _start(self):
        root = runtime_root()
        executable = root / "app/LSC_Battletron.exe"
        script = Path(__file__).with_name("lsc_native.cjs")
        self.process = subprocess.Popen([str(executable), str(script), str(root)],
            env={**os.environ, "ELECTRON_RUN_AS_NODE": "1"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def request(self, api, data=None, version="1.0", gid=None, timezone_id=None):
        with self.lock:
            if self.use_portable:
                from lsc_portable import LSCPortableTransport, PortableError
                try:
                    if self.portable is None:
                        identity = portable_identity_path()
                        if identity:
                            self.portable = LSCPortableTransport(identity)
                    if self.portable is not None:
                        return self.portable.request(api,data,version,gid,region=self.region,session=self.session,timezone_id=timezone_id)
                except PortableError as exc:
                    raise ControlError(friendly_error(exc.code)) from None
            self._start()
            self.sequence += 1
            message = {"id":self.sequence,"api":api,"data":data or {},
                       "version":version,"region":self.region,"session":self.session}
            if gid is not None:
                message["gid"] = gid
            if timezone_id is not None:
                message["timezoneId"] = timezone_id
            try:
                # The legacy native library crashes when reused across requests.
                # Isolate each call in a fresh child; no secrets survive its exit.
                output, _ = self.process.communicate(
                    json.dumps(message, separators=(",", ":")) + "\n", timeout=25)
                if self.process.returncode != 0:
                    raise OSError()
                lines = output.splitlines()
                if len(lines) != 1:
                    raise ValueError()
                result = json.loads(lines[0])
                if not isinstance(result, dict) or "ok" not in result:
                    raise ValueError()
            except (OSError, ValueError, subprocess.TimeoutExpired):
                self.close()
                raise ControlError("Le module LSC ne répond plus. Réessaie la connexion.") from None
            self.process = None
            if not result.get("ok"):
                code = str(result.get("error", "HELPER_ERROR"))
                if not code.startswith("SERVER_"):
                    self.close()
                raise ControlError(friendly_error(code))
            if result.get("id") != self.sequence:
                self.close()
                raise ControlError("Réponse de connexion LSC inattendue.")
            return result.get("result")

    def create_qr(self):
        if self.connected:
            raise ControlError("Cette session est déjà connectée.")
        token = self.request("tuya.m.user.qr.token.create")
        if not isinstance(token, str) or not 16 <= len(token) <= 256 or any(c.isspace() for c in token):
            raise ControlError("Le serveur n'a pas renvoyé de jeton QR valide.")
        return token

    def poll_qr(self, token):
        user = self.request("tuya.m.user.qr.token.user.get", {"token":token})
        if isinstance(user, dict) and user.get("sid") and user.get("ecode"):
            self.session = {"sid":user["sid"],"ecode":user["ecode"]}
            self.store.set_secret("lsc_session:" + self.region, json.dumps(self.session))
            return True
        return False

    def devices(self):
        if not self.connected:
            raise ControlError("Connecte-toi à LSC avec le QR code.")
        homes = self.request("tuya.m.location.list", version="4.0")
        if not isinstance(homes, list):
            raise ControlError("Liste des maisons LSC non reconnue.")
        found = []
        for home in homes:
            gid = home.get("groupId", home.get("gid", home.get("homeId")))
            if gid is None:
                continue
            devices = self.request("tuya.m.my.group.device.list", version="2.0", gid=gid)
            if not isinstance(devices, list):
                raise ControlError("Liste des appareils LSC non reconnue.")
            for device in devices:
                if isinstance(device, dict):
                    found.append(dict(device, _home_id=gid, _home_name=home.get("name", "Maison")))
        return found

    def remember_devices(self, devices):
        """Keep only public device metadata in JSON; keys go to separate vault entries."""
        public = []
        for device in devices:
            device_id = device.get("devId", device.get("id", ""))
            local_key = device.get("localKey")
            if device_id and isinstance(local_key, str) and local_key:
                self.store.set_secret("lsc_local:" + str(device_id), local_key)
            public.append({k:device[k] for k in (
                "devId", "id", "name", "productId", "category", "isOnline", "dps",
                "_home_id", "_home_name") if k in device})
        config = self.store.load()
        config["lsc_region"], config["lsc_devices"] = self.region, public
        self.store.save(config)
        return public

    def prepare_bulbs(self, refresh_schema=True):
        """Reconcile a complete account inventory, preserving profiles by device ID.

        Build the new list before saving: a failed inventory never clears it.
        Detail failures preserve known lights; new unknown devices are retried.
        """
        from lighting import capabilities, is_lighting
        devices = self.devices()
        config = self.store.load()
        previous = {d.get("device_id"): d for d in config.get("devices", []) if d.get("device_id")}
        accepted, lights, seen = [], [], set()
        for device in devices:
            device_id = device.get("devId", device.get("id"))
            if not device_id or device_id in seen:
                continue
            seen.add(device_id)
            old = previous.get(device_id, {})
            detail = {}
            functions = old.get("lsc_functions")
            if refresh_schema or not functions:
                try:
                    detail = self.request("tuya.m.device.get", {"devId":device_id}, gid=device["_home_id"])
                    if not isinstance(detail, dict):
                        raise ControlError("Description de l'éclairage LSC non reconnue.")
                    functions = schema_functions(detail.get("schema"))
                except ControlError:
                    if not functions:
                        continue
                    detail = {}
            if not is_lighting(device, detail, functions):
                continue
            item = dict(old)
            slot = old.get("slot") or "light_" + hashlib.sha256(str(device_id).encode()).hexdigest()[:16]
            discovered_ip = old.get("ip", "") if old.get("lsc_local_available") else ""
            item.update(slot=slot, name=str(device.get("name") or "Éclairage").strip(), device_id=device_id,
                        category=device.get("category", detail.get("category", old.get("category", ""))),
                        ip=discovered_ip or detail.get("ip", old.get("ip", "")),
                        version=str(detail.get("pv", old.get("version", "3.3"))),
                        lsc_timezone=device.get("timezoneId", old.get("lsc_timezone", "Europe/Paris")),
                        lsc_home_id=device["_home_id"], lsc_functions=functions)
            item["rgb"] = capabilities(item)["rgb"]
            key = detail.get("localKey") or device.get("localKey") or self.store.secret("lsc_local:" + str(device_id))
            if key:
                self.store.set_secret("local:" + slot, key)
            lights.append(item)
            accepted.append(device)
        config["devices"] = lights
        config["mode"], config["lsc_region"] = "lsc", self.region
        self.store.save(config)
        self.remember_devices(accepted)
        return accepted

    def detail(self, item):
        if not self.connected:
            raise ControlError("Connecte-toi à LSC avec le QR code.")
        result = self.request("tuya.m.device.get", {"devId":item["device_id"]}, gid=item["lsc_home_id"])
        if not isinstance(result, dict) or not isinstance(result.get("dps"), dict):
            raise ControlError("État LSC de l'ampoule non reconnu.")
        return result

    def publish(self, item, dps):
        if not self.connected:
            raise ControlError("Connecte-toi à LSC avec le QR code.")
        result = self.request("tuya.m.device.dp.publish", {"devId":item["device_id"], "dps":dps}, gid=item["lsc_home_id"])
        if result is False:
            raise ControlError("Le serveur LSC n'a pas accepté la commande.")
        return result

    def timers(self, item):
        if not self.connected:
            raise ControlError("Connecte-toi à LSC avec le QR code.")
        result = self.request("thing.m.timer.all.list", {"devId":item["device_id"]}, gid=item["lsc_home_id"])
        if not isinstance(result, list):
            raise ControlError("Planning LSC non reconnu.")
        return result

    def close(self):
        if self.portable:
            self.portable.close()
            self.portable = None
        process, self.process = self.process, None
        if process:
            try:
                process.stdin.close()
                process.terminate()
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
