#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAME = "clbs-slidevideo-edit"
PYTHON_PACKAGES = ["openai-whisper", "Pillow", "PyMuPDF"]


def skill_source() -> Path:
    root = Path(__file__).resolve().parent
    source = root / SKILL_NAME
    if not source.exists():
        raise SystemExit(f"ERROR: {source} が見つかりません。リポジトリ直下で実行してください。")
    return source


def target_dirs(target: str) -> list[Path]:
    home = Path.home()
    dirs: list[Path] = []
    if target in ("codex", "both"):
        dirs.append(home / ".codex" / "skills" / SKILL_NAME)
    if target in ("claude", "both"):
        dirs.append(home / ".claude" / "skills" / SKILL_NAME)
    return dirs


def copy_skill(source: Path, dest: Path) -> None:
    if source.resolve() == dest.resolve():
        raise SystemExit("ERROR: インストール元とインストール先が同じです。別の場所にclone/downloadしてから実行してください。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    print(f"Installed: {dest}")


def install_python_packages(skip_deps: bool) -> None:
    if skip_deps:
        print("Skip Python package install.")
        return
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *PYTHON_PACKAGES]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=False)


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        print("ffmpeg: OK")
        return
    print("WARNING: ffmpeg が見つかりません。")
    print("Mac: brew install ffmpeg")
    print("Windows: winget install --id Gyan.FFmpeg -e")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install clbs-slidevideo-edit skill for Codex or Claude Code.")
    parser.add_argument("--target", choices=["codex", "claude", "both"], default="codex", help="Install target. default: codex")
    parser.add_argument("--skip-deps", action="store_true", help="Skip Python package installation")
    args = parser.parse_args()

    source = skill_source()
    for dest in target_dirs(args.target):
        copy_skill(source, dest)

    install_python_packages(args.skip_deps)
    check_ffmpeg()
    print("")
    print("Done. Codex / Claude Code を再起動してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
