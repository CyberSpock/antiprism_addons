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

"""Make various color wheels."""

import argparse
from pathlib import Path
import sys

from anti_common import (CommandError, add_version_argument,
                         add_keep_temp_argument, temporary_workdir,
                         run_command, run_pipeline)


def line_count(filename):
    with open(filename, encoding="utf-8") as file:
        return sum(1 for _ in file)


def int_range(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("integer value must be positive or zero")
    return number


def polygon(num_cols, map_name, col_sys, planar_args, work_dir):
    denominator = int(num_cols)
    numerator = 3 * denominator

    run_pipeline(
        [
            ["polygon", "dih", "-s", "1", f"{numerator}/{denominator}"],
            ["off_color", "-f", "K", "-v", "E", "-e", "F", "-m", map_name],
            ["planar", "-d", "tile", "-M", col_sys, "-E", "v", *planar_args],
        ],
        cwd=work_dir,
    )


def grid(num_cols, map_name, col_sys, planar_args, work_dir):
    color_grid1 = Path(work_dir) / "color_grid1.off"
    color_grid2 = Path(work_dir) / "color_grid2.off"

    with color_grid1.open("wb") as output:
        run_pipeline(
            [
                ["col_util", "-m", map_name, "-d", "grid", "-w", "b", "-Z", str(num_cols)],
                ["off_trans", "-C"],
            ],
            cwd=work_dir,
            stdout=output,
        )

    with color_grid2.open("wb") as output:
        run_command(
            ["off_trans", "-R", "0,0,-90", color_grid1.name],
            cwd=work_dir,
            stdout=output,
        )

    run_pipeline(
        [
            ["off_util", color_grid1.name, color_grid2.name],
            ["planar", "-d", "tile", "-M", col_sys, "-E", "V", *planar_args],
        ],
        cwd=work_dir,
    )


def globe(num_cols, map_name, col_sys, planar_args, work_dir):
    count = int(num_cols)
    n_icons_count = count * 2
    color_globe1 = Path(work_dir) / "color_globe1.off"
    color_globe2 = Path(work_dir) / "color_globe2.off"

    with color_globe1.open("wb") as output:
        run_command(
            ["n_icons", "-n", str(n_icons_count), "-M", str(count),
             "-t", "0", "-m", map_name, "-F", "l"],
            cwd=work_dir,
            stdout=output,
        )

    with color_globe2.open("wb") as output:
        run_command(
            ["n_icons", "-n", str(n_icons_count), "-M", str(count),
             "-t", "0", "-m", map_name, "-F", "m"],
            cwd=work_dir,
            stdout=output,
        )

    run_pipeline(
        [
            ["off_util", color_globe1.name, color_globe2.name],
            ["planar", "-d", "tile", "-M", col_sys, "-E", "V", *planar_args],
        ],
        cwd=work_dir,
    )


def build_map(off_file, off_map, work_dir):
    with Path(work_dir, off_map).open("wb") as output:
        run_command(
            ["col_util", "-d", "4", "-U", "u", "-O", off_file],
            cwd=work_dir,
            stdout=output,
        )


def make_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "map_name",
        nargs="?",
        default="",
        help="map name or definition; if an .off file is given, build a map from it",
    )
    parser.add_argument(
        "num_cols",
        type=int_range,
        help="number of map colors; non-negative integer; zero uses all colors of an OFF file",
    )
    parser.add_argument(
        "-m", "--model",
        choices=["w", "g", "G"],
        default="w",
        help="model type: w wheel, g grid, G globe (default: %(default)s)",
    )
    parser.add_argument(
        "-c", "--col-sys",
        choices=["rgb", "hsv", "hsl"],
        default="rgb",
        help="color system (default: %(default)s)",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def main():
    parser = make_parser()
    args, planar_args = parser.parse_known_args()

    filename = args.map_name
    count = sys.maxsize

    if args.map_name and Path(args.map_name).is_file():
        filename = str(Path(args.map_name).resolve())
        count = line_count(filename)

    try:
        with temporary_workdir("color-wheel-", keep=args.keep_temp,
                               program="color_wheel") as work_dir:
            if args.map_name.lower().endswith(".off"):
                off_map = "off_map.txt"
                build_map(filename, off_map, work_dir)
                filename = off_map
                count = line_count(Path(work_dir) / off_map)

                if args.num_cols == 0:
                    args.num_cols = count

            if args.model == "G" and args.num_cols < 3:
                parser.error("with globe model, num_cols must be greater than 2")
            if args.num_cols == 0:
                parser.error("num_cols must be greater than zero")
            if args.num_cols > count:
                parser.error(f"num_cols is greater than map count ({count})")

            if args.model == "w":
                polygon(args.num_cols, filename, args.col_sys, planar_args, work_dir)
            elif args.model == "g":
                grid(args.num_cols, filename, args.col_sys, planar_args, work_dir)
            else:
                globe(args.num_cols, filename, args.col_sys, planar_args, work_dir)

    except CommandError as exc:
        parser.exit(1, f"color_wheel: {exc}\n")
    except OSError as exc:
        parser.exit(1, f"color_wheel: {exc}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
