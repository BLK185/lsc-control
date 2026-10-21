"""Exercise the Swift client against demo lamps and register the actual appex.

Registration does not prove that Control Center renders or launches the widget;
that remains a separate test on the user's Mac.
"""
import json
import os
from pathlib import Path
import plistlib
import secrets
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from control_center import create_server
from core import Controller


class DemoStore:
    def load(self):
        return {"mode": "local", "devices": []}


def main():
    build = ROOT / "app/build/macos"
    sdk = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
    probe = build / "ControlsProbe"
    subprocess.run(["xcrun", "swiftc", "-parse-as-library", "-sdk", sdk,
                    "-target", "arm64-apple-macos26.0", str(ROOT / "macos/Shared/ControlsClient.swift"),
                    str(ROOT / "macos/Tests/Probe.swift"), "-o", str(probe)], check=True)
    token = secrets.token_urlsafe(32)
    server = create_server(Controller(DemoStore(), demo=True), token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        subprocess.run([str(probe)], env={**os.environ, "LSC_TEST_CONTROLS_CODE": token}, check=True, timeout=45)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    app = ROOT / "release/macos/LSC Control.app"
    extension = app / "Contents/PlugIns/LSCControls.appex"
    subprocess.run(["codesign", "--verify", "--strict", "--deep", str(app)], check=True)
    subprocess.run(["/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
                    "-f", str(app)], check=True)
    subprocess.run(["pluginkit", "-a", str(extension)], check=True)
    result = subprocess.check_output(["pluginkit", "-m", "-A", "-D", "-i", "fr.carfr.LSCControl.Controls"], text=True)
    if "fr.carfr.LSCControl.Controls" not in result:
        raise RuntimeError("WidgetKit extension not registered")
    info = plistlib.loads((extension / "Contents/Info.plist").read_bytes())
    assert info["NSExtension"]["NSExtensionPointIdentifier"] == "com.apple.widgetkit-extension"
    print("Signed sandboxed WidgetKit extension registered on macOS; Control Center UI requires user validation.")


if __name__ == "__main__":
    main()
