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

"""Step through model files in the current directory.

OFF and OBJ files are viewed with antiview or offview. VRML/X3D files
(.wrl and .x3d) are always viewed with x3dview.

For browser-based viewers, press Space or Enter for the next model, or
Escape to exit. With antiview, close the viewer window to advance.

An optional subcommand may be inserted between the model input and viewer.
Extra viewer arguments may also be supplied. These strings are passed as
requested; their validity is the user's responsibility.
"""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import time
import subprocess
import sys

from anti_common import add_version_argument


MODEL_EXTENSIONS = {".off", ".obj", ".wrl", ".x3d"}


def find_program(*names):
    """Return the first program found on PATH."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def viewer_command(viewer, viewer_args):
    """Return command list for the requested viewer."""
    if viewer == "antiview":
        program = find_program("antiview.exe", "antiview")
        if program is None:
            raise RuntimeError("antiview not found in PATH")
        command = [program]
    else:
        script_name = viewer + ".py"
        program = find_program(script_name)
        if program is None:
            raise RuntimeError(f"{script_name} not found in PATH")
        command = [sys.executable, program]

    if viewer_args:
        command.extend(
            shlex.split(
                viewer_args,
                posix=(os.name != "nt"),
            )
        )

    return command


def source_command(path):
    """Return producer command for OFF/OBJ, else None."""
    suffix = path.suffix.lower()

    if suffix == ".off":
        program = find_program("off_util.exe", "off_util")
        if program is None:
            raise RuntimeError("off_util not found in PATH")
        return [program, str(path)]

    if suffix == ".obj":
        program = find_program("obj2off.exe", "obj2off")
        if program is None:
            raise RuntimeError("obj2off not found in PATH")
        return [program, str(path)]

    return None


def show_command(command):
    print(
        "+ " + subprocess.list2cmdline(command),
        file=sys.stderr,
    )


def run_model(
    path,
    off_viewer,
    subcommand,
    viewer_args,
    antiview_args,
    verbose,
):
    """Launch one model and return viewer name and process list."""
    suffix = path.suffix.lower()

    if suffix in {".wrl", ".x3d"}:
        viewer = "x3dview"
    else:
        viewer = off_viewer

    if viewer == "antiview":
        extra_args = f'{antiview_args} -T "{path.name}"'
    else:
        extra_args = ""

    if viewer_args:
        if extra_args:
            extra_args += " "
        extra_args += viewer_args

    viewer_cmd = viewer_command(viewer, extra_args)
    producer_cmd = source_command(path)

    processes = []
    opened_file = None
    previous = None

    try:
        if producer_cmd is None:
            opened_file = path.open("rb")
            previous = opened_file
        else:
            if verbose:
                show_command(producer_cmd)

            producer = subprocess.Popen(
                producer_cmd,
                stdout=subprocess.PIPE,
            )
            processes.append(producer)
            previous = producer.stdout

        if subcommand:
            if verbose:
                print(
                    "+ " + subcommand,
                    file=sys.stderr,
                )

            processor = subprocess.Popen(
                subcommand,
                shell=True,
                stdin=previous,
                stdout=subprocess.PIPE,
            )
            processes.append(processor)

            if previous is not opened_file:
                previous.close()

            previous = processor.stdout

        if verbose:
            show_command(viewer_cmd)

        viewer_proc = subprocess.Popen(
            viewer_cmd,
            stdin=previous,
        )
        processes.append(viewer_proc)

        if previous is not opened_file:
            previous.close()

        return viewer, processes, opened_file

    except Exception:
        if opened_file is not None:
            opened_file.close()

        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()

        raise


def stop_processes(processes, opened_file=None):
    """Stop a viewer pipeline and reap every process."""
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()

    for process in reversed(processes):
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    if opened_file is not None:
        opened_file.close()


def wait_for_browser(processes):
    """Wait for browser-based viewer helper and upstream pipeline."""
    viewer_proc = processes[-1]
    viewer_status = viewer_proc.wait()

    for process in processes[:-1]:
        status = process.wait()
        if status != 0:
            raise RuntimeError(
                f"command exited with status {status}"
            )

    if viewer_status != 0:
        raise RuntimeError(
            f"viewer exited with status {viewer_status}"
        )

def wait_for_next(viewer_proc=None):
    """Wait for next/exit key, or for Antiview to close."""
    print(
        "Space or Enter: next file.  Q: quit.",
        file=sys.stderr,
        flush=True,
    )

    if os.name == "nt":
        import msvcrt

        while True:
            if viewer_proc is not None:
                if viewer_proc.poll() is not None:
                    print(file=sys.stderr)
                    return True

            if msvcrt.kbhit():
                key = msvcrt.getwch()

                if key in (" ", "\r", "\n"):
                    print(file=sys.stderr)
                    return True

                if key in ("q", "Q"):
                    print(file=sys.stderr)
                    return False

                # Windows special keys, including arrows, arrive as
                # a prefix byte followed by a second character.
                if key in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue

            time.sleep(0.05)

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)

        while True:
            if viewer_proc is not None:
                if viewer_proc.poll() is not None:
                    print(file=sys.stderr)
                    return True

            ready, _, _ = select.select(
                [sys.stdin],
                [],
                [],
                0.05,
            )

            if not ready:
                continue

            key = sys.stdin.read(1)

            if key in (" ", "\r", "\n"):
                print(file=sys.stderr)
                return True

            if key in ("q", "Q"):
                print(file=sys.stderr)
                return False

    finally:
        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings,
        )


def make_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "-V",
        "--viewer",
        choices=["antiview", "offview"],
        default="antiview",
        help=(
            "viewer for OFF/OBJ files; WRL/X3D always use "
            "x3dview (default: %(default)s)"
        ),
    )

    parser.add_argument(
        "-s",
        "--subcommand",
        default="",
        help=(
            "quoted command inserted between model input "
            "and viewer"
        ),
    )

    parser.add_argument(
        "-a",
        "--viewer-args",
        default="",
        help="quoted arguments appended to whichever viewer is used",
    )

    parser.add_argument(
        "-A",
        "--antiview-args",
        default="-geometry 1024x768+100+100 -B black -v 0.04",
        help=(
            "arguments appended only to antiview "
            "(default: %(default)s)"
        ),
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show commands being run",
    )

    add_version_argument(parser)
    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()

    files = sorted(
        (
            path
            for path in Path(".").iterdir()
            if path.is_file()
            and path.suffix.lower() in MODEL_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )

    if not files:
        parser.exit(
            1,
            "stepview: no OFF, OBJ, WRL, or X3D files found\n",
        )

    try:
        for index, path in enumerate(files):
            print(
                f"viewing: '{path.name}'",
                file=sys.stderr,
            )

            viewer, processes, opened_file = run_model(
                path,
                args.viewer,
                args.subcommand,
                args.viewer_args,
                args.antiview_args,
                args.verbose,
            )

            if viewer == "antiview":
                go_next = wait_for_next(processes[-1])
            else:
                wait_for_browser(processes)
                go_next = wait_for_next()

            stop_processes(processes, opened_file)

            if not go_next or index == len(files) - 1:
                break

    except KeyboardInterrupt:
        print(
            "\nstepview: interrupted",
            file=sys.stderr,
        )
        return 130

    except RuntimeError as exc:
        parser.exit(
            1,
            f"stepview: {exc}\n",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
