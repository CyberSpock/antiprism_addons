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

"""Make Kaufman polyhedra by repeatedly joining a model and its dual.

The original method takes the convex hull of the canonical base-and-dual
model for each iteration. The -c method uses Conway's j^n operation instead.
Both methods finish with side-based face coloring and canonicalization.
"""

import argparse
from contextlib import nullcontext
import subprocess
import sys
import tempfile
from pathlib import Path

from anti_common import (
    CommandError,
    add_version_argument,
    read_off_file,
    run_command,
)


CANONICAL_OPTIONS = (
    "-d", "0", "-l", "16", "-i", "100000",
    "-n", "100000", "-z", "100000",
)


def nonnegative_integer(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "number of iterations must be a non-negative integer"
        ) from exc
    if number < 0:
        raise argparse.ArgumentTypeError(
            "number of iterations must be a non-negative integer"
        )
    return number


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "off_file", nargs="?", default="-", metavar="model",
        help="OFF file or Antiprism built-in model (default: stdin)",
    )
    parser.add_argument(
        "n", type=nonnegative_integer,
        help="number of join iterations (non-negative integer)",
    )
    parser.add_argument(
        "-c", "--conway", action="store_true",
        help="use Conway's j^n operation instead of the hull method",
    )
    parser.add_argument(
        "-E", "--edge-color", default="lightgray", metavar="COLOR",
        help="edge color (default: %(default)s)",
    )
    parser.add_argument(
        "-V", "--vertex-color", default="gold", metavar="COLOR",
        help="vertex color (default: %(default)s)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show commands and canonicalization diagnostics on stderr",
    )
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="preserve intermediate OFF files and report their directory",
    )
    add_version_argument(parser)
    return parser


def run_canonical(work_dir, *, output_file=None, both=False,
                  stdout=None, verbose=False):
    """Run canonical with Roger's original precision/iteration settings."""
    command = ["canonical", "tmp_base.off", *CANONICAL_OPTIONS]
    if both:
        command += ["-O", "bd"]
    if output_file is not None:
        command += ["-o", output_file]
    run_command(
        command, cwd=work_dir,
        stdout=(subprocess.DEVNULL if output_file is not None else stdout),
        stderr=None if verbose else subprocess.DEVNULL,
        verbose=verbose,
    )


def hull_method(work_dir, iterations, *, verbose=False):
    """Canonical base+dual followed by convex hull, n times."""
    for step in range(iterations):
        if verbose:
            print(f"join iteration {step + 1}/{iterations}",
                  file=sys.stderr)
        run_canonical(
            work_dir, output_file="tmp_canonical_bd.off", both=True,
            verbose=verbose,
        )
        # Antiprism conv_hull returns the dimension (0..3), not a simple
        # success/failure code. Use a fresh output path so an error cannot
        # be mistaken for success because tmp_base.off already existed.
        hull = Path(work_dir) / "tmp_hull.off"
        hull.unlink(missing_ok=True)
        run_command(
            ["conv_hull", "tmp_canonical_bd.off", "-o", hull.name],
            cwd=work_dir, stdout=subprocess.DEVNULL, verbose=verbose,
            ok_returncodes=(0, 1, 2, 3),
        )
        if not hull.is_file() or hull.stat().st_size == 0:
            raise CommandError("conv_hull did not produce a nonempty OFF file")
        hull.replace(Path(work_dir) / "tmp_base.off")


def conway_method(work_dir, iterations, *, verbose=False):
    """Use j^n, or Conway's seed operation S for zero iterations."""
    operation = f"j^{iterations}" if iterations else "S"
    with (Path(work_dir) / "tmp_conway.off").open("wb") as output:
        run_command(
            ["conway", *(["-v"] if verbose else []), operation,
             "tmp_base.off"],
            cwd=work_dir, stdout=output, verbose=verbose,
        )
    (Path(work_dir) / "tmp_conway.off").replace(
        Path(work_dir) / "tmp_base.off"
    )


def make_kaufman(args, *, output=None):
    """Read a model; construct, color, canonicalize and emit OFF."""
    # A normal run cleans up, including on failure. A diagnostic run
    # deliberately keeps intermediate models for examination and reruns.
    if args.keep_temp:
        work = nullcontext(tempfile.mkdtemp(prefix="kaufman-"))
    else:
        work = tempfile.TemporaryDirectory(prefix="kaufman-")
    with work as directory:
        work_dir = Path(directory)
        if args.keep_temp:
            print(f"kaufman: temporary files: {work_dir}", file=sys.stderr)
        base = read_off_file(
            args.off_file, work_dir, "tmp_base.off", verbose=args.verbose,
        )
        if not base.stat().st_size:
            raise CommandError("empty OFF input")

        if args.conway:
            conway_method(work_dir, args.n, verbose=args.verbose)
        else:
            hull_method(work_dir, args.n, verbose=args.verbose)

        with (work_dir / "tmp_color.off").open("wb") as colored:
            run_command(
                ["off_color", "tmp_base.off", "-f", "S",
                 "-e", args.edge_color, "-v", args.vertex_color],
                cwd=work_dir, stdout=colored, verbose=args.verbose,
            )
        (work_dir / "tmp_color.off").replace(base)

        run_canonical(
            work_dir, stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        make_kaufman(args)
    except (CommandError, OSError, ValueError, OverflowError) as exc:
        parser.exit(1, f"kaufman: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
