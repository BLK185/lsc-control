"""Prepare a private interoperability runtime from the locally supplied client.

Does not download, execute, or redistribute the client, and never prints its
application identity. The accepted artifact is pinned to the analysed version.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

EXPECTED = "77a5d32d13bc8084c33676e7e7bab20612deb845c6cdbddbcacc22079a6d07e5"


def prepare(client_root, source_config):
    root = Path(client_root).resolve()
    archive = root / "resources/app.asar"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError("Le client ne correspond pas à la version analysée.")
    target = root.parent / "interop"
    target.mkdir(exist_ok=True)
    with archive.open("rb") as stream:
        header = stream.read(16)
        base = 8 + struct.unpack_from("<I", header, 4)[0]
        tree = json.loads(stream.read(struct.unpack_from("<I", header, 12)[0]))

        def walk(node, parent=""):
            for name, entry in node.get("files", {}).items():
                relative = parent + name
                if "files" in entry:
                    yield from walk(entry, relative + "/")
                else:
                    yield relative, entry

        count = 0
        for relative, entry in walk(tree):
            if not relative.startswith("node_modules/") or "offset" not in entry:
                continue
            if "/prebuilds/" in relative and "/win32-ia32/" not in relative:
                continue
            destination = (target / relative).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise ValueError("Chemin d'archive invalide.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            stream.seek(base + int(entry["offset"]))
            destination.write_bytes(stream.read(entry["size"]))
            count += 1

    source = Path(source_config).read_text(encoding="utf-8")
    identity = {}
    for name in ("APPKEY", "APPSECRET"):
        match = re.search(r"export const " + name + r'\s*=\s*"([^"\n]+)"', source)
        if not match:
            raise ValueError("Configuration du client non reconnue.")
        identity[name] = match.group(1)
    block = re.search(r"export const POST_DEFAULTPARAMS\s*=\s*\{(.*?)\};", source, re.S)
    if not block:
        raise ValueError("Paramètres du client non reconnus.")
    defaults = {}
    for key, value in re.findall(r'(\w+)\s*:\s*("[^"\n]*"|APPKEY)', block.group(1)):
        defaults[key] = identity["APPKEY"] if value == "APPKEY" else json.loads(value)
    identity["defaults"] = defaults
    (target / "client-identity.json").write_text(json.dumps(identity), encoding="utf-8")
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("client_root")
    parser.add_argument("source_config")
    args = parser.parse_args()
    print("Fichiers préparés :", prepare(args.client_root, args.source_config))
