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

"""Common helpers for Antiprism Addons Python programs."""

from pathlib import Path
from contextlib import contextmanager
import tempfile
import shutil
import subprocess
import sys
import math
import os
import shlex


ADDONS_VERSION = "0.9.0b1"  # Beta; authoritative package version
DEFAULT_LIMIT = 12
DEFAULT_EPSILON = 10.0 ** -DEFAULT_LIMIT

# Shared n/d help text; generators enforce any construction restrictions.
POLYGON_NOTATION_METAVAR = "n[/d]"
POLYGON_NOTATION_HELP = (
    "n or n/d; d is the step (default 1), not a denominator. "
    "Values are not reduced."
)


def add_version_argument(parser):
    """Give every executable the same Antiprism Addons package version."""
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {ADDONS_VERSION}")


def add_keep_temp_argument(parser):
    """Add the standard temporary-model retention switch."""
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="preserve temporary files and report their directory",
    )


@contextmanager
def temporary_workdir(prefix, *, keep=False, program=None):
    """Manage a temporary work directory, optionally preserving it.

    Preserved directories remain after success and failure; ordinary runs
    clean up in both cases. Emit the path on stderr immediately so even an
    interrupted or failed command leaves an identifiable working directory.
    """
    if keep:
        directory = Path(tempfile.mkdtemp(prefix=prefix))
        label = program or prefix.rstrip("-")
        print(f"{label}: temporary files: {directory}", file=sys.stderr)
        yield directory
    else:
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            yield Path(directory)


class CommandError(RuntimeError):
    """Raised when an external command cannot be started or fails."""


def _resolve_program(command):
    if not command:
        raise CommandError("empty command")
    program = str(command[0])
    resolved = shutil.which(program)
    if resolved is None:
        raise CommandError(f"required program '{program}' not found in PATH")
    return [resolved, *[str(arg) for arg in command[1:]]]


def _show_command(command, verbose):
    if verbose:
        print("+", subprocess.list2cmdline(command), file=sys.stderr)


def run_command(command, *, cwd=None, stdin=None, stdout=None, stderr=None,
                verbose=False, ok_returncodes=(0,)):
    """Run an external command without a shell.

    A program may document nonzero *successful* exit codes (Antiprism's
    conv_hull returns the dimension of its result, for example). Supply those
    codes at the call site; the default remains strictly zero for other tools.
    """
    command = _resolve_program(command)
    _show_command(command, verbose)
    try:
        result = subprocess.run(
            command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
            check=False,
        )
    except OSError as exc:
        raise CommandError(f"{command[0]}: {exc}") from exc
    if result.returncode not in ok_returncodes:
        raise CommandError(
            f"command failed with exit status {result.returncode}: {command[0]}"
        )
    return result


def run_pipeline(commands, *, cwd=None, stdin=None, stdout=None, stderr=None, verbose=False):
    """Run a pipeline of external commands directly, without a shell."""
    if not commands:
        raise CommandError("empty pipeline")

    resolved = [_resolve_program(command) for command in commands]
    for command in resolved:
        _show_command(command, verbose)

    processes = []
    previous_stdout = None
    try:
        for index, command in enumerate(resolved):
            first = index == 0
            last = index == len(resolved) - 1
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=stdin if first else previous_stdout,
                stdout=stdout if last else subprocess.PIPE,
                stderr=stderr,
            )
            processes.append(process)
            if previous_stdout is not None:
                previous_stdout.close()
            previous_stdout = None if last else process.stdout

        failed = None
        for process, command in zip(processes, resolved):
            returncode = process.wait()
            if returncode != 0 and failed is None:
                failed = (returncode, command[0])

        if failed:
            returncode, program = failed
            raise CommandError(
                f"pipeline command failed with exit status {returncode}: {program}"
            )
        return processes[-1]

    except OSError as exc:
        for process in processes:
            if process.poll() is None:
                process.kill()
        for process in processes:
            process.wait()
        raise CommandError(str(exc)) from exc


def _work_path(work_dir):
    """Accept a TemporaryDirectory object or a normal path.

    A pathlib.Path also has a .name property: don't mistake the final
    directory component for the complete path.
    """
    if isinstance(work_dir, (str, os.PathLike)):
        return Path(work_dir)
    if hasattr(work_dir, "name"):
        return Path(work_dir.name)
    return Path(work_dir)


