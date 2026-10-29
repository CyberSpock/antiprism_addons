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

"""Orient OFF geometry using two selected elements.

Align the first element's centre with the positive Y axis; use the
second to establish the forward (positive Z) direction. The rotation
uses Antiprism's twelve-number off_trans -R operation.
"""

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

from anti_common import (
    CommandError,
    DEFAULT_EPSILON,
    add_version_argument,
    add_keep_temp_argument,
    temporary_workdir,
    max_element_indices,
    read_off_file,
    run_command,
)


ELEMENT_NAMES = {"v": "vertex", "e": "edge", "f": "face"}


def parse_element(value):
    """Parse vN, eN or fN as (type, zero-based index)."""
    match = re.fullmatch(r"([vef])(\d+)", value, re.IGNORECASE)
    if match is None:
        raise argparse.ArgumentTypeError(
            "expected vN, eN or fN (N is a zero-based index)"
        )
    return match.group(1).lower(), int(match.group(2))


def element_label(element):
    kind, index = element
    return f"{kind}{index} ({ELEMENT_NAMES[kind]} {index})"


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "off_file", metavar="model",
        help="OFF file, Antiprism built-in model, or '-' for stdin",
    )
    parser.add_argument(
        "-y", "--y-axis", dest="y_element", required=True,
        type=parse_element, metavar="vN|eN|fN",
        help="element whose centre is oriented along positive Y",
    )
    parser.add_argument(
        "-z", "--z-axis", dest="z_element", required=True,
        type=parse_element, metavar="vN|eN|fN",
        help="second element establishing positive Z direction",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show the selected coordinates and commands on stderr",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def parse_query_output(raw, element):
    """Extract exactly one indexed X,Y,Z record from off_query output.

    off_query writes, for example: 3,0.25 0.5 -0.75
    Validate the returned index, not just the command's exit status.
    """
    lines = [line.strip() for line in raw.decode(
        "utf-8-sig", errors="replace").splitlines() if line.strip()]
    description = element_label(element)
    expected_index = element[1]
    if len(lines) != 1:
        raise ValueError(
            f"{description}: index out of range or no coordinates returned"
        )
    index_text, separator, coordinates = lines[0].partition(",")
    if not separator:
        raise ValueError(f"{description}: invalid off_query output")
    try:
        actual_index = int(index_text.strip())
    except ValueError as exc:
        raise ValueError(f"{description}: invalid off_query index") from exc
    if actual_index != expected_index:
        raise ValueError(
            f"{description}: index out of range "
            f"(off_query returned {actual_index})"
        )
    fields = coordinates.replace(",", " ").split()
    if len(fields) != 3:
        raise ValueError(f"{description}: expected three coordinates")
    try:
        values = tuple(float(field) for field in fields)
    except ValueError as exc:
        raise ValueError(f"{description}: invalid coordinates") from exc
    if not all(math.isfinite(number) for number in values):
        raise ValueError(f"{description}: non-finite coordinates")
    return ",".join(fields), values


def validate_element_indices(elements, staged_name, work_dir, *,
                             verbose=False):
    """Reject invalid selections before querying any element coordinates."""
    limits = max_element_indices(
        staged_name, cwd=work_dir, verbose=verbose,
    )
    for element in elements:
        kind, index = element
        maximum = limits[kind]
        if index > maximum:
            if maximum < 0:
                raise ValueError(
                    f"{element_label(element)}: no elements of this type"
                )
            raise ValueError(
                f"{element_label(element)}: index out of range "
                f"(valid indices: 0..{maximum})"
            )


def get_coord(element, staged_name, work_dir, *, verbose=False):
    """Get a vertex location or edge/face centroid from off_query."""
    kind, index = element
    query = kind.upper() + ("c" if kind == "v" else "C")
    command = [
        "off_query", "-c", "C", "-I", str(index), query, staged_name,
    ]
    try:
        result = run_command(
            command, cwd=work_dir, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, verbose=verbose,
        )
    except CommandError as exc:
        if "not found in PATH" in str(exc):
            raise
        raise ValueError(
            f"{element_label(element)}: off_query failed; "
            "check the model and element coordinates"
        ) from exc
    return parse_query_output(result.stdout, element)


def validate_vectors(y_vec, z_vec):
    """Reject undefined and collinear directions before calling off_trans."""
    y_norm = math.hypot(*y_vec)
    z_norm = math.hypot(*z_vec)
    if not y_norm or not z_norm:
        raise ValueError(
            "selected element is at the model centroid; "
            "cannot define an orientation"
        )
    cross = (
        y_vec[1] * z_vec[2] - y_vec[2] * z_vec[1],
        y_vec[2] * z_vec[0] - y_vec[0] * z_vec[2],
        y_vec[0] * z_vec[1] - y_vec[1] * z_vec[0],
    )
    if math.hypot(*cross) <= DEFAULT_EPSILON * y_norm * z_norm:
        raise ValueError(
            "selected elements define collinear directions; "
            "cannot establish both Y and Z"
        )


def orient_model(args, *, output=None):
    """Stage input, query selected elements and rotate the OFF model."""
    if args.y_element == args.z_element:
        raise ValueError("the Y and Z elements must be different")

    with temporary_workdir("rotyz-", keep=args.keep_temp,
                           program="rotyz") as directory:
        work_dir = Path(directory)
        staged = read_off_file(
            args.off_file, work_dir, "rotyz.off", verbose=args.verbose,
        )
        validate_element_indices(
            (args.y_element, args.z_element), staged.name, work_dir,
            verbose=args.verbose,
        )
        y_coord, y_vec = get_coord(
            args.y_element, staged.name, work_dir, verbose=args.verbose,
        )
        z_coord, z_vec = get_coord(
            args.z_element, staged.name, work_dir, verbose=args.verbose,
        )
        if args.verbose:
            print(f"Y {element_label(args.y_element)}: {y_coord}",
                  file=sys.stderr)
            print(f"Z {element_label(args.z_element)}: {z_coord}",
                  file=sys.stderr)
        validate_vectors(y_vec, z_vec)
        rotation = f"{y_coord},{z_coord},0,1,0,0,0,1"
        run_command(
            ["off_trans", "-R", rotation, staged.name],
            cwd=work_dir,
            stdout=sys.stdout.buffer if output is None else output,
            verbose=args.verbose,
        )


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        orient_model(args)
    except (CommandError, OSError, ValueError) as exc:
        parser.exit(1, f"rotyz: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
