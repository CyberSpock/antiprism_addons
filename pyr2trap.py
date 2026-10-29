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

"""Make a trapezohedron from two pyramids and a central antiprism.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
Output the selected components as colored OFF on stdout.
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
    run_command,
    run_pipeline,
)



def parse_model(value):
    """Accept compact sets of part letters, as in Antiprism -x vef."""
    if not value or any(letter not in "pma" for letter in value):
        raise argparse.ArgumentTypeError(
            "model must be a combination of p, m, and a (e.g. pma)"
        )
    return "".join(letter for letter in "pma" if letter in value)


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
        "-p", "--pyramid-height", type=float, default=1.0,
        metavar="HEIGHT", help="pyramid height (default: 1)",
    )
    parser.add_argument(
        "-m", "--model", type=parse_model, default="pma",
        metavar="PARTS",
        help="parts: pyramid (p), mirrored pyramid (m), "
             "antiprism (a); combine letters, e.g. pma (default: pma)",
    )
    parser.add_argument(
        "-P", "--pyramid-color", default="red", metavar="COLOR",
        help="pyramid face color (default: red)",
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
        help="print calculated heights and commands to stderr",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def antiprism_height(n, d, pyramid_height):
    """Calculate Adrian's central antiprism height from pyramid height."""
    angle = 180.0 * d / n
    cosine = math.cos(math.pi * angle / 180)
    # A half-turn step is a pole of Adrian's height equation.
    if abs(cosine) < 1e-12:
        raise ValueError(f"undefined antiprism height for {n}/{d}")
    height = pyramid_height * (1 / cosine - 1)
    if not math.isfinite(height):
        raise ValueError("antiprism height is not finite")
    return angle, height


def make_trapezohedron(n, d, args, *, output=None):
    """Produce the selected OFF components using Antiprism executables."""
    angle, height = antiprism_height(n, d, args.pyramid_height)
    if args.verbose:
        print(f"pyramid height   = {args.pyramid_height}", file=sys.stderr)
        print(f"antiprism height = {height}", file=sys.stderr)

    selected = set(args.model)
    with temporary_workdir("pyr2trap-", keep=args.keep_temp,
                           program="pyr2trap") as tmp_name:
        tmp = Path(tmp_name)
        pyramid = tmp / "tmp1.off"
        mirrored = tmp / "tmp2.off"
        antiprism = tmp / "tmp3.off"

        # The mirrored half is made from the original pyramid even when the
        # original is not one of the requested output components.
        if "p" in selected or "m" in selected:
            with pyramid.open("wb") as result:
                run_pipeline(
                    [
                        ["polygon", "pyr", f"{n}/{d}", "-l",
                         f"{args.pyramid_height:.17f}"],
                        ["off_trans", "-R", f"0,0,{angle / 2:.17f}",
                         "-T", f"0,0,{height / 2:.17f}"],
                        ["off_color", "-f", args.pyramid_color],
                    ],
                    cwd=tmp, stdout=result, verbose=args.verbose,
                )

        if "m" in selected:
            with mirrored.open("wb") as result:
                run_command(
                    ["off_trans", "-R", f"0,0,{angle:.17f}",
                     "-M", "0,0,1", pyramid.name],
                    cwd=tmp, stdout=result, verbose=args.verbose,
                )

        if "a" in selected:
            with antiprism.open("wb") as result:
                run_pipeline(
                    [
                        ["polygon", "ant", f"{n}/{d}", "-l",
                         f"{height:.17f}"],
                        ["off_color", "-f", args.antiprism_color],
                    ],
                    cwd=tmp, stdout=result, verbose=args.verbose,
                )

        # Preserve the original component ordering, irrespective of -m order.
        components = [
            file.name for part, file in (
                ("p", pyramid), ("m", mirrored), ("a", antiprism)
            ) if part in selected
        ]
        run_pipeline(
            [
                ["off_util", *components],
                ["off_trans", "-R", "90,0,0"],
                ["off_color", "-e", args.edge_color, "-v", args.vertex_color],
            ],
            cwd=tmp,
            stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        n, d = parse_polygon(args.polygon_fraction)
        if n < 2:
            raise ValueError("n must be at least 2 for this construction")
        if not math.isfinite(args.pyramid_height):
            raise ValueError("pyramid height must be finite")
        make_trapezohedron(n, d, args)
    except (CommandError, ValueError, OverflowError, OSError) as exc:
        parser.exit(1, f"pyr2trap: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
