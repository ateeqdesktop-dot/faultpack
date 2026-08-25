from pathlib import Path
import sys


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(path.read_text(encoding="utf-8").strip() if path else "hello from FaultPack")
