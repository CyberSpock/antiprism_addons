#!/usr/bin/env python3
"""Final-pass tests for shared temporary directories and CLI contracts."""

import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import anti_common
import offview
import x3dview

TEMP_PROGRAMS = (
    "color_wheel", "embeddip", "inscribe", "offview", "pyr2trap",
    "rotyz", "trapstel", "x3dview",
)


class KeepTempTests(unittest.TestCase):
    def test_normal_cleanup_on_success_and_failure(self):
        paths = []
        with anti_common.temporary_workdir("test-addon-") as directory:
            paths.append(directory)
            (directory / "intermediate.off").write_text("OFF\n")
            self.assertTrue(directory.exists())
        self.assertFalse(paths[0].exists())

        with self.assertRaisesRegex(RuntimeError, "planned failure"):
            with anti_common.temporary_workdir("test-addon-") as directory:
                paths.append(directory)
                raise RuntimeError("planned failure")
        self.assertFalse(paths[1].exists())

    def test_keep_on_success_and_failure(self):
        for fail in (False, True):
            saved = None
            diagnostics = io.StringIO()
            try:
                with contextlib.redirect_stderr(diagnostics):
                    try:
                        with anti_common.temporary_workdir(
                            "test-addon-", keep=True, program="tester"
                        ) as directory:
                            saved = directory
                            (directory / "intermediate.off").write_text("OFF\n")
                            if fail:
                                raise RuntimeError("planned failure")
                    except RuntimeError:
                        if not fail:
                            raise
                self.assertTrue(saved.exists())
                self.assertEqual((saved / "intermediate.off").read_text(), "OFF\n")
                self.assertIn(f"tester: temporary files: {saved}",
                              diagnostics.getvalue())
            finally:
                if saved is not None:
                    shutil.rmtree(saved, ignore_errors=True)

    def test_keep_temp_is_in_all_applicable_help(self):
        root = Path(anti_common.__file__).parent
        for name in TEMP_PROGRAMS:
            with self.subTest(program=name):
                result = subprocess.run(
                    [sys.executable, str(root / f"{name}.py"), "--help"],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--keep-temp", result.stdout)

    def test_x3dview_local_only_privacy_wording(self):
        self.assertIn("does not upload VRML/X3D geometry",
                      " ".join(x3dview.make_parser().format_help().split()))
        self.assertIn("does not upload OFF",
                      " ".join(offview.make_parser().format_help().split()))

    def test_x3dview_failed_viewer_keeps_served_file(self):
        import re
        text = b"#VRML V2.0 utf8\nGroup { children [] }\n"
        stderr = io.StringIO()
        with patch.object(x3dview, "read_input", return_value=text), \
             patch.object(x3dview, "open_browser",
                          side_effect=RuntimeError("test browser failure")), \
             contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                x3dview.main(["--keep-temp", "-timeout", "1"])
        match = re.search(r"x3dview: temporary files: (.+)", stderr.getvalue())
        self.assertIsNotNone(match, stderr.getvalue())
        folder = Path(match.group(1).strip())
        try:
            self.assertTrue((folder / "stdin_copy.wrl").exists())
            self.assertEqual((folder / "stdin_copy.wrl").read_bytes(), text)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_offview_failed_viewer_keeps_served_file(self):
        import re
        data = b"OFF\n1 0 0\n0 0 0\n"
        stderr = io.StringIO()
        with patch.object(offview, "read_off_bytes", return_value=data), \
             patch.object(offview, "preprocess_off", return_value=data), \
             patch.object(offview, "open_browser",
                          side_effect=RuntimeError("test browser failure")), \
             contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit):
                offview.main(["--keep-temp", "-timeout", "1"])
        match = re.search(r"offview: temporary files: (.+)", stderr.getvalue())
        self.assertIsNotNone(match, stderr.getvalue())
        folder = Path(match.group(1).strip())
        try:
            self.assertEqual((folder / "stdin_copy.off").read_bytes(), data)
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
