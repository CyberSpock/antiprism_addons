#!/usr/bin/env python3
"""Regression tests for modern Antiprism Addons kaufman.py."""

import io
import contextlib
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import kaufman


class KaufmanTests(unittest.TestCase):
    def test_parser(self):
        p = kaufman.make_parser()
        args = p.parse_args(['cube', '3', '-E', 'red', '-V', 'gold'])
        self.assertEqual((args.off_file, args.n), ('cube', 3))
        self.assertEqual(args.edge_color, 'red')
        self.assertEqual(args.vertex_color, 'gold')
        self.assertFalse(args.conway)
        self.assertEqual(p.parse_args(['0']).off_file, '-')
        self.assertEqual(p.parse_args(['-c', 'cube', '2']).n, 2)
        self.assertTrue(p.parse_args(['cube', '2', '-c']).conway)
        self.assertFalse(p.parse_args(['cube', '1']).keep_temp)
        self.assertTrue(p.parse_args(['cube', '1', '--keep-temp']).keep_temp)

    def test_nonnegative_integer(self):
        for value in ('-1', 'oops', '1.2'):
            with self.subTest(value=value), self.assertRaises(SystemExit), \
                 contextlib.redirect_stderr(io.StringIO()):
                kaufman.make_parser().parse_args(['cube', value])
        self.assertEqual(kaufman.nonnegative_integer('0'), 0)
        self.assertEqual(kaufman.nonnegative_integer('123'), 123)

    def test_hyphenated_help_and_version(self):
        help_text = kaufman.make_parser().format_help()
        self.assertIn('--edge-color', help_text)
        self.assertIn('--vertex-color', help_text)
        self.assertNotIn('--edgeColor', help_text)
        self.assertNotIn('--vertexColor', help_text)
        proc = subprocess.run(
            [sys.executable, str(Path(kaufman.__file__)), '--version'],
            text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), 'kaufman.py 0.9.0b1')

    def test_original_canonical_flags(self):
        with patch.object(kaufman, 'run_command') as cmd:
            kaufman.run_canonical('/tmp', output_file='dual.off', both=True)
            command = cmd.call_args.args[0]
            self.assertEqual(command, [
                'canonical', 'tmp_base.off', '-d', '0', '-l', '16',
                '-i', '100000', '-n', '100000', '-z', '100000',
                '-O', 'bd', '-o', 'dual.off',
            ])
        with patch.object(kaufman, 'run_command') as cmd:
            output = io.BytesIO()
            kaufman.run_canonical('/tmp', stdout=output)
            self.assertEqual(cmd.call_args.args[0][2:], list(
                kaufman.CANONICAL_OPTIONS))
            self.assertIs(cmd.call_args.kwargs['stdout'], output)

    def test_hull_iteration_count_and_order(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            def canonical(*args, **kwargs):
                events.append(('canonical', kwargs.get('output_file')))
            def command(args, **kwargs):
                events.append(('command', list(args)))
                self.assertEqual(kwargs['ok_returncodes'], (0, 1, 2, 3))
                (folder / 'tmp_hull.off').write_bytes(b'OFF\n0 0 0\n')
            with patch.object(kaufman, 'run_canonical', side_effect=canonical), \
                 patch.object(kaufman, 'run_command', side_effect=command):
                kaufman.hull_method(folder, 2)
            self.assertEqual((folder/'tmp_base.off').read_bytes(),
                             b'OFF\n0 0 0\n')
        self.assertEqual([x[0] for x in events],
                         ['canonical', 'command', 'canonical', 'command'])
        self.assertEqual(events[1][1],
                         ['conv_hull', 'tmp_canonical_bd.off', '-o',
                          'tmp_hull.off'])
        self.assertEqual(events[3][1], events[1][1])

    def test_conv_hull_requires_fresh_nonempty_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'tmp_base.off').write_bytes(b'original')
            (folder / 'tmp_hull.off').write_bytes(b'stale output')
            with patch.object(kaufman, 'run_canonical'), \
                 patch.object(kaufman, 'run_command') as command:
                with self.assertRaisesRegex(kaufman.CommandError,
                                            'nonempty OFF'):
                    kaufman.hull_method(folder, 1)
                command.assert_called_once()
                self.assertFalse((folder / 'tmp_hull.off').exists())
                self.assertEqual((folder/'tmp_base.off').read_bytes(),
                                 b'original')

    def test_shared_runner_accepts_only_explicit_exit_codes(self):
        from anti_common import run_command, CommandError
        command = [sys.executable, '-c', 'import sys; sys.exit(3)']
        with self.assertRaisesRegex(CommandError, 'exit status 3'):
            run_command(command)
        result = run_command(command, ok_returncodes=(0, 1, 2, 3))
        self.assertEqual(result.returncode, 3)
        with self.assertRaisesRegex(CommandError, 'exit status 4'):
            run_command([sys.executable, '-c', 'import sys; sys.exit(4)'],
                        ok_returncodes=(0, 1, 2, 3))

    def test_zero_hull_iterations(self):
        with patch.object(kaufman, 'run_canonical') as can, \
             patch.object(kaufman, 'run_command') as cmd:
            kaufman.hull_method('/tmp', 0)
            can.assert_not_called()
            cmd.assert_not_called()

    def test_conway_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/'tmp_base.off').write_bytes(b'original')
            recorded = []
            def fake_run(args, **kwargs):
                recorded.append(args)
                kwargs['stdout'].write(b'new model')
            with patch.object(kaufman, 'run_command', side_effect=fake_run):
                kaufman.conway_method(folder, 4)
            self.assertEqual(recorded, [['conway', 'j^4', 'tmp_base.off']])
            self.assertEqual((folder/'tmp_base.off').read_bytes(), b'new model')
            with patch.object(kaufman, 'run_command', side_effect=fake_run):
                kaufman.conway_method(folder, 0, verbose=True)
            self.assertEqual(recorded[-1],
                             ['conway', '-v', 'S', 'tmp_base.off'])

    def test_missing_program_is_reported(self):
        with patch.object(kaufman, 'read_off_file', side_effect=
                          kaufman.CommandError('model missing')):
            with self.assertRaisesRegex(kaufman.CommandError, 'model missing'):
                kaufman.make_kaufman(
                    kaufman.make_parser().parse_args(['foo', '1']),
                    output=io.BytesIO(),
                )

    def test_zero_length_stdin_rejected(self):
        def fake_reader(model, work_dir, name, **kwargs):
            target = Path(work_dir) / name
            target.write_bytes(b'')
            return target
        with patch.object(kaufman, 'read_off_file', side_effect=fake_reader), \
             patch.object(kaufman, 'run_command') as cmd:
            with self.assertRaisesRegex(kaufman.CommandError,
                                        'empty OFF input'):
                kaufman.make_kaufman(kaufman.make_parser().parse_args(['0']),
                                     output=io.BytesIO())
            cmd.assert_not_called()

    def test_hull_failure_does_not_call_color_or_final_canonical(self):
        args = kaufman.make_parser().parse_args(['cube', '1'])
        def fake_reader(model, work_dir, filename, **kwargs):
            p = Path(work_dir) / filename
            p.write_bytes(b'OFF\n0 0 0\n')
            return p
        with patch.object(kaufman, 'read_off_file', side_effect=fake_reader), \
             patch.object(kaufman, 'run_canonical', side_effect=
                          kaufman.CommandError('canonical failed')) as can, \
             patch.object(kaufman, 'run_command') as cmd:
            with self.assertRaisesRegex(kaufman.CommandError,
                                        'canonical failed'):
                kaufman.make_kaufman(args, output=io.BytesIO())
            can.assert_called_once()
            cmd.assert_not_called()

    def test_keep_temp_retains_failed_canonical_output(self):
        """Allow inspecting the exact OFF data sent to conv_hull."""
        args = kaufman.make_parser().parse_args(['cube', '1', '--keep-temp'])
        saved = {}

        def fake_reader(model, directory, name, **kwargs):
            path = Path(directory) / name
            path.write_bytes(b'OFF\n1 0 0\n0 0 0\n')
            saved['directory'] = Path(directory)
            return path

        def fake_canonical(directory, **kwargs):
            (Path(directory) / 'tmp_canonical_bd.off').write_bytes(
                b'OFF\n1 0 0\n0 0 0\n')

        def failing_hull(*args, **kwargs):
            raise kaufman.CommandError('conv_hull exited 3')

        try:
            with patch.object(kaufman, 'read_off_file',
                              side_effect=fake_reader), \
                 patch.object(kaufman, 'run_canonical',
                              side_effect=fake_canonical), \
                 patch.object(kaufman, 'run_command',
                              side_effect=failing_hull), \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaisesRegex(kaufman.CommandError,
                                            'conv_hull exited 3'):
                    kaufman.make_kaufman(args, output=io.BytesIO())
            directory = saved['directory']
            self.assertTrue(directory.exists())
            self.assertTrue((directory / 'tmp_base.off').exists())
            self.assertEqual((directory / 'tmp_canonical_bd.off').read_bytes(),
                             b'OFF\n1 0 0\n0 0 0\n')
            self.assertIn(str(directory), err.getvalue())
        finally:
            if 'directory' in saved:
                shutil.rmtree(saved['directory'], ignore_errors=True)

    def test_default_temp_cleans_up_after_failure(self):
        """Preserve original automatic cleanup without --keep-temp."""
        args = kaufman.make_parser().parse_args(['cube', '1'])
        saved = {}

        def fake_reader(model, directory, name, **kwargs):
            path = Path(directory) / name
            path.write_bytes(b'OFF\n1 0 0\n0 0 0\n')
            saved['directory'] = Path(directory)
            return path

        with patch.object(kaufman, 'read_off_file',
                          side_effect=fake_reader), \
             patch.object(kaufman, 'run_canonical',
                          side_effect=kaufman.CommandError('canonical failed')):
            with self.assertRaisesRegex(kaufman.CommandError,
                                        'canonical failed'):
                kaufman.make_kaufman(args, output=io.BytesIO())
        self.assertFalse(saved['directory'].exists())

    def test_process_flows_with_standins(self):
        if os.name == 'nt':
            self.skipTest('POSIX executable test harness')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            log = root / 'commands.txt'

            def fake_tool(name, source):
                path = bin_dir / name
                path.write_text('#!/usr/bin/env python3\n' + source)
                path.chmod(0o755)

            prologue = '''import os, sys
from pathlib import Path
with open(os.environ['KAUFMAN_TEST_LOG'], 'a') as log:
    log.write(sys.argv[0].rsplit('/', 1)[-1] + ' ' + repr(sys.argv[1:]) + '\\n')
'''
            fake_tool('off_util', prologue + '''if len(sys.argv) == 1:
    sys.stdout.buffer.write(sys.stdin.buffer.read())
else:
    sys.stdout.buffer.write(b'OFF\\n1 0 0\\n0 0 0\\n')
''')
            fake_tool('canonical', prologue + '''model = Path(sys.argv[1]).read_bytes()
if '-o' in sys.argv:
    Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(model + b'#dual\\n')
else:
    sys.stdout.buffer.write(model + b'#final\\n')
''')
            fake_tool('conv_hull', prologue + '''data = Path(sys.argv[1]).read_bytes()
Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(data + b'#hull\\n')
sys.exit(3)  # 3D hull successfully produced
''')
            fake_tool('conway', prologue + '''sys.stdout.buffer.write(
    Path(sys.argv[-1]).read_bytes() + b'#conway\\n')
''')
            fake_tool('off_color', prologue + '''assert sys.argv[2:4] == ['-f', 'S']
assert '-e' in sys.argv and '-v' in sys.argv
sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes() + b'#color\\n')
''')
            env = dict(os.environ)
            env['PATH'] = str(bin_dir) + os.pathsep + env.get('PATH', '')
            env['KAUFMAN_TEST_LOG'] = str(log)
            script = str(Path(kaufman.__file__).resolve())

            def execute(args, input_data=None):
                log.write_text('')
                result = subprocess.run(
                    [sys.executable, script, *args],
                    cwd=root, env=env, input=input_data,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(result.returncode, 0,
                                 result.stderr.decode('utf-8', 'replace'))
                return result.stdout, log.read_text().splitlines()

            output, commands = execute(['cube', '2'])
            self.assertTrue(output.startswith(b'OFF\n'))
            self.assertEqual(output.count(b'#dual'), 2)
            self.assertEqual(output.count(b'#hull'), 2)
            self.assertIn(b'#color\n#final\n', output)
            self.assertEqual([line.split()[0] for line in commands], [
                'off_util', 'canonical', 'conv_hull', 'canonical',
                'conv_hull', 'off_color', 'canonical',
            ])
            self.assertIn("'-O', 'bd'", commands[1])
            self.assertIn("'-d', '0'", commands[-1])

            output, commands = execute(['cube', '0'])
            self.assertEqual([line.split()[0] for line in commands], [
                'off_util', 'off_color', 'canonical',
            ])
            self.assertNotIn(b'#hull', output)

            output, commands = execute(['cube', '3', '-c',
                                        '--edge-color', 'red',
                                        '--vertex-color', 'blue'])
            self.assertEqual([line.split()[0] for line in commands], [
                'off_util', 'conway', 'off_color', 'canonical',
            ])
            self.assertIn("'j^3'", commands[1])
            self.assertIn("'red'", commands[2])
            self.assertIn("'blue'", commands[2])
            self.assertIn(b'#conway\n', output)

            output, commands = execute(['cube', '0', '-c'])
            self.assertIn("'S'", commands[1])

            model = root / 'some model.off'
            model.write_bytes(b'OFF\n1 0 0\n0 0 0\n')
            output, commands = execute([str(model), '1'])
            self.assertTrue(output.startswith(b'OFF\n'))
            self.assertEqual(commands[0].split()[0], 'off_util')
            self.assertNotIn(str(model), commands[0])

            output, commands = execute(['0'],
                                       input_data=b'OFF\n1 0 0\n0 0 0\n')
            self.assertTrue(output.startswith(b'OFF\n'))
            self.assertEqual([line.split()[0] for line in commands], [
                'off_color', 'canonical',
            ])


if __name__ == '__main__':
    unittest.main()
