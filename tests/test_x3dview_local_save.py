#!/usr/bin/env python3
"""Regression tests for X3Dview's optional local copy."""

import contextlib
import gzip
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit
from urllib.request import urlopen

import x3dview

X3D_TEXT = b'#X3D V3.3 utf8\nTransform { }\n'
VRML2 = b'#VRML V2.0 utf8\nTransform { }\n'
X3D_XML = b'<?xml version="1.0"?><X3D version="3.3"></X3D>\n'


@contextlib.contextmanager
def working_directory(folder):
    previous = Path.cwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(previous)


class LocalSaveTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.inputs = self.root / 'inputs'
        self.output = self.root / 'output'
        self.inputs.mkdir()
        self.output.mkdir()
        self.fetches = []

    def fetch_in_browser(self, page_url):
        parameters = parse_qs(urlsplit(page_url).query)
        model_url = parameters['url'][0]
        parts = urlsplit(model_url)
        safe_url = urlunsplit((parts.scheme, parts.netloc,
                               quote(parts.path), parts.query, parts.fragment))
        with urlopen(safe_url, timeout=5) as reply:
            self.fetches.append((urlsplit(safe_url).path, reply.read()))

    def test_flags_visible_in_help(self):
        helptext = x3dview.make_parser().format_help()
        self.assertIn('-s, --save-local-copy', helptext)
        self.assertNotIn('--writeout', helptext)

    def test_saved_data_matches_browser_bytes_and_numbering(self):
        source = self.inputs / 'my model.x3dv'
        source.write_bytes(X3D_TEXT)
        diagnostics = io.StringIO()
        with (working_directory(self.output),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser),
              contextlib.redirect_stderr(diagnostics)):
            self.assertEqual(x3dview.main([str(source), '-s', '-timeout', '5']), 0)
            self.assertEqual(x3dview.main([str(source), '--save-local-copy',
                                            '-timeout', '5']), 0)
        self.assertEqual([name for name, _ in self.fetches],
                         ['/my%20model_copy.x3dv'] * 2)
        self.assertEqual([data for _, data in self.fetches],
                         [X3D_TEXT, X3D_TEXT])
        self.assertEqual((self.output / 'my model_copy.x3dv').read_bytes(),
                         X3D_TEXT)
        self.assertEqual((self.output / 'my model_copy_2.x3dv').read_bytes(),
                         X3D_TEXT)
        self.assertEqual(source.read_bytes(), X3D_TEXT)
        self.assertIn('saved local copy:', diagnostics.getvalue())

    def test_no_copy_by_default(self):
        source = self.inputs / 'foo.wrl'
        source.write_bytes(VRML2)
        with (working_directory(self.output),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser)):
            self.assertEqual(x3dview.main([str(source), '-timeout', '5']), 0)
        self.assertEqual(self.fetches[0][1], VRML2)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_stdin_compressed_x3dvz_saves_decompressed_x3dv(self):
        import sys
        with (working_directory(self.output),
              mock.patch.object(sys, 'stdin',
                                io.TextIOWrapper(io.BytesIO(gzip.compress(X3D_TEXT)))),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(x3dview.main(['-s', '-timeout', '5']), 0)
        self.assertEqual(self.fetches[0][1], X3D_TEXT)
        self.assertEqual((self.output / 'stdin_copy.x3dv').read_bytes(), X3D_TEXT)

    def test_xml_x3d_preserves_extension(self):
        source = self.inputs / 'scene.x3dz'
        source.write_bytes(gzip.compress(X3D_XML))
        with (working_directory(self.output),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(x3dview.main([str(source), '-s', '-timeout', '5']), 0)
        self.assertEqual((self.output / 'scene_copy.x3d').read_bytes(), X3D_XML)
        self.assertEqual(self.fetches[0][1], X3D_XML)

    def test_vrml1_conversion_is_saved_not_original(self):
        old = b'#VRML V1.0 ascii\nSeparator {}\n'
        source = self.inputs / 'old.wrl'
        source.write_bytes(old)
        with (working_directory(self.output),
              mock.patch.object(x3dview, 'convert_vrml1', return_value=VRML2),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(x3dview.main([str(source), '-s', '-timeout', '5']), 0)
        self.assertEqual((self.output / 'old_copy.wrl').read_bytes(), VRML2)
        self.assertEqual(self.fetches[0][1], VRML2)
        self.assertEqual(source.read_bytes(), old)

    def test_saved_copy_survives_browser_failure(self):
        source = self.inputs / 'failed.x3dv'
        source.write_bytes(X3D_TEXT)
        with (working_directory(self.output),
              mock.patch.object(x3dview, 'open_browser',
                                side_effect=RuntimeError('browser failed')),
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit) as raised:
                x3dview.main([str(source), '-s', '-timeout', '5'])
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual((self.output / 'failed_copy.x3dv').read_bytes(), X3D_TEXT)

    def test_obsolete_writeout_options_are_rejected(self):
        parser = x3dview.make_parser()
        for option in ('-w', '--writeout'):
            with self.subTest(option=option):
                with (contextlib.redirect_stderr(io.StringIO()),
                      self.assertRaises(SystemExit) as raised):
                    parser.parse_args(['model.wrl', option])
                self.assertEqual(raised.exception.code, 2)

    def test_viewer_always_opens_with_or_without_save(self):
        import sys
        source = self.inputs / 'pipe.wrl'
        source.write_bytes(VRML2)
        stdout = mock.Mock(buffer=io.BytesIO())
        with (working_directory(self.output),
              mock.patch.object(sys, 'stdout', stdout),
              mock.patch.object(x3dview, 'open_browser', self.fetch_in_browser),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(x3dview.main([str(source), '-timeout', '5']), 0)
            self.assertEqual(x3dview.main([str(source), '-s', '-timeout', '5']), 0)
        self.assertEqual(len(self.fetches), 2)
        self.assertEqual([data for _, data in self.fetches], [VRML2, VRML2])
        self.assertEqual(stdout.buffer.getvalue(), b'')
        self.assertEqual((self.output / 'pipe_copy.wrl').read_bytes(), VRML2)

    def test_invalid_gzip_does_not_leave_local_copy(self):
        source = self.inputs / 'corrupt.x3dvz'
        source.write_bytes(b'\x1f\x8bnot actually gzip')
        with (working_directory(self.output),
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit) as raised:
                x3dview.main([str(source), '-s'])
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
