#!/usr/bin/env python3
"""Smoke-test installed Antiprism Addons commands (--help and --version).

Run with the interpreter in the environment containing the installed package:

    python tools/check_install.py
"""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig


def find_launcher(name):
    scripts = Path(sysconfig.get_path("scripts"))
    for path in (scripts / name, scripts / f"{name}.exe"):
        if path.is_file():
            return str(path)
    return shutil.which(name)


def main():
    try:
        dist = distribution("antiprism-addons")
    except PackageNotFoundError:
        print("antiprism-addons is not installed in this Python.",
              file=sys.stderr)
        return 1

    commands = sorted(
        ep.name for ep in dist.entry_points
        if ep.group == "console_scripts"
    )
    if not commands:
        print("No console scripts registered.", file=sys.stderr)
        return 1

    failed = []
    for command in commands:
        launcher = find_launcher(command)
        if not launcher:
            failed.append(f"{command}: launcher missing")
            continue
        for flag in ("--help", "--version"):
            proc = subprocess.run(
                [launcher, flag], capture_output=True, text=True,
                timeout=20, check=False,
            )
            expected = ("usage:" in proc.stdout.lower() if flag == "--help"
                        else dist.version in proc.stdout)
            if proc.returncode or not expected:
                failed.append(f"{command} {flag}: exit {proc.returncode}")

    if failed:
        for message in failed:
            print("FAILED:", message, file=sys.stderr)
        return 1
    print(f"All {len(commands)} installed commands passed help/version "
          f"checks ({dist.version}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
