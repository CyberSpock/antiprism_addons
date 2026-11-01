"""Executable resolution and old/new Antiview compatibility tests."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import anti_common
import stepview


class CompatibilityTests(unittest.TestCase):
    def test_exe_fallback(self):
        def lookup(name):
            return '/tools/off_util.exe' if name == 'off_util.exe' else None

        with patch('anti_common.shutil.which', side_effect=lookup):
            self.assertEqual(
                anti_common._resolve_program(['off_util', '-h']),
                ['/tools/off_util.exe', '-h'],
            )

    def test_native_precedence(self):
        with patch('anti_common.shutil.which',
                   side_effect=lambda name: '/tools/' + name):
            self.assertEqual(
                anti_common._resolve_program(['off_util'])[0],
                '/tools/off_util',
            )

    def _run_viewer(self, model, *, fails_first, try_title=True):
        """Simulate a viewer rejecting -T or remaining open with -T."""
        commands = []

        def spawn(command, **kwargs):
            commands.append(command[:])
            proc = Mock()
            if fails_first and len(commands) == 1:
                proc.wait.return_value = 2
                proc.poll.return_value = 2
            else:
                proc.wait.side_effect = subprocess.TimeoutExpired(command, 1)
                proc.poll.return_value = None
            return proc

        with (patch('stepview.viewer_command', side_effect=lambda *args: ['antiview']),
              patch('stepview.source_command', return_value=None),
              patch('stepview.subprocess.Popen', side_effect=spawn)):
            result = stepview.run_model(
                model, 'antiview', None, '', '', False,
                try_title=try_title,
            )
            # The real file was opened as viewer stdin; clean it up.
            result[2].close()
        return commands, result[3]

    def test_new_antiview_receives_title(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cube.off'
            path.write_text('OFF\n0 0 0\n')
            commands, try_title = self._run_viewer(
                path, fails_first=False,
            )
        self.assertEqual(commands, [['antiview', '-T', 'cube.off']])
        self.assertTrue(try_title)

    def test_old_antiview_retries_without_title_once(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cube.off'
            path.write_text('OFF\n0 0 0\n')
            commands, try_title = self._run_viewer(
                path, fails_first=True,
            )
            next_commands, next_try_title = self._run_viewer(
                path, fails_first=False, try_title=try_title,
            )
        self.assertEqual(commands, [
            ['antiview', '-T', 'cube.off'],
            ['antiview'],
        ])
        self.assertFalse(try_title)
        self.assertEqual(next_commands, [['antiview']])
        self.assertFalse(next_try_title)

    def test_pipx_viewers(self):
        with patch('stepview.shutil.which', side_effect=lambda name: (
            '/opt/pipx/bin/' + name if name in ('x3dview', 'offview')
            else None
        )):
            self.assertEqual(stepview.viewer_command('x3dview', ''),
                             ['/opt/pipx/bin/x3dview'])
            self.assertEqual(stepview.viewer_command('offview', ''),
                             ['/opt/pipx/bin/offview'])

    def test_legacy_python_viewer(self):
        with patch('stepview.shutil.which', side_effect=lambda name: (
            '/usr/local/bin/x3dview.py' if name == 'x3dview.py'
            else None
        )):
            self.assertEqual(stepview.viewer_command('x3dview', ''),
                             [sys.executable, '/usr/local/bin/x3dview.py'])


if __name__ == '__main__':
    unittest.main()
