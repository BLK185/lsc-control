"""Build the WidgetKit extension and its reload helper using the installed SDK."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build_native(build):
    subprocess.run(["xcodegen", "generate"], cwd=ROOT / "macos", check=True)
    subprocess.run(["xcodebuild", "-quiet", "-project", str(ROOT / "macos/LSCControls.xcodeproj"),
                    "-scheme", "LSCControls", "-configuration", "Release", "-sdk", "macosx",
                    "-arch", "arm64", "-derivedDataPath", str(build / "xcode"),
                    "CODE_SIGNING_ALLOWED=NO", "build"], check=True)
    sdk = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
    native = build / "native"
    native.mkdir(exist_ok=True)
    subprocess.run(["xcrun", "swiftc", "-O", "-sdk", sdk, "-target", "arm64-apple-macos26.0",
                    str(ROOT / "macos/ReloadControls.swift"), "-o", str(native / "LSCControlSignals")], check=True)
    extension = build / "xcode/Build/Products/Release/LSCControls.appex"
    if not extension.is_dir():
        raise RuntimeError("WidgetKit extension was not built")
    return extension, native / "LSCControlSignals"
