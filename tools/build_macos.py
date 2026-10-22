"""Build a self-contained Apple Silicon application and drag-to-Applications DMG.

Ad-hoc signing verifies bundle integrity; it is not Developer ID signing or
notarization. No account/profile or vendor resource is copied into the app.
"""
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

from build_windows import licenses

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.5.1"


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("Build on an Apple Silicon macOS runner.")
    output = ROOT / "release/macos"
    output.mkdir(parents=True, exist_ok=True)
    build = ROOT / "app/build/macos"
    build.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "app"))
    from PySide6.QtWidgets import QApplication
    from desktop import bulb_icon
    qt = QApplication.instance() or QApplication([])
    iconset = build / "LSC.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{size}x{size}" + ("@2x" if scale == 2 else "") + ".png"
            if not bulb_icon(size * scale).pixmap(size * scale, size * scale).save(str(iconset / name)):
                raise RuntimeError("Application icon could not be written")
    icon = build / "LSC.icns"
    run("iconutil", "--convert", "icns", "--output", icon, iconset)
    from build_controls_macos import build_native
    extension, helper = build_native(build)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
        "--windowed", "--onedir", "--name", "LSC Control", "--target-architecture", "arm64",
        "--osx-bundle-identifier", "fr.carfr.LSCControl", "--icon", icon,
        "--distpath", output, "--workpath", build / "pyinstaller", "--specpath", build,
        "--add-data", str(ROOT / "app/assets") + ":assets",
        "--add-binary", str(helper) + ":native",
        "--collect-all", "tinytuya", "--collect-all", "keyring", ROOT / "app/entry.py")
    bundle = output / "LSC Control.app"
    resources = bundle / "Contents/Resources"
    licenses(resources)
    shutil.copy2(ROOT / "docs/INSTALLATION_MACOS.md", resources / "INSTALLATION_MACOS.md")
    info = bundle / "Contents/Info.plist"
    metadata = plistlib.loads(info.read_bytes())
    metadata.update(CFBundleShortVersionString=VERSION, CFBundleVersion="6",
                    LSMinimumSystemVersion="13.0", NSHighResolutionCapable=True,
                    NSLocalNetworkUsageDescription="Retrouver vos éclairages LSC sur le réseau local pour un contrôle plus rapide.",
                    NSHumanReadableCopyright="LSC Control contributors — MIT")
    info.write_bytes(plistlib.dumps(metadata))
    plugins = bundle / "Contents/PlugIns"
    plugins.mkdir(exist_ok=True)
    widget = plugins / extension.name
    shutil.copytree(extension, widget, symlinks=True)
    run("codesign", "--force", "--sign", "-", "--entitlements", ROOT / "macos/Controls.entitlements", widget)
    run(sys.executable, ROOT / "tools/check_publication.py", "--bundle", bundle)
    run("codesign", "--force", "--sign", "-", bundle)
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", bundle)
    staging = build / "dmg"
    staging.mkdir(exist_ok=True)
    app_link = staging / bundle.name
    if app_link.exists():
        raise RuntimeError("Use a clean build directory to build the DMG.")
    shutil.copytree(bundle, app_link, symlinks=True)
    (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
    shutil.copy2(ROOT / "docs/INSTALLATION_MACOS.md", staging / "Lisez-moi.md")
    dmg = output / f"LSC-Control-{VERSION}-macos-arm64.dmg"
    run("hdiutil", "create", "-ov", "-volname", "LSC Control", "-srcfolder", staging,
        "-format", "UDZO", dmg)
    archive = output / f"LSC-Control-{VERSION}-macos-arm64.zip"
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", bundle, archive)
    (output / "SHA256SUMS-macos.txt").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
        for path in (dmg, archive)), encoding="utf-8")
    print("macOS arm64 DMG and ZIP built.")


if __name__ == "__main__":
    main()
