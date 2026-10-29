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

"""Regression tests for the modern embeddip.py and common N/D parser."""

import io
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import anti_common
import embeddip


class PolygonParsingTests(unittest.TestCase):
    def test_notation_not_reduced(self):
        examples = {
            "5": (5, 1), "5/4": (5, 4), "5/6": (5, 6),
            "5/9": (5, 9), "10/4": (10, 4), "10/5": (10, 5),
            "100/2": (100, 2), "2/1": (2, 1),
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(anti_common.parse_polygon(text), expected)

    def test_bad_input(self):
        bad = ("", "5/5", "1", "0/2", "2/0", "-5/2",
               "5/", "/5", "5/3/2", "hi", "5/x")
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    anti_common.parse_polygon(text)

    def test_parse_default(self):
        self.assertEqual(embeddip.make_parser().parse_args([]).polygon_fraction,
                         "6")


class PipelineTests(unittest.TestCase):
    def test_embedding_math(self):
        for mode in ("d", "D", "e", "E"):
            with self.subTest(mode=mode):
                angle, parameter = embeddip.embedding(5, 4, mode)
                self.assertAlmostEqual(angle, math.pi * 4 / 5)
                fn = math.tan if mode.lower() == "d" else math.sin
                self.assertAlmostEqual(parameter, 1/(2*fn(angle)))

    def test_degenerate_fraction(self):
        for mode in ("d", "e", "D", "E"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "degenerate"):
                    embeddip.embedding(5, 10, mode)

    def test_all_four_modes_and_colors(self):
        for mode in ("d", "e", "D", "E"):
            with self.subTest(mode=mode):
                args = embeddip.make_parser().parse_args([
                    "10/4", "-m", mode, "-D", "gold", "-C", "blue",
                    "-E", "lightgrey", "-V", "red"])
                calls = []

                def fake_pipeline(commands, *, cwd, stdout, verbose):
                    calls.append(commands)
                    if stdout is not None:
                        stdout.write(b"OFF\n1 0 0\n0 0 0\n")

                output = io.BytesIO()
                with mock.patch.object(embeddip, "run_pipeline",
                                       side_effect=fake_pipeline):
                    embeddip.make_embedded_off(10, 4, args, output=output)

                self.assertEqual(len(calls), 3)
                self.assertEqual(calls[0][0][:3],
                                 ["polygon", "dip", "10/4"])
                self.assertEqual(calls[0][-1],
                                 ["off_color", "-f", "gold"])
                self.assertEqual(calls[1][0][:2], ["off_trans", "cube"])
                self.assertEqual(calls[1][-1],
                                 ["off_color", "-f", "blue", "-r", "A:0.5"])
                self.assertEqual(calls[2], [
                    ["off_util", "tmp1.off", "tmp2.off"],
                    ["off_color", "-e", "lightgrey", "-v", "red"],
                ])
                self.assertIn(b"OFF", output.getvalue())
                self.assertEqual("-R" in calls[0][1], True)
                self.assertEqual(calls[0][1][-1] == "90,0,0",
                                 mode in ("e", "E"))
                self.assertEqual(calls[0][0][4] == "1",
                                 mode.isupper())

    def test_hyphenated_color_options(self):
        parser = embeddip.make_parser()
        args = parser.parse_args([
            "5/2", "--dipyramid-color", "gold", "--cube-color", "blue",
            "--edge-color", "lightgrey", "--vertex-color", "red",
        ])
        self.assertEqual(args.dipyramid_color, "gold")
        self.assertEqual(args.cube_color, "blue")
        self.assertEqual(args.edge_color, "lightgrey")
        self.assertEqual(args.vertex_color, "red")
        for obsolete in ("--dipyramidColor", "--cubeColor",
                         "--edgeColor", "--vertexColor"):
            self.assertNotIn(obsolete, parser.format_help())

    def test_common_polygon_help(self):
        help_text = embeddip.make_parser().format_help()
        self.assertIn("d is the step (default 1), not a", help_text)
        self.assertIn("Values are not reduced.", help_text)

    def test_version_and_help(self):
        script = Path(embeddip.__file__).resolve()
        version = subprocess.run(
            [sys.executable, str(script), "--version"],
            capture_output=True, text=True, check=True)
        self.assertIn(anti_common.ADDONS_VERSION, version.stdout)
        help_result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True, text=True, check=True)
        self.assertNotIn("pyramidHeight", help_result.stdout)

    def test_invalid_inputs_fail_cleanly(self):
        script = Path(embeddip.__file__).resolve()
        for fraction in ("5/5", "0/2", "1/2", "5/10"):
            with self.subTest(fraction=fraction):
                p = subprocess.run([sys.executable, str(script), fraction],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode, 1)
                self.assertIn("embeddip:", p.stderr)


if __name__ == "__main__":
    unittest.main()
