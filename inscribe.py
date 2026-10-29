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

"""Scale one OFF model to match a selected element radius of another.

Model 2 is uniformly scaled so that the distance of its selected vertex,
edge midpoint, or face centroid from its model centroid matches that of
model 1's selected element. The two models are combined as OFF on stdout;
neither source is modified.
"""

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

from anti_common import (
    CommandError,
    add_version_argument,
    add_keep_temp_argument,
    temporary_workdir,
    max_element_index,
    read_off_file,
    run_command,
    run_pipeline,
)


ELEMENT_NAMES = {"v": "vertex", "e": "edge", "f": "face"}


def parse_element(value):
    """Parse vN, eN, or fN as a type and zero-based index."""
    match = re.fullmatch(r"([vef])(\d+)", value, re.IGNORECASE)
    if match is None:
        raise argparse.ArgumentTypeError(
            "expected vN, eN, or fN (N is a zero-based index)"
        )
    return match.group(1).lower(), int(match.group(2))


def element_label(element):
    kind, index = element
    return f"{kind}{index} ({ELEMENT_NAMES[kind]} {index})"


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "model1", help="first OFF file or Antiprism built-in model",
    )
    parser.add_argument(
        "model2", help="second OFF file or Antiprism built-in model",
    )
    parser.add_argument(
        "-a", "--first-element", type=parse_element, required=True,
        metavar="vN|eN|fN", help="element in model 1 setting target radius",
    )
    parser.add_argument(
        "-b", "--second-element", type=parse_element, required=True,
        metavar="vN|eN|fN", help="element in model 2 to match to model 1",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="print selected radii, scale factor, and commands to stderr",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def check_element_index(element, model, work_dir, *, verbose=False):
    """Preflight an index using off_report, before querying its radius."""
    kind, index = element
    maximum = max_element_index(
        model, kind, cwd=work_dir, verbose=verbose,
    )
    if index > maximum:
        if maximum < 0:
            raise ValueError(
                f"{element_label(element)}: no elements of this type"
            )
        raise ValueError(
            f"{element_label(element)}: index out of range "
            f"(valid indices: 0..{maximum})"
        )


def parse_radius_output(raw, element):
    """Parse one 'index,distance' result from off_query."""
    label = element_label(element)
    lines = [line.strip() for line in raw.decode(
        "utf-8-sig", errors="replace").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{label}: off_query returned no unique distance")
    index_text, separator, value_text = lines[0].partition(",")
    if not separator:
        raise ValueError(f"{label}: invalid off_query output")
    try:
        returned_index = int(index_text.strip())
    except ValueError as exc:
        raise ValueError(f"{label}: invalid off_query index") from exc
    if returned_index != element[1]:
        raise ValueError(f"{label}: off_query returned wrong element index")
    try:
        distance = float(value_text.strip())
    except ValueError as exc:
        raise ValueError(f"{label}: invalid distance") from exc
    if not math.isfinite(distance) or distance < 0:
        raise ValueError(f"{label}: invalid distance")
    return distance


def get_radius(element, model, work_dir, *, verbose=False):
    """Query the centroid-relative radius of an element with off_query."""
    kind, index = element
    query = kind.upper() + "d"
    result = run_command(
        ["off_query", "-c", "C", "-I", str(index), query, model],
        cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        verbose=verbose,
    )
    return parse_radius_output(result.stdout, element)


def inscribe_models(args, *, output=None):
    """Stage, measure, scale and combine, preserving the original sources."""
    with temporary_workdir("inscribe-", keep=args.keep_temp,
                           program="inscribe") as directory:
        work_dir = Path(directory)
        first = read_off_file(
            args.model1, work_dir, "inscribe1.off", verbose=args.verbose,
        )
        second = read_off_file(
            args.model2, work_dir, "inscribe2.off", verbose=args.verbose,
        )

        # Reject invalid indices before attempting either off_query.
        check_element_index(
            args.first_element, first.name, work_dir, verbose=args.verbose,
        )
        check_element_index(
            args.second_element, second.name, work_dir, verbose=args.verbose,
        )

        radius1 = get_radius(
            args.first_element, first.name, work_dir, verbose=args.verbose,
        )
        radius2 = get_radius(
            args.second_element, second.name, work_dir,
            verbose=args.verbose,
        )
        if args.verbose:
            print(f"model 1 {element_label(args.first_element)}: "
                  f"{radius1:.17g}", file=sys.stderr)
            print(f"model 2 {element_label(args.second_element)}: "
                  f"{radius2:.17g}", file=sys.stderr)

        if radius1 == 0 or radius2 == 0:
            raise ValueError(
                "selected element radius is zero; "
                "cannot calculate a non-degenerate scale"
            )
        ratio = radius1 / radius2
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError("scale factor is not finite and positive")
        if args.verbose:
            print(f"model 2 scale factor: {ratio:.17g}", file=sys.stderr)

        run_pipeline(
            [
                ["off_trans", "-S", f"{ratio:.17g}", second.name],
                ["off_util", "-", first.name],
            ],
            cwd=work_dir,
            stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        inscribe_models(args)
    except (CommandError, OSError, ValueError, OverflowError) as exc:
        parser.exit(1, f"inscribe: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
