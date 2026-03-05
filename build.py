#!/usr/bin/env python3
"""Build standalone newsnet executable using PyInstaller."""

import subprocess
import sys


def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "newsnet.spec",
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\nBuild complete! Executable is in dist/newsnet")
    else:
        print("\nBuild failed.", file=sys.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
