#!/usr/bin/env python3
"""Tests for rotyz notation, off_query, and end-to-end program flow."""

import io
from contextlib import redirect_stderr
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import rotyz


class RotyzTests(unittest.TestCase):
    def test_element_notation(self):
        self.assertEqual(rotyz.parse_element('e3'), ('e', 3))
        self.assertEqual(rotyz.parse_element('f5'), ('f', 5))
        self.assertEqual(rotyz.parse_element('v123456'), ('v', 123456))
        self.assertEqual(rotyz.parse_element('E03'), ('e', 3))

    def test_reject_malformed_elements(self):
        from argparse import ArgumentTypeError
        for value in ('', 'e', 'e-1', 'e+3', '3e', 'g3', 'f3x', 'e1.0'):
            with self.subTest(value=value):
                with self.assertRaises(ArgumentTypeError):
                    rotyz.parse_element(value)

    def test_cli_interface(self):
        args = rotyz.make_parser().parse_args(
            ['cube', '-y', 'e3', '-z', 'f5', '--verbose'])
        self.assertEqual(args.y_element, ('e', 3))
        self.assertEqual(args.z_element, ('f', 5))
        self.assertTrue(args.verbose)
        help_text = rotyz.make_parser().format_help()
        self.assertIn('-y', help_text)
        self.assertIn('--y-axis', help_text)
        self.assertIn('--z-axis', help_text)
        self.assertIn('vN|eN|fN', help_text)
        self.assertNotIn('--elemtype1', help_text)

    def test_query_output(self):
        output = b'5, 0.75  -0.125  0.5\n'
        self.assertEqual(rotyz.parse_query_output(output, ('f', 5)),
                         ('0.75,-0.125,0.5', (0.75, -0.125, 0.5)))

    def test_wrong_index_and_empty_query_rejected(self):
        for data in (b'', b'3,1 0 0\n'):
            with self.subTest(data=data), self.assertRaisesRegex(
                    ValueError, 'out of range'):
                rotyz.parse_query_output(data, ('e', 15))

    def test_invalid_coordinates_rejected(self):
        for data in (b'5,1 2\n', b'5,nan 0 0\n', b'5,1 q 0\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                rotyz.parse_query_output(data, ('f', 5))

    def test_range_validation_happens_before_off_query(self):
        limits = {'v': 11, 'e': 29, 'f': 19}
        with patch.object(rotyz, 'max_element_indices',
                          return_value=limits) as report, \
             patch.object(rotyz, 'run_command') as query:
            with self.assertRaisesRegex(ValueError, r'valid indices: 0\.\.11'):
                rotyz.validate_element_indices(
                    (('v', 1), ('v', 100)), 'rotyz.off', '/tmp')
            report.assert_called_once_with(
                'rotyz.off', cwd='/tmp', verbose=False)
            query.assert_not_called()

    def test_range_checks_both_types_in_one_report(self):
        limits = {'v': 7, 'e': 11, 'f': 5}
        with patch.object(rotyz, 'max_element_indices',
                          return_value=limits) as report:
            rotyz.validate_element_indices(
                (('v', 7), ('f', 5)), 'rotyz.off', '/tmp')
            report.assert_called_once()
            with self.assertRaisesRegex(ValueError, 'valid indices: 0..5'):
                rotyz.validate_element_indices(
                    (('e', 3), ('f', 6)), 'rotyz.off', '/tmp')

    def test_no_elements_range_error(self):
        with patch.object(rotyz, 'max_element_indices',
                          return_value={'v': 0, 'e': -1, 'f': -1}):
            with self.assertRaisesRegex(ValueError, 'no elements of this type'):
                rotyz.validate_element_indices(
                    (('v', 0), ('f', 0)), 'rotyz.off', '/tmp')

    def test_selected_query_types(self):
        for elem, query in ((('v', 7), 'Vc'), (('e', 3), 'EC'),
                            (('f', 5), 'FC')):
            with self.subTest(elem=elem), patch.object(
                    rotyz, 'run_command',
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout=f'{elem[1]},1 0 0\n'.encode())) as cmd:
                rotyz.get_coord(elem, 'rotyz.off', '/tmp')
                argv = cmd.call_args.args[0]
                self.assertEqual(argv,
                                 ['off_query', '-c', 'C', '-I', str(elem[1]),
                                  query, 'rotyz.off'])

    def test_same_element_rejected_early(self):
        args = rotyz.make_parser().parse_args(
            ['cube', '-y', 'e3', '-z', 'e3'])
        with patch.object(rotyz, 'read_off_file') as reader:
            with self.assertRaisesRegex(ValueError, 'must be different'):
                rotyz.orient_model(args)
        reader.assert_not_called()

    def test_invalid_second_selection_stops_before_queries(self):
        args = rotyz.make_parser().parse_args(
            ['ico', '-y', 'v1', '-z', 'v100', '-v'])

        def staged_path(model, directory, filename, **kwargs):
            return Path(directory) / filename

        with patch.object(rotyz, 'read_off_file',
                          side_effect=staged_path), \
             patch.object(rotyz, 'max_element_indices',
                          return_value={'v': 11, 'e': 30, 'f': 19}) as report, \
             patch.object(rotyz, 'run_command') as query:
            with self.assertRaisesRegex(ValueError, r'valid indices: 0\.\.11'):
                rotyz.orient_model(args, output=io.BytesIO())
            report.assert_called_once()
            query.assert_not_called()

    def test_zero_and_parallel_directions(self):
        for a, b in (((0, 0, 0), (0, 0, 1)),
                     ((1, 0, 0), (2, 0, 0)),
                     ((1, 0, 0), (-2, 0, 0))):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                rotyz.validate_vectors(a, b)
        rotyz.validate_vectors((1, 0, 0), (0, 0, 2))

    def test_verbose_collinear_reports_both_vectors_before_error(self):
        args = rotyz.make_parser().parse_args(
            ['ico', '-y', 'v1', '-z', 'v2', '-v'])
        coords = [
            ('1,0,0', (1.0, 0.0, 0.0)),
            ('-1,0,0', (-1.0, 0.0, 0.0)),
        ]
        def staged_path(model, directory, filename, **kwargs):
            return Path(directory) / filename

        err = io.StringIO()
        with patch.object(rotyz, 'read_off_file', side_effect=staged_path), \
             patch.object(rotyz, 'validate_element_indices'), \
             patch.object(rotyz, 'get_coord', side_effect=coords), \
             patch.object(rotyz, 'run_command') as command, \
             redirect_stderr(err):
            with self.assertRaisesRegex(ValueError, 'collinear directions'):
                rotyz.orient_model(args, output=io.BytesIO())
        self.assertIn('Y v1 (vertex 1): 1,0,0', err.getvalue())
        self.assertIn('Z v2 (vertex 2): -1,0,0', err.getvalue())
        command.assert_not_called()

    def test_full_mocked_pipeline_and_rotation_order(self):
        args = rotyz.make_parser().parse_args(
            ['cube', '-y', 'e3', '-z', 'f5'])
        commands = []

        def command(argv, **kwargs):
            commands.append(list(argv))
            if argv[0] == 'off_query':
                index = argv[4]
                xyz = ('1 0 0' if index == '3' else '0 0 1')
                return subprocess.CompletedProcess(
                    argv, 0, stdout=f'{index},{xyz}\n'.encode()
                )
            kwargs['stdout'].write(b'OFF\n0 0 0\n')
            return subprocess.CompletedProcess(argv, 0)

        def staged_path(model, directory, filename, **kwargs):
            return Path(directory) / filename

        with patch.object(rotyz, 'read_off_file', side_effect=staged_path), \
             patch.object(rotyz, 'validate_element_indices'), \
             patch.object(rotyz, 'run_command', side_effect=command):
            output = io.BytesIO()
            rotyz.orient_model(args, output=output)
        self.assertEqual(output.getvalue(), b'OFF\n0 0 0\n')
        self.assertEqual(commands[0][5], 'EC')
        self.assertEqual(commands[1][5], 'FC')
        self.assertEqual(commands[2], ['off_trans', '-R',
                                       '1,0,0,0,0,1,0,1,0,0,0,1',
                                       'rotyz.off'])

    def test_version(self):
        exe = Path(rotyz.__file__)
        p = subprocess.run([sys.executable, str(exe), '--version'],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn('0.9.0b1', p.stdout)

    @unittest.skipIf(os.name == "nt", "requires POSIX executable fixtures")
    def test_external_programs_end_to_end(self):
        """Test the CLI with stand-in Antiprism executables."""
        exe = Path(rotyz.__file__)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_path = root / 'bin'
            bin_path.mkdir()
            (root / 'my model.off').write_text('OFF\n0 0 0\n')
            tools = {
                'off_util': '''#!/usr/bin/env python3
import sys
if len(sys.argv) > 1:
    sys.stdout.write('OFF\\n0 0 0\\n')
else:
    sys.stdout.buffer.write(sys.stdin.buffer.read())
''',
                'off_query': '''#!/usr/bin/env python3
import sys
import os
from pathlib import Path
if os.environ.get('ROTYZ_ORDER_LOG'):
    with Path(os.environ['ROTYZ_ORDER_LOG']).open('a') as log:
        log.write('off_query\\n')
args=sys.argv
idx=int(args[args.index('-I')+1])
query=args[-2]
if idx>10:
    sys.exit(0)
coords={'Vc': '0 1 0', 'EC': '1 0 0', 'FC': '0 0 1'}
print(f'{idx},{coords[query]}')
''',
                'off_trans': '''#!/usr/bin/env python3
import sys
from pathlib import Path
if len(sys.argv[sys.argv.index('-R')+1].split(',')) != 12:
    sys.exit(2)
sys.stdout.buffer.write(Path(sys.argv[-1]).read_bytes())
''',
                'off_report': '''#!/usr/bin/env python3
import sys
import os
from pathlib import Path
if os.environ.get('ROTYZ_ORDER_LOG'):
    with Path(os.environ['ROTYZ_ORDER_LOG']).open('a') as log:
        log.write('off_report\\n')
assert sys.argv[1:] == ['rotyz.off', '-S', 'G']
print('[general]')
print('num_verts = 8')
print('num_edges = 12')
print('num_faces = 6')
''',
            }
            for name, source in tools.items():
                program = bin_path / name
                program.write_text(source)
                program.chmod(0o755)
            env = os.environ.copy()
            env['PATH'] = f'{bin_path}{os.pathsep}{env["PATH"]}'
            env['ROTYZ_ORDER_LOG'] = str(root / 'order.log')
            def run(*opts, input=None):
                return subprocess.run(
                    [sys.executable, str(exe), *opts],
                    input=input, capture_output=True, env=env,
                )
            # A full source path with a space must survive staging.
            success = run(str(root / 'my model.off'), '-y', 'e3', '-z', 'f5')
            self.assertEqual(success.returncode, 0, success.stderr.decode())
            self.assertEqual(success.stdout, b'OFF\n0 0 0\n')
            self.assertEqual((root / 'order.log').read_text().splitlines(),
                             ['off_report', 'off_query', 'off_query'])
            for input_args in [
                    ('cube', '-y', 'e3', '-z', 'f5'),
                    ('-', '-y', 'e3', '-z', 'f5')]:
                with self.subTest(args=input_args):
                    outcome = run(*input_args, input=b'OFF\n0 0 0\n'
                                  if input_args[0] == '-' else None)
                    self.assertEqual(outcome.returncode, 0,
                                     outcome.stderr.decode())
                    self.assertEqual(outcome.stdout, b'OFF\n0 0 0\n')
            (root / 'order.log').write_text('')
            missing = run('cube', '-y', 'e90', '-z', 'f5')
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(b'out of range', missing.stderr)
            self.assertIn(b'valid indices: 0..11', missing.stderr)
            self.assertEqual(missing.stdout, b'')
            self.assertEqual((root / 'order.log').read_text().splitlines(),
                             ['off_report'])
            duplicate = run('cube', '-y', 'v1', '-z', 'v1')
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn(b'must be different', duplicate.stderr)


if __name__ == '__main__':
    unittest.main()
