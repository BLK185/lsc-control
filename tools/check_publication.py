"""Inspect exactly the tracked files or a release payload. Never print secret values."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES={"settings.json","devices.json","tinytuya.json","snapshot.json",
                 "portable-identity.json","client-identity.json","startup-error.log"}
FORBIDDEN_PREFIXES=("analysis/","release/","tools/battletron/","tools/github-cli/",
                    "tools/inno-setup/","tools/archive-reader/","app/.venv/","app/build/","app/dist")
FORBIDDEN_SUFFIXES=(".apk",".xapk",".asar",".har",".jks",".p12",".pfx",".log")
TOKEN=re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n(?:[A-Za-z0-9+/=]{40,80}\r?\n){2,}-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def identity_secrets(identity):
    sensitive={"clientid","appkey","appsecret","deviceid","ttid"}
    values=[identity.get("portable_signing_key")]
    values.extend(value for key,value in identity.items() if key.lower() in sensitive)
    values.extend(value for key,value in identity.get("defaults",{}).items() if key.lower() in sensitive)
    return [value for value in values if isinstance(value,str) and len(value)>=8]


def local_secrets():
    sys.path.insert(0,str(ROOT/"app"))
    from core import Store,DEFAULTS,HOME
    store=Store()
    config=store.load()
    values=set()
    def add(value):
        if isinstance(value,str) and len(value)>=8: values.add(value)
    for name in ("cloud_id","cloud_secret","lsc_session:eu","lsc_session:us","lsc_session:cn","macos_control_center"):
        raw=store.secret(name)
        if name.startswith("lsc_session:") and raw:
            for value in json.loads(raw).values(): add(value)
        else: add(raw)
    for item in config.get("devices",[]):
        add(item.get("device_id"))
        add(str(item.get("lsc_home_id","")))
        add(store.secret("local:"+item["slot"]))
        if item.get("device_id"): add(store.secret("lsc_local:"+item["device_id"]))
        generic=next((d["name"] for d in DEFAULTS if d["slot"]==item["slot"]),"")
        if item.get("name") and item["name"]!=generic:
            values.add(item["name"])
    for private in (ROOT/"tools/battletron/interop/portable-identity.json",
                    ROOT/"tools/battletron/interop/client-identity.json",
                    HOME/"private/portable-identity.json",
                    HOME/"connection/battletron-2.0.17/interop/client-identity.json"):
        if private.exists():
            for value in identity_secrets(json.loads(private.read_text(encoding="utf-8"))): add(value)
    return [encoded for value in values for encoded in (value.encode(),value.encode("utf-16-le"))]


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tracked",action="store_true")
    group.add_argument("--bundle",type=Path)
    group.add_argument("--manifest",type=Path,help="Review an explicit list of repository-relative paths before staging")
    parser.add_argument("--known-local",action="store_true",help="Also compare with private values kept on this machine, without outputting them")
    args=parser.parse_args()
    if args.manifest:
        base=ROOT
        files=[(ROOT/name).resolve() for name in args.manifest.read_text(encoding="utf-8").splitlines() if name]
        if any(not path.is_relative_to(ROOT) for path in files): raise SystemExit("Manifest path outside project")
    elif args.tracked:
        raw=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-z"])
        files=[ROOT/name.decode("utf-8") for name in raw.split(b"\0") if name]
        base=ROOT
    else:
        base=args.bundle.resolve()
        files=[p for p in base.rglob("*") if p.is_file()]
    if not files: raise SystemExit("No publication files found")
    secrets=local_secrets() if args.known_local else []
    errors=[]
    for path in files:
        relative=path.relative_to(base).as_posix()
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES or ((args.tracked or args.manifest) and relative.startswith(FORBIDDEN_PREFIXES)):
            errors.append((relative,"private path"))
        content=path.read_bytes()
        if TOKEN.search(content): errors.append((relative,"credential-shaped content"))
        if any(value in content for value in secrets): errors.append((relative,"known private value"))
    if errors:
        for path,reason in errors: print(reason+": "+path)
        raise SystemExit(1)
    print(f"Publication audit passed: {len(files)} files; known-local comparison: {bool(secrets)}")


if __name__=="__main__": main()