def read_off_file(model, work_dir, work_file, *, verbose=False):
    """Read an OFF file, built-in model, or stdin into work_file.

    Real files are piped to off_util through stdin so native Windows Python can
    use Cygwin-built Antiprism tools without passing Windows pathnames to them.
    Empty model or '-' reads stdin directly.
    """
    work_dir = _work_path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    destination = work_dir / work_file

    if model in ("", "-", None):
        with destination.open("wb") as output:
            shutil.copyfileobj(sys.stdin.buffer, output)
        return destination

    source = Path(model)
    if not source.is_file() and any(c in str(model) for c in "*?[]"):
        raise CommandError(f"input OFF file not found: {model}")

    try:
        with destination.open("wb") as output:
            if source.is_file():
                with source.open("rb") as input_file:
                    run_command(
                        ["off_util"],
                        stdin=input_file,
                        stdout=output,
                        verbose=verbose,
                    )
            else:
                run_command(
                    ["off_util", str(model)],
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    verbose=verbose,
                )
    except CommandError as exc:
        destination.unlink(missing_ok=True)
        raise CommandError(f"input file or model '{model}' not found") from exc

    if not destination.exists() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise CommandError(f"empty OFF input from '{model}'")

    return destination


COLOR_TEST_OFF = b"OFF\n1 0 0\n0 0 0\n"


def name_to_copy(filename=None, extension=None):
    """Return an informative basename for a temporary model copy.

    extension, when specified, is the extension of the served/converted data,
    not necessarily the extension of the source model.
    """
    name = Path(str(filename)).name if filename not in (None, "", "-") else "stdin"
    path = Path(name)
    stem = path.stem if path.suffix else name
    suffix = extension if extension is not None else path.suffix
    if suffix and not suffix.startswith("."):
        suffix = "." + suffix
    return f"{stem}_copy{suffix}"



def save_local_copy(source, *, directory=None):
    """Copy a staged model to directory, numbering names without overwriting.

    Input should already have an informative ``*_copy.off`` basename.
    The destination is reserved atomically, including across concurrent runs.
    """
    source = Path(source)
    directory = Path.cwd() if directory is None else Path(directory)
    stem, suffix = source.stem, source.suffix

    number = 1
    while True:
        basename = (f"{stem}{suffix}" if number == 1
                    else f"{stem}_{number}{suffix}")
        destination = directory / basename
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o666)
        except FileExistsError:
            number += 1
            continue

        try:
            with os.fdopen(fd, "wb") as output:
                with source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return destination

