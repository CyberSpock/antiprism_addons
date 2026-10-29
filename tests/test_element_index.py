#!/usr/bin/env python3
"""Regression tests for Antiprism off_report element index limits."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import anti_common


REPORT = b'''[general]\nnum_verts = 8\nnum_faces = 6\nnum_edges = 12\nvertex_centroid = (0 0 0)\nvolume_centroid = (0 0 0)\n'''


class ElementIndexTest(unittest.TestCase):
    def test_cube_maximum_indices(self):
        with patch.object(anti_common, "run_command", return_value=
                          subprocess.CompletedProcess([], 0, stdout=REPORT)) as run:
            self.assertEqual(anti_common.max_element_index("cube", "v"), 7)
            self.assertEqual(anti_common.max_element_index("cube", "e"), 11)
            self.assertEqual(anti_common.max_element_index("cube", "f"), 5)
            self.assertEqual(run.call_args.args[0],
                             ["off_report", "cube", "-S", "G"])

    def test_all_limits_in_one_report(self):
        with patch.object(anti_common, 'run_command', return_value=
                          subprocess.CompletedProcess([], 0, stdout=REPORT)) as run:
            limits = anti_common.max_element_indices('staged.off', cwd='/tmp')
            self.assertEqual(limits, {'v': 7, 'e': 11, 'f': 5})
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0],
                             ['off_report', 'staged.off', '-S', 'G'])
            self.assertEqual(run.call_args.kwargs['cwd'], '/tmp')

    def test_uppercase_and_cwd(self):
        with patch.object(anti_common, "run_command", return_value=
                          subprocess.CompletedProcess([], 0, stdout=REPORT)) as run:
            self.assertEqual(anti_common.max_element_index("staged.off", "V",
                                                             cwd="/tmp/models"), 7)
            self.assertEqual(run.call_args.kwargs["cwd"], "/tmp/models")

    def test_empty_element_lists(self):
        report = b"[general]\nnum_verts = 1\nnum_edges = 0\nnum_faces = 0\n"
        with patch.object(anti_common, "run_command", return_value=
                          subprocess.CompletedProcess([], 0, stdout=report)):
            self.assertEqual(anti_common.max_element_index("point.off", "v"), 0)
            self.assertEqual(anti_common.max_element_index("point.off", "e"), -1)
            self.assertEqual(anti_common.max_element_index("point.off", "f"), -1)

    def test_bad_element_type_rejected_without_running(self):
        with patch.object(anti_common, "run_command") as run:
            with self.assertRaisesRegex(ValueError, "v, e or f"):
                anti_common.max_element_index("cube", "x")
            run.assert_not_called()

    def test_invalid_or_missing_count(self):
        for data in (b"[general]\nnum_edges = nonsense\n",
                     b"[general]\nnum_faces = 6\n"):
            with self.subTest(data=data), patch.object(
                anti_common, "run_command", return_value=
                    subprocess.CompletedProcess([], 0, stdout=data)):
                with self.assertRaises(anti_common.CommandError):
                    anti_common.max_element_index("cube", "e")

    @unittest.skipIf(os.name == "nt", "requires POSIX test executable")
    def test_real_subprocess_with_stand_in_report(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            executable = root / "off_report"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "assert sys.argv[1:] == ['cube', '-S', 'G']\n"
                "print('[general]\\nnum_verts = 8\\nnum_edges = 12\\nnum_faces = 6')\n"
            )
            executable.chmod(0o755)
            path = os.environ.get("PATH", "")
            with patch.dict(os.environ, {"PATH": f"{root}{os.pathsep}{path}"}):
                self.assertEqual(anti_common.max_element_index("cube", "f"), 5)


if __name__ == "__main__":
    unittest.main()
