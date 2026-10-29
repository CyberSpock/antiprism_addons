#!/usr/bin/env python3
"""Regression tests for Trapstel's geometry, CLI and external pipelines."""

import contextlib
import io
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import trapstel
from anti_common import parse_polygon


class TrapstelTest(unittest.TestCase):
    def test_notation_and_special_compound(self):
        self.assertEqual(parse_polygon("10/5"), (10, 5))
        self.assertEqual(parse_polygon("5/9"), (5, 9))
        self.assertEqual(parse_polygon("10/4"), (10, 4))
        self.assertAlmostEqual(trapstel.antiprism_height(10, 5),
                               math.sqrt(2))

    def test_adrian_height_formula(self):
        n, d = 6, 1
        a = math.pi * d / n
        expected = 2 * math.cos(a / 2) * math.sqrt(
            (1 - math.cos(a)) / (1 + math.cos(a))
        )
        self.assertAlmostEqual(trapstel.antiprism_height(n, d), expected)

    def test_singular_input(self):
        with self.assertRaisesRegex(ValueError, "undefined antiprism height"):
            trapstel.antiprism_height(5, 15)

    def test_parser_and_help(self):
        parser = trapstel.make_parser()
        args = parser.parse_args([
            "5/4", "-m", "ta", "-r",
            "--trapezohedron-color", "red", "--antiprism-color", "blue",
            "--edge-color", "lightgray", "--vertex-color", "gold",
        ])
        self.assertEqual(args.polygon_fraction, "5/4")
        self.assertEqual(args.model, "ta")
        self.assertTrue(args.rotate_antiprism)
        self.assertEqual(parser.parse_args([]).model, "t")
        help_text = parser.format_help()
        self.assertIn("n[/d]", help_text)
        self.assertIn("n or n/d; d is the step", help_text)
        self.assertIn("--rotate-antiprism", help_text)
        self.assertNotIn("--rotateAntiprism", help_text)

    def test_compact_selection(self):
        parser = trapstel.make_parser()
        for inp, want in [("ta", "ta"), ("at", "ta"), ("t", "t"),
                          ("a", "a"), ("taa", "ta")]:
            with self.subTest(inp=inp):
                self.assertEqual(parser.parse_args(["-m", inp]).model, want)
        for inp in ("x", "t,a", "tpa", ""):
            with self.subTest(inp=inp), \
                 contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit):
                parser.parse_args(["-m", inp])

    def test_both_models_pipeline_and_rotation(self):
        args = trapstel.make_parser().parse_args(["10/5", "-m", "ta", "-r"])
        captured = []

        def pipeline(stages, **kwargs):
            captured.append(stages)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        out = io.BytesIO()
        with patch.object(trapstel, "run_pipeline", side_effect=pipeline):
            trapstel.make_trapstel(10, 5, args, output=out)

        self.assertEqual(out.getvalue(), b"OFF\n0 0 0\n")
        self.assertEqual(len(captured), 3)
        self.assertEqual(captured[0][0][:6],
                         ["polygon", "ant", "10/5", "-s", "1", "-r"])
        self.assertEqual(captured[0][1],
                         ["off_color", "-f", "red"])
        self.assertEqual(captured[1][0][:3], ["pol_recip", "-r", "0.70710678118654757"])
        self.assertEqual(captured[1][1],
                         ["off_trans", "-R", "0,0,90.00000000000000000"])
        self.assertEqual(captured[1][2], ["off_color", "-f", "blue"])
        self.assertEqual(captured[2][0], ["off_util", "tmp1.off", "tmp2.off"])
        self.assertEqual(captured[2][1], ["off_trans", "-R", "90,0,0"])
        self.assertEqual(captured[2][2],
                         ["off_color", "-e", "lightgray", "-v", "gold"])

    def test_trapezohedron_only_skips_reciprocal(self):
        args = trapstel.make_parser().parse_args([])
        captured = []

        def pipeline(stages, **kwargs):
            captured.append(stages)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        with patch.object(trapstel, "run_pipeline", side_effect=pipeline):
            trapstel.make_trapstel(6, 1, args, output=io.BytesIO())
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[-1][0], ["off_util", "tmp1.off"])

    def test_antiprism_only_needs_trapezohedron_first(self):
        args = trapstel.make_parser().parse_args(["-m", "a"])
        captured = []

        def pipeline(stages, **kwargs):
            captured.append(stages)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        with patch.object(trapstel, "run_pipeline", side_effect=pipeline):
            trapstel.make_trapstel(6, 1, args, output=io.BytesIO())
        self.assertEqual(len(captured), 3)
        self.assertEqual(captured[1][0][0], "pol_recip")
        self.assertEqual(captured[-1][0], ["off_util", "tmp2.off"])

    def test_rotate_always_includes_reciprocal(self):
        # -r adds the antiprism to the output selection, without replacing t.
        cases = [
            ([], ["tmp1.off"], 2, None),
            (["-r"], ["tmp1.off", "tmp2.off"], 3, 30.0),
            (["-m", "t", "-r"], ["tmp1.off", "tmp2.off"], 3, 30.0),
            (["-m", "a", "-r"], ["tmp2.off"], 3, 30.0),
            (["-m", "ta", "-r"], ["tmp1.off", "tmp2.off"], 3, 30.0),
        ]
        for arguments, filenames, pipeline_count, rotation in cases:
            with self.subTest(arguments=arguments):
                args = trapstel.make_parser().parse_args(arguments)
                captured = []

                def pipeline(stages, **kwargs):
                    captured.append(stages)
                    kwargs["stdout"].write(b"OFF\n0 0 0\n")

                with patch.object(trapstel, "run_pipeline", side_effect=pipeline):
                    trapstel.make_trapstel(6, 1, args, output=io.BytesIO())

                self.assertEqual(len(captured), pipeline_count)
                self.assertEqual(captured[-1][0], ["off_util", *filenames])
                if rotation is not None:
                    self.assertEqual(captured[1][1], [
                        "off_trans", "-R", f"0,0,{rotation:.17f}",
                    ])
                # Do not mutate the parsed -m selection for callers.
                self.assertEqual(args.model, "t" if not arguments or
                                 arguments[0] == "-r" else arguments[1])

    def test_errors_and_version(self):
        script = Path(trapstel.__file__)
        version = subprocess.run([sys.executable, script, "--version"],
                                 capture_output=True, text=True)
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("0.9.0b1", version.stdout)
        for value in ("5/5", "5/15", "1/2", "abc"):
            with self.subTest(value=value):
                result = subprocess.run([sys.executable, script, value],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("trapstel:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as temp:
            env["PATH"] = temp
            result = subprocess.run([sys.executable, script, "6"],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("required program 'polygon'", result.stderr)


if __name__ == "__main__":
    unittest.main()
