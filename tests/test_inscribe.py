#!/usr/bin/env python3
"""Regression tests for modern Antiprism Addons inscribe.py."""

import argparse
from contextlib import redirect_stderr
import io
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import inscribe


class InscribeTests(unittest.TestCase):
    def test_parse_element(self):
        self.assertEqual(inscribe.parse_element('v0'), ('v', 0))
        self.assertEqual(inscribe.parse_element('E17'), ('e', 17))
        self.assertEqual(inscribe.parse_element('f0005'), ('f', 5))

    def test_bad_elements(self):
        for value in ('', 'v', 'v-1', 'v+2', 'v 2', 'a4', '9e', 'f1x', 'e1.5'):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    inscribe.parse_element(value)

    def test_parser_and_version(self):
        args = inscribe.make_parser().parse_args(
            ['octahedron', 'icosahedron', '-a', 'v0', '-b', 'e0', '-v'])
        self.assertEqual(args.first_element, ('v', 0))
        self.assertEqual(args.second_element, ('e', 0))
        self.assertTrue(args.verbose)
        help_text = inscribe.make_parser().format_help()
        self.assertIn('--first-element', help_text)
        self.assertIn('--second-element', help_text)
        self.assertNotIn('--elemtype1', help_text)
        self.assertNotIn('--elemnum1', help_text)
        self.assertNotIn('-n ELEMNUM1', help_text)

    def test_radius_output_valid(self):
        self.assertAlmostEqual(inscribe.parse_radius_output(
            b'0,0.7071067811865475\n', ('e', 0)), math.sqrt(0.5))
        self.assertEqual(inscribe.parse_radius_output(
            b'3,0\n', ('v', 3)), 0.0)

    def test_invalid_query_response(self):
        for data in (b'', b'3,1\n', b'0,not-a-number\n', b'0,nan\n',
                     b'0,inf\n', b'0,-1\n', b'0,1\n0,1\n', b'0 1\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                inscribe.parse_radius_output(data, ('e', 0))

    def test_query_command_names(self):
        for element, query in ((('v', 0), 'Vd'), (('e', 3), 'Ed'),
                               (('f', 5), 'Fd')):
            with self.subTest(element=element), patch.object(
                inscribe, 'run_command', return_value=subprocess.CompletedProcess(
                    [], 0, stdout=f'{element[1]},1.5\n'.encode())) as cmd:
                self.assertEqual(inscribe.get_radius(
                    element, 'model.off', '/tmp'), 1.5)
                cmd.assert_called_once_with(
                    ['off_query', '-c', 'C', '-I', str(element[1]), query,
                     'model.off'], cwd='/tmp', stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, verbose=False)

    def test_preflight_limit(self):
        with patch.object(inscribe, 'max_element_index', return_value=7) as report:
            inscribe.check_element_index(('v', 7), 'm.off', '/tmp')
            report.assert_called_once_with('m.off', 'v', cwd='/tmp',
                                           verbose=False)
            with self.assertRaisesRegex(ValueError, 'valid indices: 0..7'):
                inscribe.check_element_index(('v', 8), 'm.off', '/tmp')
        with patch.object(inscribe, 'max_element_index', return_value=-1):
            with self.assertRaisesRegex(ValueError, 'no elements of this type'):
                inscribe.check_element_index(('f', 0), 'm.off', '/tmp')

    @staticmethod
    def fake_reader(model, work_dir, filename, **kwargs):
        return Path(work_dir) / filename

    def test_preflight_before_any_query(self):
        args = inscribe.make_parser().parse_args(
            ['octahedron', 'icosahedron', '-a', 'v1', '-b', 'e100'])
        with patch.object(inscribe, 'read_off_file', side_effect=self.fake_reader), \
             patch.object(inscribe, 'max_element_index',
                          side_effect=[5, 29]) as report, \
             patch.object(inscribe, 'run_command') as cmd, \
             patch.object(inscribe, 'run_pipeline') as pipe:
            with self.assertRaisesRegex(ValueError, '0..29'):
                inscribe.inscribe_models(args, output=io.BytesIO())
            self.assertEqual(report.call_count, 2)
            cmd.assert_not_called()
            pipe.assert_not_called()

    def test_same_element_allowed_for_two_models(self):
        args = inscribe.make_parser().parse_args(
            ['cube', 'cube', '-a', 'v0', '-b', 'v0'])
        with patch.object(inscribe, 'read_off_file', side_effect=self.fake_reader), \
             patch.object(inscribe, 'max_element_index', return_value=7), \
             patch.object(inscribe, 'run_command', return_value=
                          subprocess.CompletedProcess([], 0, stdout=b'0,1\n')), \
             patch.object(inscribe, 'run_pipeline') as pipeline:
            inscribe.inscribe_models(args, output=io.BytesIO())
            pipeline.assert_called_once()

    def test_scale_and_pipeline_order(self):
        args = inscribe.make_parser().parse_args(
            ['octahedron', 'icosahedron', '-a', 'v0', '-b', 'e0'])
        calls = []
        def query(argv, **kwargs):
            calls.append(('query', tuple(argv)))
            out = b'0,2.0\n' if argv[-1] == 'inscribe1.off' else b'0,0.5\n'
            return subprocess.CompletedProcess(argv, 0, stdout=out)
        def report(model, kind, **kwargs):
            calls.append(('report', model, kind))
            return 9
        def pipeline(commands, **kwargs):
            calls.append(('pipeline', commands))
            self.assertEqual(commands, [
                ['off_trans', '-S', '4', 'inscribe2.off'],
                ['off_util', '-', 'inscribe1.off']])
            self.assertIsInstance(kwargs['cwd'], Path)
            self.assertIs(kwargs['stdout'], output)
        output = io.BytesIO()
        with patch.object(inscribe, 'read_off_file', side_effect=self.fake_reader), \
             patch.object(inscribe, 'max_element_index', side_effect=report), \
             patch.object(inscribe, 'run_command', side_effect=query), \
             patch.object(inscribe, 'run_pipeline', side_effect=pipeline):
            inscribe.inscribe_models(args, output=output)
        self.assertEqual([c[0] for c in calls],
                         ['report', 'report', 'query', 'query', 'pipeline'])
        self.assertEqual(calls[2][1][5], 'Vd')
        self.assertEqual(calls[3][1][5], 'Ed')

    def test_zero_radius_rejected(self):
        args = inscribe.make_parser().parse_args(
            ['cube', 'cube', '-a', 'v0', '-b', 'e0'])
        for r1, r2 in ((b'0,0\n', b'0,1\n'),
                       (b'0,1\n', b'0,0\n')):
            with self.subTest(r1=r1, r2=r2), \
                 patch.object(inscribe, 'read_off_file',
                              side_effect=self.fake_reader), \
                 patch.object(inscribe, 'max_element_index', return_value=9), \
                 patch.object(inscribe, 'run_command', side_effect=[
                     subprocess.CompletedProcess([], 0, stdout=r1),
                     subprocess.CompletedProcess([], 0, stdout=r2)]), \
                 patch.object(inscribe, 'run_pipeline') as pipeline:
                with self.assertRaisesRegex(ValueError, 'radius is zero'):
                    inscribe.inscribe_models(args, output=io.BytesIO())
                pipeline.assert_not_called()

    def test_verbose_calculations(self):
        args = inscribe.make_parser().parse_args(
            ['cube', 'cube', '-a', 'f0', '-b', 'v1', '-v'])
        err = io.StringIO()
        with patch.object(inscribe, 'read_off_file', side_effect=self.fake_reader), \
             patch.object(inscribe, 'max_element_index', return_value=9), \
             patch.object(inscribe, 'run_command', side_effect=[
                 subprocess.CompletedProcess([], 0, stdout=b'0,2.5\n'),
                 subprocess.CompletedProcess([], 0, stdout=b'1,5\n')]), \
             patch.object(inscribe, 'run_pipeline'), redirect_stderr(err):
            inscribe.inscribe_models(args, output=io.BytesIO())
        self.assertIn('model 1 f0 (face 0): 2.5', err.getvalue())
        self.assertIn('model 2 v1 (vertex 1): 5', err.getvalue())
        self.assertIn('model 2 scale factor: 0.5', err.getvalue())

    def test_cli_version(self):
        result = subprocess.run([sys.executable, str(Path(inscribe.__file__)),
                                 '--version'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'inscribe.py 0.9.0b1')

    def test_real_subprocesses_with_stand_ins(self):
        if os.name == 'nt':
            self.skipTest('POSIX executable fixture')
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            tools = root / 'tools'
            tools.mkdir()
            def fake_tool(name, content):
                path = tools / name
                path.write_text('#!/usr/bin/env python3\n' + content)
                path.chmod(0o755)
            fake_tool('off_util', '''import sys
if len(sys.argv) == 1:
    sys.stdout.buffer.write(sys.stdin.buffer.read())
elif sys.argv[1] == '-':
    data = sys.stdin.buffer.read()
    with open(sys.argv[2], 'rb') as src:
        sys.stdout.buffer.write(data + src.read())
else:
    sys.stdout.buffer.write(b'OFF\\n1 0 0\\n0 0 0\\n')
''')
            fake_tool('off_report', '''import sys
print('[general]')
print('num_verts = 8')
print('num_edges = 12')
print('num_faces = 6')
''')
            fake_tool('off_query', '''import sys
assert sys.argv[1:4] == ['-c', 'C', '-I']
idx = int(sys.argv[4])
assert sys.argv[5] in ('Vd', 'Ed', 'Fd')
value = '2' if sys.argv[-1] == 'inscribe1.off' else '0.5'
print(f'{idx},{value}')
''')
            fake_tool('off_trans', '''import sys
assert sys.argv[1:4] == ['-S', '4', 'inscribe2.off']
with open(sys.argv[3], 'rb') as src:
    sys.stdout.buffer.write(src.read())
''')
            env = dict(os.environ)
            env['PATH'] = str(tools) + os.pathsep + env.get('PATH', '')
            run = subprocess.run(
                [sys.executable, str(Path(inscribe.__file__)),
                 'octahedron', 'icosahedron', '-a', 'v0', '-b', 'e0'],
                cwd=root, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            self.assertEqual(run.stdout,
                             b'OFF\n1 0 0\n0 0 0\nOFF\n1 0 0\n0 0 0\n')

            # File names with spaces must be handled by Python file I/O,
            # not interpolated into Cygwin command-line strings.
            first_model = root / 'first model.off'
            second_model = root / 'second model.off'
            for filename in (first_model, second_model):
                filename.write_bytes(b'OFF\n1 0 0\n0 0 0\n')
            real_files = subprocess.run(
                [sys.executable, str(Path(inscribe.__file__)),
                 str(first_model), str(second_model),
                 '-a', 'f0', '-b', 'v0'],
                cwd=root, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            self.assertEqual(real_files.returncode, 0,
                             real_files.stderr.decode())
            self.assertEqual(real_files.stdout, run.stdout)


if __name__ == '__main__':
    unittest.main()
