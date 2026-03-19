"""Cross-platform build script for packaging sync_service into an executable.

Usage:
    python build.py          # Build for current platform
    python build.py --clean  # Clean build artifacts first
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC_FILE = ROOT / "sync_service.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
DIST_RUNTIME_FILES = [
    ".env.example",
    "启动.bat",
    "启动.command",
    "快速开始.txt",
    "公司同事使用说明.md",
]


def clean() -> None:
    """Remove previous build artifacts."""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"Cleaning {d} ...")
            shutil.rmtree(d)
    print("Clean done.")


def ensure_pyinstaller() -> None:
    """Install PyInstaller if not present."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build() -> None:
    """Run PyInstaller with the spec file."""
    ensure_pyinstaller()
    print(f"\nBuilding from {SPEC_FILE} ...")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",
    ])

    output = DIST_DIR / "sync_service"
    if output.exists():
        for name in DIST_RUNTIME_FILES:
            source = ROOT / name
            if source.exists():
                shutil.copy2(source, output / name)

        # Create state directory
        (output / "state").mkdir(exist_ok=True)

        print(f"\n{'=' * 50}")
        print(f"Build complete!")
        print(f"Output: {output}")
        print(f"{'=' * 50}")
        print(f"\nNext steps:")
        print(f"  1. cd {output}")
        if sys.platform == "win32":
            print(f"  2. sync_service.exe setup")
            print(f"  3. sync_service.exe run all --dry-run")
            print(f"  4. sync_service.exe run all")
        else:
            print(f"  2. ./sync_service setup")
            print(f"  3. ./sync_service run all --dry-run")
            print(f"  4. ./sync_service run all")
    else:
        print("Build may have failed — dist/sync_service not found")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sync_service executable")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    args = parser.parse_args()

    if args.clean:
        clean()

    build()


if __name__ == "__main__":
    main()
