"""Prepare a portable LSC identity on Apple Silicon from pinned official archives.

Only the native 7-Zip archive reader is executed. The Windows installer, its
Electron runtime and DLLs are treated as data and are never executed on macOS.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from core import ControlError
from connection_setup import (Asar, CLIENT, OFFICIAL_PAGE, check_cancel,
                              download, identity_from_source, verify_file)

MAC_READER = dict(url="https://github.com/ip7z/7zip/releases/download/26.04/7z2604-mac.tar.xz",
                  size=1861928, sha256="bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578")


def unpack_reader(archive, target):
    """Read one regular executable, without following archive links or paths."""
    with tarfile.open(archive, "r:xz") as tar:
        entries = [entry for entry in tar.getmembers() if entry.name in ("7zz", "./7zz")]
        if len(entries) != 1 or not entries[0].isfile() or not 0 < entries[0].size <= 32 * 1024 * 1024:
            raise ValueError("Archive reader format")
        with tar.extractfile(entries[0]) as source, Path(target).open("wb") as output:
            shutil.copyfileobj(source, output)
    Path(target).chmod(0o700)


def identity_from_artifacts(asar_path, dll_folder):
    from connection_crypto import portable_signing_material
    archive = Asar(asar_path)
    source_map = json.loads(archive.read("js/app.2ebba8d3.js.map"))
    candidates = [content for name, content in zip(source_map["sources"], source_map["sourcesContent"])
                  if name.endswith("/src/configs/index.js")]
    if len(candidates) != 1:
        raise ValueError("Client configuration")
    identity = identity_from_source(candidates[0])
    return {"defaults": identity["defaults"],
            "portable_signing_key": portable_signing_material(identity, Path(dll_folder))}


def prepare_macos(home, progress=lambda message: None, cancel=None, installer=None):
    home = Path(home).resolve()
    base = home / "connection"
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix="prepare-mac-", dir=base)).resolve()
    try:
        check_cancel(cancel)
        client = staging / "official-client.exe"
        if installer:
            verify_file(installer, CLIENT)
            shutil.copyfile(installer, client)
        else:
            progress("Téléchargement du composant officiel Action…")
            download(CLIENT, client, progress, cancel)
        progress("Préparation du lecteur d’archives pour Mac…")
        reader_archive = staging / "reader.tar.xz"
        download(MAC_READER, reader_archive, progress, cancel)
        reader = staging / "7zz"
        unpack_reader(reader_archive, reader)

        def run(*args):
            check_cancel(cancel)
            subprocess.run([str(reader), *map(str, args)], check=True, timeout=120,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            check_cancel(cancel)

        progress("Préparation locale de la connexion LSC…")
        outer = staging / "outer"
        outer.mkdir()
        run("x", "-y", "-bso0", "-bsp0", client, "$PLUGINSDIR/app-32.7z", "-o" + str(outer))
        extracted = staging / "client"
        extracted.mkdir()
        run("x", "-y", "-bso0", "-bsp0", outer / "$PLUGINSDIR/app-32.7z",
            "resources/app.asar", "resources/static/dll/*", "-o" + str(extracted))
        identity = identity_from_artifacts(extracted / "resources/app.asar", extracted / "resources/static/dll")
        check_cancel(cancel)
        private = home / "private"
        private.mkdir(exist_ok=True, mode=0o700)
        target = private / "portable-identity.json"
        if target.exists():
            raise ControlError("La connexion est déjà préparée. Ferme puis rouvre la connexion.")
        pending = staging / "identity.tmp"
        pending.write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")
        pending.chmod(0o600)
        pending.replace(target)
        (base / "macos-provenance.json").write_text(json.dumps({
            "client": CLIENT, "reader": MAC_READER, "source_page": OFFICIAL_PAGE,
            "windows_code_executed": False,
        }), encoding="utf-8")
        progress("Connexion prête. Demande du QR code…")
        return target
    except ControlError:
        raise
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError):
        raise ControlError("Préparation LSC impossible sur ce Mac. Aucun programme Windows n’a été lancé.") from None
    finally:
        if staging.parent == base and staging.name.startswith("prepare-mac-"):
            shutil.rmtree(staging, ignore_errors=True)
