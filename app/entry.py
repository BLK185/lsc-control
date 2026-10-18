"""Executable entry point with local diagnostics, including import failures."""
import os
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from desktop import main
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        message = traceback.format_exc()
        folder = Path(os.environ.get("LSC_CONTROL_HOME", str(Path.home() / ".lsc-control")))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "startup-error.log").write_text(message, encoding="utf-8")
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        raise SystemExit(1)
