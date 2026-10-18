"""Build public Windows artifacts; private connection identities are never bundled."""
import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args],check=True,**kwargs)


def licenses(bundle):
    destination = bundle / "licenses"
    destination.mkdir(exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        for entry in distribution.files or []:
            if any(part.lower() in ("licenses","license","license.txt","license.md","copying","copying.txt") for part in entry.parts):
                source = Path(distribution.locate_file(entry))
                if source.is_file() and source.stat().st_size < 2_000_000:
                    folder = destination / name
                    folder.mkdir(exist_ok=True)
                    shutil.copy2(source,folder/source.name)
    for source in (Path(sys.base_prefix)/"LICENSE.txt",ROOT/"LICENSE"):
        if source.exists():
            shutil.copy2(source,destination/("Python-LICENSE.txt" if source.parent != ROOT else "LSC-Control-LICENSE.txt"))
    shutil.copy2(ROOT/"THIRD_PARTY_NOTICES.md",bundle/"THIRD_PARTY_NOTICES.md")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--iscc",help="Path to the Inno Setup 6 compiler")
    args=parser.parse_args()
    output=ROOT/"release"
    output.mkdir(exist_ok=True)
    build=ROOT/"app/build/public"
    build.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    sys.path.insert(0,str(ROOT/"app"))
    from PySide6.QtWidgets import QApplication
    from desktop import bulb_icon
    app=QApplication.instance() or QApplication([])
    icon=build/"LSC-Control.ico"
    if not bulb_icon().pixmap(256,256).save(str(icon),"ICO"):
        raise RuntimeError("Could not write the application icon")
    run(sys.executable,"-m","PyInstaller","--noconfirm","--log-level","WARN","--windowed","--onedir",
        "--name","LSC-Control","--distpath",output/"portable","--workpath",build/"pyinstaller",
        "--specpath",build,"--icon",icon,"--add-data",str(ROOT/"app/assets")+";assets",
        "--collect-all","tinytuya","--collect-all","keyring",ROOT/"app/entry.py",cwd=ROOT/"app")
    bundle=output/"portable/LSC-Control"
    forbidden={"portable-identity.json","client-identity.json","settings.json","devices.json","tinytuya.json","snapshot.json"}
    if any(file.name in forbidden for file in bundle.rglob("*")):
        raise RuntimeError("Private runtime data found in the public bundle")
    licenses(bundle)
    shutil.copy2(ROOT/"docs/INSTALLATION_WINDOWS.md",bundle/"INSTALLATION_WINDOWS.md")
    archive=output/f"LSC-Control-{VERSION}-windows-x64-portable.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                zipped.write(path,Path("LSC-Control")/path.relative_to(bundle))
    compiler=args.iscc or shutil.which("ISCC.exe")
    if not compiler:
        for folder in (os.environ.get("ProgramFiles(x86)",""),os.environ.get("ProgramFiles","")):
            candidate=Path(folder)/"Inno Setup 6/ISCC.exe"
            if candidate.is_file(): compiler=str(candidate); break
    if not compiler:
        raise RuntimeError("Inno Setup 6 is required; pass --iscc PATH")
    run(compiler,"/Qp","/DAppVersion="+VERSION,"/DBundleDir="+str(bundle),
        "/DOutputDir="+str(output),"/DIconFile="+str(icon),ROOT/"packaging/windows.iss")
    artifacts=[archive,output/f"LSC-Control-{VERSION}-windows-x64-setup.exe"]
    (output/"SHA256SUMS.txt").write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n" for path in artifacts),encoding="utf-8")
    print("Public artifacts built:",*[path.name for path in artifacts],sep="\n")


if __name__=="__main__":
    main()
