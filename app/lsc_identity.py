"""Import a separately supplied connection module into this user's local profile."""
import json
import os
from pathlib import Path
from core import ControlError
from lsc_portable import LSCPortableTransport, PortableError

FORBIDDEN = {"sid","ecode","localkey","local_key","password","token","access_token","refresh_token"}


def import_identity(source, home):
    try:
        path = Path(source)
        if path.stat().st_size > 65536:
            raise ValueError()
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data,dict) or set(data) != {"defaults","portable_signing_key"}:
            raise ValueError()
        if not isinstance(data["defaults"],dict) or any(key.lower() in FORBIDDEN for key in data["defaults"]):
            raise ValueError()
        transport = LSCPortableTransport(path)
        transport.close()
        target = Path(home) / "private" / "portable-identity.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
        os.chmod(temporary,0o600)
        temporary.replace(target)
        return target
    except (OSError,ValueError,KeyError,TypeError,PortableError):
        raise ControlError("Module de connexion invalide. Choisis un module compatible, sans données de compte.") from None
