"""LSC Control: local Tuya transport and optional official Tuya cloud."""
from __future__ import annotations
import colorsys
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import quote

HOME = Path(os.environ.get("LSC_CONTROL_HOME", str(Path.home() / ".lsc-control")))
SERVICE = "LSC Control"
DEFAULTS = [
    {"slot": "a65", "name": "LSC A65 CCT", "rgb": False, "device_id": "", "ip": "", "version": "3.3"},
    {"slot": "a60", "name": "LSC A60 RGB-CCT", "rgb": True, "device_id": "", "ip": "", "version": "3.3"},
]

class ControlError(Exception):
    pass

def checked(result):
    if not isinstance(result, dict) or "Error" in result:
        raise ControlError("L'ampoule ne répond pas. Vérifie l'adresse IP, la clé locale et le protocole.")
    return result

def percent(value, label="Valeur"):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ControlError(f"{label} doit être entre 0 et 100.")
    return float(value)

def validate_command(action, value, rgb):
    if action == "power":
        if type(value) is not bool:
            raise ControlError("Marche/arrêt attend un booléen.")
    elif action in ("brightness", "temperature"):
        percent(value)
    elif action == "white":
        if not isinstance(value, dict) or set(value) != {"brightness", "temperature"}:
            raise ControlError("Réglages de lumière blanche invalides.")
        percent(value["brightness"])
        percent(value["temperature"])
    elif action == "countdown":
        if type(value) is not int or not 0 <= value <= 86400:
            raise ControlError("Le compte à rebours doit être compris entre 0 et 24 heures.")
    elif action == "scene":
        from light_features import validate_scene
        validate_scene(value, rgb)
    elif action in ("colour", "hsv"):
        if not rgb:
            raise ControlError("Cette ampoule ne possède pas de couleurs RGB.")
        if action == "colour":
            if not isinstance(value, list) or len(value) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in value):
                raise ControlError("Couleur RGB invalide.")
        elif not isinstance(value, dict) or set(value) != {"h", "s", "v"}:
            raise ControlError("Couleur HSV invalide.")
        else:
            if type(value["h"]) not in (int, float) or not 0 <= value["h"] <= 360:
                raise ControlError("La teinte doit être entre 0 et 360°.")
            percent(value["s"], "Saturation")
            percent(value["v"], "Luminosité")
    else:
        raise ControlError("Commande inconnue.")

class Store:
    def __init__(self):
        HOME.mkdir(parents=True, exist_ok=True)
        self.path = HOME / "settings.json"

    def load(self):
        if not self.path.exists():
            return {"mode": "local", "region": "eu", "devices": [dict(d) for d in DEFAULTS]}
        result = json.loads(self.path.read_text(encoding="utf-8"))
        if result.get("mode") not in ("local", "cloud", "lsc"):
            raise ControlError("Mode de connexion invalide.")
        return result

    def save(self, config):
        self.path.with_suffix(".tmp").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        self.path.with_suffix(".tmp").replace(self.path)

    def secret(self, name):
        import keyring
        return keyring.get_password(SERVICE, name) or ""

    def set_secret(self, name, value):
        import keyring
        if value:
            keyring.set_password(SERVICE, name, value)

