#!/usr/bin/env python3
"""Tests of pyr2trap's geometry parameters, CLI, and subprocess pipelines."""

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

import pyr2trap
from anti_common import parse_polygon


class Pyr2TrapTest(unittest.TestCase):
    def test_notation(self):
        for s, expected in {
            "6": (6, 1), "5/4": (5, 4), "5/6": (5, 6),
            "5/9": (5, 9), "10/5": (10, 5), "10/4": (10, 4),
        }.items():
            with self.subTest(s=s):
                self.assertEqual(parse_polygon(s), expected)
        with self.assertRaises(ValueError):
            parse_polygon("5/5")

    def test_adrian_formula(self):
        angle, height = pyr2trap.antiprism_height(6, 1, 1.0)
        self.assertAlmostEqual(angle, 30)
        self.assertAlmostEqual(height, 1 / math.cos(math.pi / 6) - 1)
        self.assertAlmostEqual(
            pyr2trap.antiprism_height(6, 1, 2.5)[1],
            2.5 * height,
        )

    def test_singular_input(self):
        with self.assertRaisesRegex(ValueError, "undefined antiprism height"):
            pyr2trap.antiprism_height(10, 5, 1)

    def test_argv_and_standardized_help(self):
        parser = pyr2trap.make_parser()
        args = parser.parse_args(["5/4", "-p", "2", "-m", "pa",
                                  "--pyramid-color", "gold",
                                  "--antiprism-color", "purple",
                                  "--edge-color", "lightgray",
                                  "--vertex-color", "red"])
        self.assertEqual(args.polygon_fraction, "5/4")
        self.assertEqual(args.pyramid_height, 2)
        self.assertEqual(args.model, "pa")
        self.assertEqual(args.pyramid_color, "gold")
        self.assertEqual(args.antiprism_color, "purple")
        self.assertEqual(args.edge_color, "lightgray")
        self.assertEqual(args.vertex_color, "red")
        helptext = parser.format_help()
        self.assertIn("n[/d]", helptext)
        self.assertIn("n or n/d; d is the step", helptext)
        self.assertIn("(default: pma)", helptext)
        self.assertNotIn("--pyramidHeight", helptext)

    def test_default_model_is_three_components(self):
        self.assertEqual(pyr2trap.make_parser().parse_args([]).model,
                         "pma")

    def test_compact_selection(self):
        parser = pyr2trap.make_parser()
        for value, normalized in (
            ("pma", "pma"), ("pa", "pa"), ("am", "ma"), ("mm", "m")
        ):
            with self.subTest(value=value):
                self.assertEqual(parser.parse_args(["-m", value]).model,
                                 normalized)
        for value in ("", "x", "pmae", "p,m,a"):
            with self.subTest(invalid=value), \
                 contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit):
                parser.parse_args(["-m", value])

    def test_all_pipelines_and_math(self):
        args = pyr2trap.make_parser().parse_args(["6"])
        captured = []

        def pipeline(cmds, **kwargs):
            captured.append(("pipeline", cmds))
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        def command(cmd, **kwargs):
            captured.append(("command", cmd))
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        with patch.object(pyr2trap, "run_pipeline", side_effect=pipeline), \
             patch.object(pyr2trap, "run_command", side_effect=command):
            result = io.BytesIO()
            pyr2trap.make_trapezohedron(6, 1, args, output=result)
        self.assertEqual(result.getvalue(), b"OFF\n0 0 0\n")
        self.assertEqual([x[0] for x in captured],
                         ["pipeline", "command", "pipeline", "pipeline"])
        steps = captured[0][1]
        self.assertEqual(steps[0][:3], ["polygon", "pyr", "6/1"])
        self.assertEqual(steps[1][0], "off_trans")
        self.assertIn("0,0,15.00000000000000000", steps[1])
        self.assertEqual(steps[2], ["off_color", "-f", "red"])
        self.assertEqual(captured[1][1][:4],
                         ["off_trans", "-R", "0,0,30.00000000000000000", "-M"])
        self.assertEqual(captured[2][1][0][:3], ["polygon", "ant", "6/1"])
        self.assertEqual(captured[3][1][0],
                         ["off_util", "tmp1.off", "tmp2.off", "tmp3.off"])
        self.assertEqual(captured[3][1][1], ["off_trans", "-R", "90,0,0"])
        self.assertEqual(captured[3][1][2],
                         ["off_color", "-e", "lightgray", "-v", "gold"])

    def test_selected_mirror_makes_prerequisite_but_combines_only_mirror(self):
        args = pyr2trap.make_parser().parse_args(["-m", "m"])
        commands = []

        def pipeline(steps, **kwargs):
            commands.append(steps)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        def command(step, **kwargs):
            commands.append(step)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        with patch.object(pyr2trap, "run_pipeline", side_effect=pipeline), \
             patch.object(pyr2trap, "run_command", side_effect=command):
            pyr2trap.make_trapezohedron(6, 1, args, output=io.BytesIO())
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[-1][0], ["off_util", "tmp2.off"])

    def test_antiprism_only_skips_two_pyramids(self):
        args = pyr2trap.make_parser().parse_args(["-m", "a"])
        commands = []

        def pipeline(steps, **kwargs):
            commands.append(steps)
            kwargs["stdout"].write(b"OFF\n0 0 0\n")

        with patch.object(pyr2trap, "run_pipeline", side_effect=pipeline), \
             patch.object(pyr2trap, "run_command") as unused:
            pyr2trap.make_trapezohedron(6, 1, args, output=io.BytesIO())
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][0][:2], ["polygon", "ant"])
        self.assertEqual(commands[-1][0], ["off_util", "tmp3.off"])
        unused.assert_not_called()

    def test_cli_version_and_missing_program_error(self):
        executable = Path(pyr2trap.__file__)
        result = subprocess.run([sys.executable, executable, "--version"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.9.0b1", result.stdout)
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as tmp:
            env["PATH"] = tmp
            result = subprocess.run([sys.executable, executable, "6"],
                                    capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("required program 'polygon'", result.stderr)

    def test_invalid_input_fails_without_traceback(self):
        executable = Path(pyr2trap.__file__)
        for input_str in ["5/5", "10/5", "1/2", "not-a-number"]:
            with self.subTest(input_str=input_str):
                result = subprocess.run([sys.executable, executable, input_str],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("pyr2trap:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