def run_filter(command, data, *, label=None, verbose=False, shell=False):
    """Filter OFF bytes through one command or an explicit shell pipeline.

    Shell execution is only for -p commands intentionally written by the
    caller; normal Antiprism commands use argv lists without a shell.
    """
    if shell:
        if not isinstance(command, str):
            raise CommandError("shell filter requires a command string")
        command_to_run = command
    else:
        command_to_run = _resolve_program(command)
    if verbose:
        display = command if shell else shlex.join([str(x) for x in command])
        print("+ " + display, file=sys.stderr, flush=True)
    label = label or (command if shell else str(command[0]))
    try:
        result = subprocess.run(
            command_to_run, shell=shell, input=data,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        raise CommandError(f"{label}: cannot run command: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise CommandError(
            f"{label}: exit {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    if not result.stdout.strip():
        raise CommandError(f"{label}: empty OFF output")
    if verbose and result.stderr:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def read_off_bytes(model, *, verbose=False):
    """Read a real OFF file first, otherwise try an Antiprism built-in model.

    Caller must reject wildcard and multi-file inputs before this helper.
    Using stdin for '-' and None is supported.
    """
    if model is None or str(model) in ("", "-"):
        data = sys.stdin.buffer.read()
        if not data.strip():
            raise CommandError("empty OFF input")
        return data
    name = str(model)
    source = Path(name)
    if source.is_file():
        data = source.read_bytes()
    else:
        if any(c in name for c in "*?[]"):
            raise CommandError(f"input OFF file not found: {name}")
        try:
            command = _resolve_program(["off_util", name])
            _show_command(command, verbose)
            proc = subprocess.run(command, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, check=False)
        except OSError as exc:
            raise CommandError(f"{name}: {exc}") from exc
        if proc.returncode:
            detail = proc.stderr.decode("utf-8", errors="replace").strip()
            raise CommandError(
                f"input file or built-in model '{name}' not found"
                + (f": {detail}" if verbose and detail else "")
            )
        data = proc.stdout
    if not data.strip():
        raise CommandError(f"empty OFF input from '{name}'")
    return data


def resolve_color(color, *, verbose=False):
    """Ask off_color for normalized RGB[A]; support its named colors.

    Interpret byte-valued integer channels as 0..255. A fourth channel is
    returned when present; otherwise opacity defaults to 1.
    """
    result = run_filter(["off_color", "-v", color], COLOR_TEST_OFF,
                        label=f"color {color!r}", verbose=verbose)
    records = []
    for line in result.decode("utf-8-sig", errors="replace").splitlines():
        tokens = line.partition("#")[0].split()
        if len(tokens) in (5, 6) and tokens[:2] == ["1", "0"]:
            records.append(tokens[2:])
    if len(records) != 1:
        raise CommandError(f"invalid color output for {color!r}")
    try:
        values = [float(x) for x in records[0]]
    except ValueError as exc:
        raise CommandError(f"invalid color output for {color!r}") from exc
    if any(not math.isfinite(v) or v < 0 or v > 255 for v in values):
        raise CommandError(f"invalid color output for {color!r}")
    # Antiprism may emit normalized float colors or integer byte values.
    if max(values) > 1:
        values = [v / 255 for v in values]
    if len(values) == 3:
        values.append(1.)
    return tuple(values)


def valid_color(color):
    """True if off_color accepts color; false otherwise, without diagnostics."""
    try:
        resolve_color(color)
    except (CommandError, ValueError, TypeError, OSError):
        return False
    return True


def parse_polygon(value):
    """Parse n or n/d without reducing or imposing polygon-step limits.

    This parses notation, not geometry: a caller may impose constraints.
    """
    parts = str(value).strip().split("/")
    if len(parts) not in (1, 2) or not all(parts):
        raise ValueError("expected n or n/d")
    try:
        n = int(parts[0])
        d = int(parts[1]) if len(parts) == 2 else 1
    except ValueError as exc:
        raise ValueError("n and d must be integers") from exc
    if n < 1 or d < 1:
        raise ValueError("n and d must be positive")
    if n == d:
        raise ValueError("n and d cannot be equal")
    return n, d


_ELEMENT_REPORT_FIELDS = {
    "v": "num_verts", "e": "num_edges", "f": "num_faces",
}


def _get_element_limits(model, fields, *, cwd=None, verbose=False):
    """Read selected element index limits in one off_report invocation."""
    result = run_command(
        ["off_report", str(model), "-S", "G"],
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        verbose=verbose,
    )
    limits = {}
    wanted = set(fields.values())
    for line in result.stdout.decode(
            "utf-8-sig", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and key in wanted:
            count = value.strip()
            if not count.isdecimal():
                raise CommandError(f"off_report: invalid {key} count")
            limits[key] = int(count) - 1
    for field in wanted:
        if field not in limits:
            raise CommandError(f"off_report: missing {field} count")
    return {kind: limits[field] for kind, field in fields.items()}


def max_element_indices(model, *, cwd=None, verbose=False):
    """Return {'v': max_v, 'e': max_e, 'f': max_f} in one report.

    Element indices are zero-based. An empty element list has maximum -1.
    """
    return _get_element_limits(
        model, _ELEMENT_REPORT_FIELDS, cwd=cwd, verbose=verbose,
    )


def max_element_index(model, kind, *, cwd=None, verbose=False):
    """Return the last valid zero-based index for v, e, or f.

    For a staged model, pass the basename and set ``cwd`` to its directory,
    avoiding Windows-to-Cygwin pathname incompatibilities.
    """
    kind = str(kind).lower()
    if kind not in _ELEMENT_REPORT_FIELDS:
        raise ValueError("element type must be v, e or f")
    return _get_element_limits(
        model, {kind: _ELEMENT_REPORT_FIELDS[kind]},
        cwd=cwd, verbose=verbose,
    )[kind]