class TuyaCloud:
    HOSTS = {"eu": "openapi.tuyaeu.com", "eu-w": "openapi-weaz.tuyaeu.com",
             "us": "openapi.tuyaus.com", "us-e": "openapi-ueaz.tuyaus.com",
             "cn": "openapi.tuyacn.com", "in": "openapi.tuyain.com", "sg": "openapi-sg.iotbing.com"}

    def __init__(self, region, key, secret, session=None):
        import requests
        if region not in self.HOSTS or not key or not secret:
            raise ControlError("Renseigne la région, l'Access ID et l'Access Secret du projet Tuya.")
        self.host, self.key, self.secret = self.HOSTS[region], key, secret
        self.session = session or requests.Session()
        self.token, self.expires = "", 0

    def _request(self, method, path, data=None, token_call=False):
        body = "" if data is None else json.dumps(data, separators=(",", ":"))
        stamp = str(int(time.time() * 1000))
        signed = method + "\n" + hashlib.sha256(body.encode()).hexdigest() + "\n\n" + path
        token = "" if token_call else self.token
        signature = hmac.new(self.secret.encode(), (self.key + token + stamp + signed).encode(), hashlib.sha256).hexdigest().upper()
        headers = {"client_id": self.key, "sign": signature, "t": stamp, "sign_method": "HMAC-SHA256"}
        if token:
            headers["access_token"] = token
        if data is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self.session.request(method, "https://" + self.host + path,
                                            headers=headers, data=body or None, timeout=(5, 12))
            response.raise_for_status()
            result = response.json()
        except Exception:
            raise ControlError("Connexion au cloud Tuya impossible.") from None
        if not isinstance(result, dict) or result.get("success") is not True:
            code = str(result.get("code", "?")) if isinstance(result, dict) else "?"
            raise ControlError("Le cloud Tuya a refusé la requête (code " + code + "). Vérifie les droits et l'abonnement du projet.")
        return result.get("result")

    def request(self, method, path, data=None):
        if time.time() >= self.expires:
            token = self._request("GET", "/v1.0/token?grant_type=1", token_call=True)
            self.token = token["access_token"]
            self.expires = time.time() + max(0, int(token.get("expire_time", 7200)) - 60)
        return self._request(method, path, data)

    def device(self, device_id, suffix):
        return "/v1.0/iot-03/devices/" + quote(device_id, safe="") + "/" + suffix

    def status(self, device_id):
        result = self.request("GET", self.device(device_id, "status"))
        if not isinstance(result, list):
            raise ControlError("État cloud non reconnu.")
        return {item["code"]: item["value"] for item in result}

    def functions(self, device_id):
        result = self.request("GET", self.device(device_id, "functions"))
        return {f["code"]: f for f in result.get("functions", [])}

    def command(self, device_id, commands):
        result = self.request("POST", self.device(device_id, "commands"), {"commands": commands})
        if result is not True:
            raise ControlError("Le cloud n'a pas confirmé la prise en charge de la commande.")

def cloud_command(functions, action, value):
    """Select actual declared function codes; never assume model-specific DP ids."""
    def find(*codes):
        for code in codes:
            if code in functions:
                return code
        raise ControlError("La fonction demandée n'est pas déclarée par cette ampoule.")

    if action == "power":
        return [{"code": find("switch_led", "switch"), "value": value}]
    if action == "white":
        return cloud_command(functions,"temperature",value["temperature"]) + cloud_command(functions,"brightness",value["brightness"])
    if action == "countdown":
        code=find("countdown","countdown_1")
        spec=functions[code].get("values",{})
        spec=json.loads(spec) if isinstance(spec,str) else spec
        if not spec.get("min",0)<=value<=spec.get("max",0):
            raise ControlError("Durée non prise en charge par cette ampoule.")
        return [{"code":code,"value":value}]
    if action in ("brightness", "temperature"):
        codes = ("bright_value_v2", "bright_value") if action == "brightness" else ("temp_value_v2", "temp_value")
        code = find(*codes)
        spec = functions[code].get("values", "{}")
        spec = json.loads(spec) if isinstance(spec, str) else spec
        low, high, step = spec.get("min"), spec.get("max"), spec.get("step", 1)
        if low is None or high is None or high <= low or step <= 0:
            raise ControlError("Plage de réglage cloud inconnue.")
        raw = low + round((high-low) * value / 100 / step) * step
        commands = [{"code": code, "value": max(low, min(high, raw))}]
        if action == "temperature" and "work_mode" in functions:
            commands.insert(0, {"code": "work_mode", "value": "white"})
        return commands
    if action in ("colour", "hsv"):
        # Legacy RGB encodings differ; require the documented HSV v2 schema.
        code = find("colour_data_v2")
        if action == "hsv":
            hue, saturation, brightness = value["h"] / 360, value["s"] / 100, value["v"] / 100
        else:
            hue, saturation, brightness = colorsys.rgb_to_hsv(*(v / 255 for v in value))
        payload = json.dumps({"h": round(hue*360), "s": round(saturation*1000), "v": round(brightness*1000)}, separators=(",", ":"))
        return [{"code": find("work_mode"), "value": "colour"}, {"code": code, "value": payload}]
    raise ControlError("Commande inconnue.")

