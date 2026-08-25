from pathlib import Path
import sys


if __name__ == "__main__":
    payload = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(f"lines={len(payload.splitlines())}")
    raise SystemExit(1 if "TRIGGER" in payload else 0)
