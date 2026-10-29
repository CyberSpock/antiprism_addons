#!/usr/bin/env python3

# ChatGPT assisted utility script

# Maintained by Roger Kaufman <polyhedrasmith@gmail.com>

# BSD Zero Clause License
#
# Copyright (c) 2006-2026 Roger Kaufman <polyhedrasmith@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Send an OFF model to Stella4D without changing the original.

Examples:
    stella model.off
    stella cube
    off_color -f S model.off | stella
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from anti_common import (add_version_argument, name_to_copy,
                         read_off_file, run_filter, save_local_copy)



def is_windows():
    return sys.platform == "win32"


def is_cygwin():
    return sys.platform == "cygwin"


def is_wsl():
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def to_windows_path(path):
    """Return a path that native Stella can open."""
    path = str(path)

    if is_windows():
        return path
    if is_cygwin():
        return subprocess.check_output(["cygpath", "-w", path], text=True).strip()
    if is_wsl():
        return subprocess.check_output(["wslpath", "-w", path], text=True).strip()

    return path


def stella_executable():
    """Use only the explicitly configured Stella executable path."""
    configured = os.environ.get("STELLA_EXE", "").strip()
    if not configured:
        raise RuntimeError(
            "Stella executable not found; set STELLA_EXE to the "
            "location of Stella on your system"
        )

    # Native Windows accepts Windows paths directly. Cygwin and WSL can
    # accept POSIX paths or convert a configured Windows drive path.
    if not is_windows() and len(configured) > 1 and configured[1] == ":":
        if is_cygwin():
            return subprocess.check_output(
                ["cygpath", "-u", configured], text=True
            ).strip()
        if is_wsl():
            return subprocess.check_output(
                ["wslpath", "-u", configured], text=True
            ).strip()
    return configured

def stage_input(source, staged, work_dir):
    """Stage a source OFF unchanged; compatibility filtering follows."""
    if source and source != "-" and Path(source).is_file():
        shutil.copyfile(Path(source).resolve(), staged)
        return

    if source in ("", "-"):
        with staged.open("wb") as output:
            shutil.copyfileobj(sys.stdin.buffer, output)
        return

    # Let the shared reader resolve a built-in model on every platform
    # where off_util is available on PATH.
    read_off_file(source, work_dir, staged.name)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    parser.add_argument(
        "off_file",
        nargs="?",
        default="",
        help="OFF file, Antiprism built-in model, or standard input",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show commands and temporary filename",
    )
    parser.add_argument("-s", "--save-local-copy", action="store_true",
                        help="save original colored OFF in current directory; "
                             "number copies rather than overwrite")
    add_version_argument(parser)
    args = parser.parse_args()
    invocation_dir = Path.cwd()

    try:
        exe = stella_executable()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"stella: {exc}\n")
    if not Path(exe).is_file():
        parser.exit(1, "stella: Stella executable not found at STELLA_EXE: "
                       f"{exe}\nSet STELLA_EXE to the location of "
                       "Stella on your system\n")

    # Deliberately keep this directory after stella.py exits. Stella may hand
    # the filename to an already-running instance and return immediately.
    work_dir = Path(tempfile.mkdtemp(prefix="stella-"))
    staged = work_dir / name_to_copy(args.off_file, ".off")

    try:
        stage_input(args.off_file, staged, work_dir)

        if not staged.exists() or staged.stat().st_size == 0:
            parser.error("empty OFF input")

        # Preserve Antiprism's color extensions in the user's saved copy;
        # Stella-specific compatibility filtering only changes the staged file.
        if args.save_local_copy:
            saved = save_local_copy(staged, directory=invocation_dir)
            print(f"stella: saved local copy: {saved}", file=sys.stderr)

        # Stella's OFF reader does not understand Antiprism's extended
        # explicit vertex/edge color records. Strip them only from the copy.
        processed = run_filter(["off_util", "-x", "ev"], staged.read_bytes(),
                               label="Stella OFF compatibility",
                               verbose=args.verbose)
        staged.write_bytes(processed)
        command = [exe, to_windows_path(staged)]

        if args.verbose:
            print("Launching:", subprocess.list2cmdline(command), file=sys.stderr)
            print("Temporary copy:", staged, file=sys.stderr)

        subprocess.run(command, check=True)

    except FileNotFoundError as exc:
        name = exc.filename or args.off_file
        parser.exit(1, f"stella: {name}: file not found\n")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"stella: {exc}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