def decode_hsv(raw, maximum=1000):
    """Decode only known HSV representations; malformed data stays unknown."""
    try:
        if isinstance(raw, dict):
            data = raw
        elif isinstance(raw, str) and raw.startswith("{"):
            data = json.loads(raw)
        elif isinstance(raw, str) and len(raw) == 12:
            data = {"h": int(raw[:4], 16), "s": int(raw[4:8], 16), "v": int(raw[8:], 16)}
        elif isinstance(raw, str) and len(raw) == 14:
            data = {"h": int(raw[6:10], 16), "s": int(raw[10:12], 16), "v": int(raw[12:], 16)}
            maximum = 255
        else:
            return None
        hue, saturation, brightness = data["h"], data["s"], data["v"]
        if not all(type(n) in (int, float) for n in (hue, saturation, brightness)):
            return None
        if not (0 <= hue <= 360 and 0 <= saturation <= maximum and 0 <= brightness <= maximum):
            return None
        return {"h": hue, "s": round(saturation / maximum * 100), "v": round(brightness / maximum * 100)}
    except (ValueError, TypeError, KeyError):
        return None

def cloud_state(values, functions):
    power = values.get("switch_led", values.get("switch"))
    if type(power) is not bool:
        raise ControlError("État marche/arrêt cloud inconnu.")
    def scaled(codes):
        for code in codes:
            raw = values.get(code)
            spec = functions.get(code, {}).get("values", {})
            try:
                spec = json.loads(spec) if isinstance(spec, str) else spec
                maximum = spec.get("max")
                if type(raw) in (int, float) and type(maximum) in (int, float) and maximum > 0:
                    return max(0, min(100, round(raw / maximum * 100)))
            except (ValueError, TypeError, AttributeError):
                pass
        return None
    mode = values.get("work_mode", "white")
    colour = decode_hsv(values.get("colour_data_v2")) if "colour_data_v2" in values else decode_hsv(values.get("colour_data"), 255)
    return {"power": power, "mode": mode, "hsv": colour,
            "countdown":values.get("countdown",values.get("countdown_1")),
            "scene_data":values.get("scene_data_v2",values.get("scene_data")),
            "brightness": colour["v"] if mode == "colour" and colour else scaled(("bright_value_v2", "bright_value")),
            "temperature": scaled(("temp_value_v2", "temp_value"))}

