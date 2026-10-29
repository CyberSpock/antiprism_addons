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

"""Generate a trapezohedron that is dual to and a stellation of an antiprism.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
When n/d = 2, the model is a compound of tetrahedra.
Output selected parts as colored OFF on stdout.
"""

import argparse
import math
from pathlib import Path
import sys

from anti_common import (
    CommandError,
    POLYGON_NOTATION_HELP,
    POLYGON_NOTATION_METAVAR,
    add_version_argument,
    add_keep_temp_argument,
    temporary_workdir,
    parse_polygon,
    run_pipeline,
)


def parse_model(value):
    """Accept a compact set of model letters: t, a or ta."""
    if not value or any(letter not in "ta" for letter in value):
        raise argparse.ArgumentTypeError(
            "model must be a combination of t and a (e.g. ta)"
        )
    return "".join(letter for letter in "ta" if letter in value)


def make_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "polygon_fraction", nargs="?", default="6",
        metavar=POLYGON_NOTATION_METAVAR,
        help=POLYGON_NOTATION_HELP + " (default: 6)",
    )
    parser.add_argument(
        "-m", "--model", type=parse_model, default="t", metavar="PARTS",
        help="trapezohedron (t), reciprocal antiprism (a), or both (ta); "
             "default t",
    )
    parser.add_argument(
        "-r", "--rotate-antiprism", action="store_true",
        help="rotate the reciprocal antiprism into the trapezohedron; "
             "include a in selected parts",
    )
    parser.add_argument(
        "-T", "--trapezohedron-color", default="red", metavar="COLOR",
        help="trapezohedron face color (default: red)",
    )
    parser.add_argument(
        "-A", "--antiprism-color", default="blue", metavar="COLOR",
        help="antiprism face color (default: blue)",
    )
    parser.add_argument(
        "-E", "--edge-color", default="lightgray", metavar="COLOR",
        help="edge color (default: lightgray)",
    )
    parser.add_argument(
        "-V", "--vertex-color", default="gold", metavar="COLOR",
        help="vertex color (default: gold)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="print calculated height and commands to stderr",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def antiprism_height(n, d):
    """Adrian's antiprism height for the dual/stellation construction."""
    a = math.pi * d / n
    cosine = math.cos(a)
    divisor = 1 + cosine
    if divisor <= 1e-12:
        raise ValueError(f"undefined antiprism height for {n}/{d}")
    height = 2 * math.cos(a / 2) * math.sqrt((1 - cosine) / divisor)
    if not math.isfinite(height):
        raise ValueError(f"non-finite antiprism height for {n}/{d}")
    return height


def make_trapstel(n, d, args, *, output=None):
    """Build the stellated trapezohedron and optionally its reciprocal."""
    height = antiprism_height(n, d)
    rotation = 180.0 * d / n if args.rotate_antiprism else 0.0
    # Rotation makes the reciprocal visible, but never hides selected parts.
    models = args.model
    if args.rotate_antiprism and "a" not in models:
        models += "a"
    radius = math.cos(math.pi * d / (2 * n))

    if args.verbose:
        print(f"antiprism height = {height}", file=sys.stderr)

    with temporary_workdir("trapstel-", keep=args.keep_temp,
                           program="trapstel") as tmp_name:
        tmp = Path(tmp_name)
        trap = tmp / "tmp1.off"
        ant = tmp / "tmp2.off"

        # The reciprocal uses tmp1 even when only the antiprism is selected.
        with trap.open("wb") as result:
            run_pipeline(
                [
                    ["polygon", "ant", f"{n}/{d}", "-s", "1", "-r", "1",
                     "-l", f"{height:.17f}"],
                    ["off_color", "-f", args.trapezohedron_color],
                ],
                cwd=tmp, stdout=result, verbose=args.verbose,
            )

        if "a" in models:
            with ant.open("wb") as result:
                run_pipeline(
                    [
                        ["pol_recip", "-r", f"{radius:.17f}", trap.name],
                        ["off_trans", "-R", f"0,0,{rotation:.17f}"],
                        ["off_color", "-f", args.antiprism_color],
                    ],
                    cwd=tmp, stdout=result, verbose=args.verbose,
                )

        # Keep t-before-a ordering, regardless of the order of -m letters.
        selected = [
            file.name for letter, file in (("t", trap), ("a", ant))
            if letter in models
        ]
        run_pipeline(
            [
                ["off_util", *selected],
                ["off_trans", "-R", "90,0,0"],
                ["off_color", "-e", args.edge_color, "-v", args.vertex_color],
            ],
            cwd=tmp, stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        n, d = parse_polygon(args.polygon_fraction)
        if n < 2:
            raise ValueError("n must be at least 2 for this construction")
        make_trapstel(n, d, args)
    except (CommandError, ValueError, OverflowError, OSError) as exc:
        parser.exit(1, f"trapstel: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
