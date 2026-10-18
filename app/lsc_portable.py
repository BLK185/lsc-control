"""Personal LSC HTTPS transport, independent of Electron and native DLLs.

The manufacturer identity is supplied separately in a private runtime file.
This module contains no manufacturer credentials and never logs account data.
"""
import base64
import hashlib
import hmac
import json
import re
import uuid
from pathlib import Path

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


HOSTS = {"eu": "a1.tuyaeu.com", "us": "a1.tuyaus.com", "cn": "a1.tuyacn.com"}
SIGNED_KEYS = frozenset((
    "a", "v", "lat", "lon", "lang", "deviceId", "appVersion", "ttid",
    "isH5", "h5Token", "os", "clientId", "postData", "time", "requestId",
    "et", "n4h5", "sid", "chKey", "sp",
))
ALLOWED_APIS = frozenset((
    "tuya.m.user.qr.token.create", "tuya.m.user.qr.token.user.get",
    "tuya.m.location.list", "tuya.m.location.get", "tuya.m.my.group.device.list",
    "tuya.m.device.ref.info.list", "tuya.m.device.get", "tuya.m.device.dp.publish",
    "thing.m.timer.all.list", "tuya.m.timer.all.list", "thing.m.timer.category.list",
    "tuya.m.timer.category.list", "thing.m.clock.dps.add", "thing.m.clock.dps.update",
    "thing.m.clock.batch.status.update",
))
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class PortableError(Exception):
    """Only an opaque, bounded error code may cross the transport boundary."""
    def __init__(self, code):
        self.code = re.sub(r"[^A-Za-z0-9_]", "", str(code))[:100] or "HELPER_ERROR"
        super().__init__(self.code)


def _compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def derive_key(request_id, signing_key, ecode=None):
    """Return 16 ASCII bytes, matching the observed vendor primitive."""
    material = signing_key + ("_" + ecode if ecode else "")
    return hmac.new(request_id.encode("utf-8"), material.encode("utf-8"),
                    hashlib.sha256).hexdigest()[:16].encode("ascii")


def sign_form(data, signing_key):
    parts = []
    for key in sorted(data):
        if key not in SIGNED_KEYS:
            continue
        value = data[key]
        if key == "postData":
            digest = hashlib.md5(value.encode("utf-8")).hexdigest()
            value = digest[8:16] + digest[:8] + digest[24:32] + digest[16:24]
        elif isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{key}={value}")
    return hmac.new(signing_key.encode("utf-8"), "||".join(parts).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def encrypt_data(value, key):
    padder = padding.PKCS7(128).padder()
    padded = padder.update(_compact_json(value).encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode("ascii")


def decode_response(raw, key):
    if not isinstance(raw, dict):
        raise PortableError("RESPONSE_FORMAT")
    if raw.get("errorCode"):
        raise PortableError("SERVER_" + str(raw["errorCode"]))
    result, signature, timestamp = raw.get("result"), raw.get("sign"), raw.get("t")
    if (not isinstance(result, str) or not isinstance(signature, str)
            or isinstance(timestamp, bool) or not isinstance(timestamp, (str, int))):
        raise PortableError("RESPONSE_FORMAT")
    expected = hashlib.md5(
        f"result={result}||t={timestamp}||{key.decode('ascii')}".encode("utf-8")
    ).hexdigest()
    if not re.fullmatch(r"[a-f0-9]{32}", signature) or not hmac.compare_digest(expected, signature):
        raise PortableError("RESPONSE_SIGNATURE")
    try:
        encrypted = base64.b64decode(result, validate=True)
        decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        decoded = json.loads((unpadder.update(padded) + unpadder.finalize()).decode("utf-8"))
    except (ValueError, TypeError, UnicodeError):
        raise PortableError("RESPONSE_DECRYPT") from None
    if not isinstance(decoded, dict):
        raise PortableError("RESPONSE_FORMAT")
    if not decoded.get("success"):
        raise PortableError("SERVER_" + str(decoded.get("errorCode") or "REFUSED"))
    return decoded.get("result")


class LSCPortableTransport:
    """Call the observed LSC APIs; callers retain session/vault ownership.

    identity_path points to interop/portable-identity.json in the private runtime.
    A custom transport is for offline tests and receives (host, form_dict).
    """
    def __init__(self, identity_path, *, transport=None):
        try:
            identity = json.loads(Path(identity_path).read_text(encoding="utf-8-sig"))
            defaults = identity["defaults"]
            signing_key = identity["portable_signing_key"]
            if not isinstance(defaults, dict) or not isinstance(signing_key, str) or len(signing_key) < 16:
                raise ValueError()
            if any(not isinstance(k, str) or not isinstance(v, (str, int, float, bool))
                   for k, v in defaults.items()):
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise PortableError("PORTABLE_IDENTITY") from None
        self._defaults = dict(defaults)
        self._signing_key = signing_key
        self._http = requests.Session()
        self._transport = transport or self._https

    def request(self, api, data=None, version="1.0", gid=None, *, region="eu", session=None, timezone_id=None):
        if api not in ALLOWED_APIS or region not in HOSTS:
            raise PortableError("REQUEST_NOT_ALLOWED")
        if data is not None and not isinstance(data, dict):
            raise PortableError("REQUEST_DATA")
        session = session or {}
        if not isinstance(session, dict) or any(
                session.get(k) is not None and not isinstance(session[k], str)
                for k in ("sid", "ecode")):
            raise PortableError("REQUEST_SESSION")
        request_id = str(uuid.uuid4())
        key = derive_key(request_id, self._signing_key, session.get("ecode"))
        form = dict(self._defaults)
        if timezone_id is not None:
            if not isinstance(timezone_id,str) or not re.fullmatch(r"[A-Za-z0-9_+./-]{1,100}",timezone_id):
                raise PortableError("REQUEST_TIMEZONE")
            form["timeZoneId"]=timezone_id
        # Each call supplies its own session; logout cannot leave a cached SID.
        form.pop("sid", None)
        form.pop("postData", None)
        form.pop("sign", None)
        if gid is not None:
            form["gid"] = gid
        if session.get("sid"):
            form["sid"] = session["sid"]
        form.update(a=api, v=version, requestId=request_id)
        if data:
            try:
                form["postData"] = encrypt_data(data, key)
            except (TypeError, ValueError):
                raise PortableError("REQUEST_DATA") from None
        form["sign"] = sign_form(form, self._signing_key)
        return decode_response(self._transport(HOSTS[region], form), key)

    def _https(self, host, form):
        try:
            with self._http.post(f"https://{host}/api.json", data=form, timeout=20,
                                 verify=True, stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise PortableError("HTTP_" + str(response.status_code))
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise PortableError("RESPONSE_SIZE")
                try:
                    return json.loads(body)
                except (ValueError, UnicodeError):
                    raise PortableError("RESPONSE_JSON") from None
        except requests.Timeout:
            raise PortableError("TIMEOUT") from None
        except requests.RequestException:
            raise PortableError("NETWORK") from None

    def close(self):
        self._http.close()
