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

"""Embed a dipyramid within a cube in four arrangements.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
Model choices:
    d   dipyramid across cube faces (default)
    e   dipyramid across cube edges
    D   alternative face arrangement
    E   alternative edge arrangement

Writes combined colored OFF geometry to standard output.
"""

import argparse
import math
import sys
from time import perf_counter
from pathlib import Path

from anti_common import (
    CommandError,
    add_version_argument,
    add_keep_temp_argument,
    temporary_workdir,
    parse_polygon,
    POLYGON_NOTATION_HELP,
    POLYGON_NOTATION_METAVAR,
    run_pipeline,
)


def make_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "polygon_fraction", nargs="?", default="6", metavar=POLYGON_NOTATION_METAVAR,
        help=POLYGON_NOTATION_HELP + " (default: 6)",
    )
    parser.add_argument(
        "-m", "--model", choices=("d", "e", "D", "E"),
        default="d",
        help="embedding: faces (d), edges (e), "
             "alternative faces (D), edges (E); default d",
    )
    parser.add_argument(
        "-D", "--dipyramid-color", default="red", metavar="COLOR",
        help="dipyramid face color (default: red)",
    )
    parser.add_argument(
        "-C", "--cube-color", default="yellow", metavar="COLOR",
        help="cube face color (default: yellow)",
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
        help="print calculations and commands to stderr",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def embedding(n, d, model):
    """Return Adrian's angle and embedding parameter A."""
    angle = math.pi * d / n
    divisor = math.tan(angle) if model in ("d", "D") else math.sin(angle)
    # A multiple of N makes the construction singular even for D != N.
    if abs(divisor) < 1e-12 or not math.isfinite(divisor):
        raise ValueError(f"degenerate embedding for {n}/{d}")
    return angle, 1 / (2 * divisor)


def dipyramid_commands(n, d, model, angle, A, color):
    """Original polygon -> transform -> face-color pipeline."""
    edge = (f"{math.sqrt(2) / 2:.17f}" if model.islower() else "1")
    rotation = (f"90,{angle * 180 / math.pi:.17f},0"
                if model in ("d", "D") else "90,0,0")
    return [
        ["polygon", "dip", f"{n}/{d}", "-e", edge, "-l", f"{A:.17f}"],
        ["off_trans", "-R", rotation],
        ["off_color", "-f", color],
    ]


def cube_commands(model, A, color):
    """Original cube transform -> half-opaque faces pipeline."""
    if model.islower():
        transforms = [
            "-R", "1,1,1,0,1,0", "-R", "0,-15,0",
            "-S", f"{A * math.sqrt(1 + 1 / 3):.17f}",
        ]
    else:
        transforms = [
            "-R", "0,45,0", "-R", "90,0,0",
            "-S", f"{A * math.sqrt(2):.17f}",
        ]
    return [
        ["off_trans", "cube", *transforms],
        ["off_color", "-f", color, "-r", "A:0.5"],
    ]


def make_embedded_off(n, d, args, *, output=None):
    """Write a dipyramid/cube combination with separate temporary models."""
    angle, A = embedding(n, d, args.model)
    if args.verbose:
        print(f"angle = {angle}", file=sys.stderr)
        print(f"A     = {A}", file=sys.stderr)

    with temporary_workdir("embeddip-", keep=args.keep_temp,
                           program="embeddip") as tmp_name:
        tmp = Path(tmp_name)
        first = tmp / "tmp1.off"
        second = tmp / "tmp2.off"
        started = perf_counter()
        with first.open("wb") as result:
            run_pipeline(
                dipyramid_commands(n, d, args.model, angle, A,
                                   args.dipyramid_color),
                cwd=tmp, stdout=result, verbose=args.verbose,
            )
        if args.verbose:
            print(f"dipyramid: {perf_counter() - started:.3f}s",
                  file=sys.stderr)

        started = perf_counter()
        with second.open("wb") as result:
            run_pipeline(
                cube_commands(args.model, A, args.cube_color),
                cwd=tmp, stdout=result, verbose=args.verbose,
            )
        if args.verbose:
            print(f"cube: {perf_counter() - started:.3f}s",
                  file=sys.stderr)

        started = perf_counter()
        run_pipeline(
            [
                ["off_util", first.name, second.name],
                ["off_color", "-e", args.edge_color, "-v", args.vertex_color],
            ],
            cwd=tmp,
            stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )
        if args.verbose:
            print(f"combine/color: {perf_counter() - started:.3f}s",
                  file=sys.stderr)


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        n, d = parse_polygon(args.polygon_fraction)
        if n < 2:
            raise ValueError("N must be at least 2 for a dipyramid")
        make_embedded_off(n, d, args)
    except (CommandError, OSError, ValueError, OverflowError) as exc:
        parser.exit(1, f"embeddip: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