class Controller:
    def __init__(self, store=None, demo=False):
        self.store = store or Store()
        self.demo = demo
        self.lock = threading.RLock()
        self.cloud = None
        self.cloud_signature = None
        self.function_cache = {}
        self.local_retry_after = {}
        self.demo_state = {d["slot"]: {"power": False, "brightness": 100, "temperature": 20, "mode": "white", "countdown":0, "hsv": {"h": 0, "s": 100, "v": 100}} for d in DEFAULTS}

    def _device(self, slot):
        config = self.store.load()
        for item in config["devices"]:
            if item["slot"] == slot:
                return config, item
        raise ControlError("Ampoule inconnue.")

    def _cloud(self, config):
        signature = (config["region"], self.store.secret("cloud_id"), self.store.secret("cloud_secret"))
        if self.cloud is None or self.cloud_signature != signature:
            self.cloud = TuyaCloud(*signature)
            self.cloud_signature = signature
            self.function_cache.clear()
        return self.cloud

    def _functions(self, cloud, device_id):
        if device_id not in self.function_cache:
            self.function_cache[device_id] = cloud.functions(device_id)
        return self.function_cache[device_id]

    def _local(self, item):
        import tinytuya
        if not item["device_id"] or not item["ip"]:
            raise ControlError("Configure d'abord l'identifiant et l'adresse IP de cette ampoule.")
        try:
            address = ipaddress.ip_address(item["ip"])
        except ValueError:
            raise ControlError("Adresse IP invalide.") from None
        if not address.is_private or address.is_loopback:
            raise ControlError("Le mode local attend l'adresse privée de l'ampoule.")
        key = self.store.secret("local:" + item["slot"])
        if len(key.encode()) != 16:
            raise ControlError("La clé locale doit contenir 16 octets.")
        bulb = tinytuya.BulbDevice(item["device_id"], str(address), key, version=float(item["version"]))
        bulb.set_socketTimeout(3)
        bulb.set_socketRetryLimit(1)
        return bulb

    def status(self, slot):
        with self.lock:
            config, item = self._device(slot)
            if self.demo:
                from light_features import scene_options
                return dict(json.loads(json.dumps(self.demo_state[slot])), slot=slot, demo=True, scenes=scene_options(item["rgb"]))
            if not item["device_id"]:
                raise ControlError("Configure d'abord l'identifiant de cette ampoule.")
            if config["mode"] == "lsc":
                from lsc_transport import lsc_state
                from lsc_account import LSCAccount
                local = self._lsc_local(item)
                if local:
                    return self._lsc_state(item, local, "lsc-local")
                account = LSCAccount(self.store, config.get("lsc_region", "eu"))
                try:
                    return self._lsc_state(item, account.detail(item), "lsc")
                finally:
                    account.close()
            if config["mode"] == "cloud":
                cloud = self._cloud(config)
                values = cloud.status(item["device_id"])
                return dict(cloud_state(values, self._functions(cloud, item["device_id"])), slot=slot, transport="cloud")
            bulb = self._local(item)
            try:
                result = checked(bulb.status())
                dps = result.get("dps")
                if not isinstance(dps, dict) or not bulb.bulb_configured:
                    raise ControlError("Schéma de l'ampoule non reconnu. Aucune commande envoyée.")
                switch = bulb.dpset.get("switch")
                power = dps.get(str(switch))
                if type(power) is not bool:
                    raise ControlError("État marche/arrêt local inconnu.")
                def setting(feature):
                    dp = bulb.dpset.get(feature)
                    raw = dps.get(str(dp))
                    maximum = bulb.dpset.get("value_max", 0)
                    return round(raw / maximum * 100) if isinstance(raw, (int, float)) and maximum > 0 else None
                mode = dps.get(str(bulb.dpset.get("mode")), "white")
                colour = decode_hsv(dps.get(str(bulb.dpset.get("colour"))))
                return {"slot": slot, "power": power, "brightness": colour["v"] if mode == "colour" and colour else setting("brightness"),
                        "temperature": setting("colourtemp"), "hsv": colour, "mode": mode, "transport": "local",
                        "scene_data":dps.get(str(bulb.dpset.get("scene"))),"countdown":dps.get(str(bulb.dpset.get("timer")))}
            finally:
                bulb.close()

    def command(self, slot, action, value):
        with self.lock:
            config, item = self._device(slot)
            validate_command(action, value, item["rgb"])
            if self.demo:
                state = self.demo_state[slot]
                state[action] = value
                if action == "colour":
                    state["mode"] = "colour"
                    h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in value))
                    state["hsv"] = {"h": round(h * 360), "s": round(s * 100), "v": round(v * 100)}
                    state["brightness"] = state["hsv"]["v"]
                elif action == "hsv":
                    state["mode"] = "colour"
                    state["hsv"] = dict(value)
                    state["brightness"] = value["v"]
                elif action == "brightness" and state["mode"] == "colour":
                    state["hsv"]["v"] = value
                elif action == "temperature":
                    state["mode"] = "white"
                elif action == "white":
                    state.update(value,mode="white")
                elif action == "scene":
                    state.update(mode="scene",scene_data=value)
                return self.status(slot)
            if not item["device_id"]:
                raise ControlError("Configure d'abord l'identifiant de cette ampoule.")
            if config["mode"] == "lsc":
                from lsc_transport import lsc_command
                from lsc_transport import lsc_state
                from lsc_account import LSCAccount
                local = self._lsc_local(item)
                if local:
                    dps = lsc_command(item["lsc_functions"], local["dps"], action, value)
                    result = self._lsc_local(item, dps)
                    if result:
                        return self._lsc_state(item,result,"lsc-local")
                account = LSCAccount(self.store, config.get("lsc_region", "eu"))
                try:
                    detail = account.detail(item)
                    if detail.get("isOnline") is False:
                        raise ControlError("Cette ampoule est hors ligne dans LSC.")
                    dps = lsc_command(item["lsc_functions"], detail["dps"], action, value)
                    account.publish(item, dps)
                finally:
                    account.close()
                return self.status(slot)
            if config["mode"] == "cloud":
                cloud = self._cloud(config)
                cloud.command(item["device_id"], cloud_command(self._functions(cloud, item["device_id"]), action, value))
                return self.status(slot)
            bulb = self._local(item)
            try:
                checked(bulb.status())
                if not bulb.bulb_configured:
                    raise ControlError("Schéma non reconnu. Aucune commande envoyée.")
                if action == "power":
                    result = bulb.turn_on() if value else bulb.turn_off()
                elif action == "brightness":
                    result = bulb.set_brightness_percentage(value)
                elif action == "temperature":
                    result = bulb.set_colourtemp_percentage(value)
                elif action == "hsv":
                    result = bulb.set_hsv(value["h"] / 360, value["s"] / 100, value["v"] / 100)
                elif action == "countdown":
                    result = bulb.set_timer(value)
                elif action == "scene":
                    scene_dp = bulb.dpset.get("scene")
                    mode_dp = bulb.dpset.get("mode")
                    if not scene_dp or not mode_dp or scene_dp == mode_dp:
                        raise ControlError("Format de scène non disponible pour cette ampoule.")
                    result = bulb.set_multiple_values({str(scene_dp):value,str(mode_dp):"scene"})
                elif action == "white":
                    result = bulb.set_white_percentage(value["brightness"],value["temperature"])
                else:
                    result = bulb.set_colour(*value)
                # None is a possible ACK, not a verified resulting state.
                if isinstance(result, dict) and "Error" in result:
                    checked(result)
            finally:
                bulb.close()
            return self.status(slot)

    def _lsc_state(self, item, detail, transport):
        from light_features import decode_scene, scene_options
        from lsc_transport import lsc_state
        state = lsc_state(detail,item["lsc_functions"])
        profiles = dict(item.get("scene_profiles",{}))
        scene = decode_scene(state.get("scene_data"))
        if scene and profiles.get(str(scene["id"])) != scene["data"]:
            profiles[str(scene["id"])] = scene["data"]
            config = self.store.load()
            for device in config["devices"]:
                if device["slot"] == item["slot"]:
                    device["scene_profiles"] = profiles
            self.store.save(config)
        return dict(state,slot=item["slot"],transport=transport,scenes=scene_options(item["rgb"],profiles))

    def scan(self):
        import tinytuya
        results = tinytuya.deviceScan(verbose=False, maxretry=8)
        found = [{"ip": ip, "device_id": d.get("gwId", d.get("id", "")), "version": d.get("version", "")}
                 for ip, d in results.items() if isinstance(d, dict)]
        config = self.store.load()
        changed = False
        if config["mode"] == "lsc":
            for observed in found:
                for item in config["devices"]:
                    if observed["device_id"] == item["device_id"]:
                        item.update(ip=observed["ip"],version=str(observed["version"]),lsc_local_available=True)
                        self.local_retry_after.pop(item["slot"], None)
                        changed = True
            if changed:
                self.store.save(config)
        return found

    def _lsc_local(self, item, dps=None):
        """Fast path for a discovered device; fall back to LSC after a short timeout."""
        if not item.get("lsc_local_available") or time.monotonic() < self.local_retry_after.get(item["slot"], 0):
            return None
        import tinytuya
        bulb = None
        try:
            address = ipaddress.ip_address(item.get("ip", ""))
            key = self.store.secret("local:" + item["slot"])
            if not address.is_private or address.is_loopback or len(key.encode()) != 16:
                return None
            bulb = tinytuya.Device(item["device_id"], str(address), key, version=float(item["version"]))
            bulb.set_socketTimeout(0.8)
            bulb.set_socketRetryLimit(1)
            bulb.set_socketRetryDelay(0)
            bulb.retry = False
            if dps is not None:
                result = bulb.set_multiple_values(dps)
                if isinstance(result, dict) and "Error" in result:
                    raise ControlError("Commande locale non confirmée.")
            result = checked(bulb.status())
            if not isinstance(result.get("dps"), dict):
                raise ControlError("État local non reconnu.")
            return {"dps":result["dps"], "isOnline":True}
        except Exception:
            self.local_retry_after[item["slot"]] = time.monotonic() + 60
            return None
        finally:
            if bulb:
                bulb.close()
