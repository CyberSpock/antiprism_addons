#!/usr/bin/env python3
"""Focused local-copy tests without Antiprism or Stella installed."""

import contextlib
import io
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit
from urllib.request import urlopen

import anti_common
import offview
import stella

CUBE = b"OFF\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n"
COLORED = CUBE + b"# Antiprism color records\n"
STELLA_BYTES = CUBE


@contextlib.contextmanager
def working_directory(folder):
    before = Path.cwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


def safe_model_url(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path),
                       parts.query, parts.fragment))


class LocalCopyTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.source_dir = self.folder / "sources"
        self.save_dir = self.folder / "output"
        self.source_dir.mkdir()
        self.save_dir.mkdir()

    def test_numbering_preserves_all_prior_copies(self):
        staged = self.source_dir / "my model_copy.off"
        staged.write_bytes(b"first")
        filenames = []
        for content in [b"first", b"second", b"third"]:
            staged.write_bytes(content)
            result = anti_common.save_local_copy(staged, directory=self.save_dir)
            filenames.append(result.name)
        self.assertEqual(filenames, ["my model_copy.off",
                                     "my model_copy_2.off",
                                     "my model_copy_3.off"])
        self.assertEqual([(self.save_dir / f).read_bytes() for f in filenames],
                         [b"first", b"second", b"third"])
        self.assertEqual(staged.read_bytes(), b"third")

    def test_existing_directory_is_not_overwritten(self):
        staged = self.source_dir / 'cube_copy.off'
        staged.write_bytes(b'OFF')
        (self.save_dir / staged.name).mkdir()
        result = anti_common.save_local_copy(staged, directory=self.save_dir)
        self.assertEqual(result.name, 'cube_copy_2.off')
        self.assertTrue((self.save_dir / 'cube_copy.off').is_dir())

    def test_offview_saves_preprocessed_bytes_and_uses_cwd(self):
        source = self.source_dir / "a model.off"
        source.write_bytes(CUBE)
        displayed = CUBE + b"# after preprocessing\n"
        fetched = []

        def fake_browser(url):
            model_url = parse_qs(urlsplit(url).query)['url'][0]
            with urlopen(safe_model_url(model_url), timeout=5) as response:
                fetched.append(response.read())

        stderr = io.StringIO()
        with (working_directory(self.save_dir),
              mock.patch.object(offview, 'run_off_tool', return_value=displayed),
              mock.patch.object(offview, 'open_browser', side_effect=fake_browser),
              contextlib.redirect_stderr(stderr)):
            self.assertEqual(offview.main([str(source), '-s', '-timeout', '5']), 0)
            self.assertEqual(offview.main([str(source), '--save-local-copy',
                                           '-timeout', '5']), 0)
        self.assertEqual(fetched, [displayed, displayed])
        self.assertEqual(source.read_bytes(), CUBE)
        self.assertEqual((self.save_dir / 'a model_copy.off').read_bytes(), displayed)
        self.assertEqual((self.save_dir / 'a model_copy_2.off').read_bytes(), displayed)
        self.assertIn('a model_copy.off', stderr.getvalue())
        self.assertIn('a model_copy_2.off', stderr.getvalue())

    def test_offview_stdin_copies_without_requiring_input_filename(self):
        displayed = CUBE + b'# modified\n'
        def fake_browser(url):
            model_url = parse_qs(urlsplit(url).query)['url'][0]
            with urlopen(safe_model_url(model_url), timeout=5) as response:
                self.assertEqual(response.read(), displayed)
        with (working_directory(self.save_dir),
              mock.patch.object(sys, 'stdin', io.TextIOWrapper(io.BytesIO(CUBE))),
              mock.patch.object(offview, 'run_off_tool', return_value=displayed),
              mock.patch.object(offview, 'open_browser', side_effect=fake_browser),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(offview.main(['-s', '-timeout', '5']), 0)
        self.assertEqual((self.save_dir / 'stdin_copy.off').read_bytes(), displayed)

    def test_offview_no_save_by_default(self):
        source = self.source_dir / "cube.off"
        source.write_bytes(CUBE)
        def fake_browser(url):
            model_url = parse_qs(urlsplit(url).query)['url'][0]
            with urlopen(safe_model_url(model_url), timeout=5) as response:
                self.assertEqual(response.read(), CUBE)
        with (working_directory(self.save_dir),
              mock.patch.object(offview, 'run_off_tool', return_value=CUBE),
              mock.patch.object(offview, 'open_browser', side_effect=fake_browser)):
            self.assertEqual(offview.main([str(source), '-timeout', '5']), 0)
        self.assertFalse(list(self.save_dir.glob('*_copy*.off')))

    def test_stella_cygwin_path_translation(self):
        """Cygwin passes a native Windows pathname to the Stella executable."""
        target = r"L:\cygwin64\tmp\model_copy.off"
        with (mock.patch.object(stella, 'is_windows', return_value=False),
              mock.patch.object(stella, 'is_cygwin', return_value=True),
              mock.patch.object(stella.subprocess, 'check_output',
                                return_value=target + "\n") as convert):
            self.assertEqual(stella.to_windows_path('/tmp/model_copy.off'),
                             target)
        convert.assert_called_once_with(
            ['cygpath', '-w', '/tmp/model_copy.off'], text=True)

    def test_stella_preserves_colors_before_stripping_and_numbers_copies(self):
        source = self.source_dir / 'painted model.off'
        source.write_bytes(COLORED)
        exe = self.source_dir / 'stella.anyname'
        exe.write_bytes(b'fake')
        stage = self.folder / 'stella-stage'
        stage.mkdir()
        launched = []

        def filter_for_stella(command, data, **kwargs):
            self.assertEqual(command, ['off_util', '-x', 'ev'])
            self.assertEqual(data, COLORED)
            return STELLA_BYTES

        def capture_launch(command, **kwargs):
            launched.append(Path(command[1]).read_bytes())
            return mock.Mock(returncode=0)

        stderr = io.StringIO()
        with (working_directory(self.save_dir),
              mock.patch.object(stella, 'stella_executable', return_value=str(exe)),
              mock.patch.object(stella.tempfile, 'mkdtemp', return_value=str(stage)),
              mock.patch.object(stella, 'run_filter', side_effect=filter_for_stella),
              # The launch mock needs a local POSIX path to inspect the staged
              # OFF bytes.  Test cygpath conversion separately instead.
              mock.patch.object(stella, 'to_windows_path',
                                side_effect=lambda path: str(path)),
              mock.patch.object(stella.subprocess, 'run', side_effect=capture_launch),
              contextlib.redirect_stderr(stderr)):
            for arg in ('-s', '--save-local-copy'):
                with mock.patch.object(sys, 'argv', ['stella', str(source), arg]):
                    self.assertEqual(stella.main(), 0)

        self.assertEqual(launched, [STELLA_BYTES, STELLA_BYTES])
        self.assertEqual(source.read_bytes(), COLORED)
        self.assertEqual((stage / 'painted model_copy.off').read_bytes(), STELLA_BYTES)
        self.assertEqual((self.save_dir / 'painted model_copy.off').read_bytes(), COLORED)
        self.assertEqual((self.save_dir / 'painted model_copy_2.off').read_bytes(), COLORED)
        self.assertIn('saved local copy:', stderr.getvalue())

    def test_offview_saves_before_browser_failure(self):
        source = self.source_dir / 'failed-browser.off'
        source.write_bytes(CUBE)
        with (working_directory(self.save_dir),
              mock.patch.object(offview, 'run_off_tool', return_value=COLORED),
              mock.patch.object(offview, 'open_browser',
                                side_effect=RuntimeError('browser failed')),
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit) as result:
                offview.main([str(source), '-s', '-timeout', '5'])
        self.assertEqual(result.exception.code, 1)
        self.assertEqual((self.save_dir / 'failed-browser_copy.off').read_bytes(),
                         COLORED)

    def test_stella_saves_before_compatibility_failure(self):
        source = self.source_dir / 'failed-strip.off'
        source.write_bytes(COLORED)
        exe = self.source_dir / 'fake-stella.exe'
        exe.write_bytes(b'fake')
        stage = self.folder / 'failed-stella-stage'
        stage.mkdir()
        with (working_directory(self.save_dir),
              mock.patch.object(stella, 'stella_executable', return_value=str(exe)),
              mock.patch.object(stella.tempfile, 'mkdtemp', return_value=str(stage)),
              mock.patch.object(stella, 'run_filter',
                                side_effect=RuntimeError('strip failed')),
              mock.patch.object(sys, 'argv', ['stella', str(source), '-s']),
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit) as result:
                stella.main()
        self.assertEqual(result.exception.code, 1)
        self.assertEqual((self.save_dir / 'failed-strip_copy.off').read_bytes(),
                         COLORED)

    def test_stella_stdin_without_save(self):
        exe = self.source_dir / 'stella.anyname'
        exe.write_bytes(b'fake')
        stage = self.folder / 'stella-stdin-stage'
        stage.mkdir()
        launched = []
        def capture_launch(command, **kwargs):
            launched.append(Path(command[1]).read_bytes())
        with (working_directory(self.save_dir),
              mock.patch.object(sys, 'stdin', io.TextIOWrapper(io.BytesIO(COLORED))),
              mock.patch.object(stella, 'stella_executable', return_value=str(exe)),
              mock.patch.object(stella.tempfile, 'mkdtemp', return_value=str(stage)),
              mock.patch.object(stella, 'run_filter', return_value=STELLA_BYTES),
              mock.patch.object(stella, 'to_windows_path',
                                side_effect=lambda path: str(path)),
              mock.patch.object(stella.subprocess, 'run', side_effect=capture_launch),
              mock.patch.object(sys, 'argv', ['stella'])):
            self.assertEqual(stella.main(), 0)
        self.assertEqual(launched, [STELLA_BYTES])
        self.assertFalse(list(self.save_dir.glob('*_copy*.off')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
