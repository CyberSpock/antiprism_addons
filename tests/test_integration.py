#!/usr/bin/env python3

# ChatGPT assisted utility script

# Maintained by Roger Kaufman <polyhedrasmith@gmail.com>

# BSD Zero Clause License
#
# Copyright (c) 2006-2026 Roger Kaufman <polyhedrasmith@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Portable integration checks; executable Antiprism commands are faked."""

import contextlib
import gzip
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit, quote, urlunsplit
from urllib.request import urlopen

TEST_DIR = Path(__file__).resolve().parent
PARENT = (TEST_DIR if (TEST_DIR / "anti_common.py").is_file()
          else TEST_DIR.parent)
sys.path.insert(0, str(PARENT))

import anti_common
import anemone
import offanim
import offview
import x3dview
import stella

CUBE = b"OFF\n4 4 0\n1 1 1\n-1 -1 1\n-1 1 -1\n1 -1 -1\n3 0 1 2\n3 0 3 1\n3 0 2 3\n3 1 3 2\n"

FAKE = '''#!/usr/bin/env python3
import sys
cmd=sys.argv[0].rsplit('/',1)[-1]
arg=sys.argv[1:]
if cmd=='off_util' and arg and arg[0]=='cube':
    sys.stdout.buffer.write(b'OFF\\n1 0 0\\n0 0 0\\n')
    sys.exit(0)
if cmd=='off_util' and arg and arg[0]=='missing':
    sys.stderr.write('invalid model\\n');sys.exit(1)
data=sys.stdin.buffer.read()
if cmd=='off_util' and arg==['-x','ev']:
    # Stand-in for Stella compatibility filtering of explicit edge color.
    sys.stdout.buffer.write(data.replace(b'2 0 1 0.8 0.6 0.8 1', b'2 0 1'))
    sys.exit(0)
if cmd=='off_color' and '-v' in arg and data==b'OFF\\n1 0 0\\n0 0 0\\n':
    c=arg[arg.index('-v')+1]
    if c in ('nonsense','broken'):
        sys.stderr.write('invalid colouring\\n');sys.exit(1)
    col={'red':'1 0 0 1','black':'0 0 0 1','gold':'1 0.84314 0 1',
         'lightgrey':'.82 .82 .82 1','0,0,0':'0 0 0 1'}.get(c,'0.8 0.6 0.8 1')
    sys.stdout.buffer.write(('OFF\\n1 1 0\\n0 0 0\\n1 0 '+col+'\\n').encode())
else:
    sys.stdout.buffer.write(data)
'''

class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        for name in ('off_color','off_util'):
            file=self.tmp/name
            file.write_text(FAKE)
            file.chmod(0o755)
        fake_path = str(self.tmp) + os.pathsep + os.environ.get('PATH','')
        p = mock.patch.dict(os.environ, {'PATH':fake_path})
        p.start(); self.addCleanup(p.stop)

    def test_copy_names(self):
        self.assertEqual(anti_common.name_to_copy('cube.off'), 'cube_copy.off')
        self.assertEqual(anti_common.name_to_copy('movie.x3dvz','.x3dv'), 'movie_copy.x3dv')
        self.assertEqual(anti_common.name_to_copy('/tmp/a b.off','.wrl'), 'a b_copy.wrl')
        self.assertEqual(anti_common.name_to_copy(None,'.off'), 'stdin_copy.off')

    def test_color_success_failure(self):
        self.assertTrue(anti_common.valid_color('red'))
        self.assertFalse(anti_common.valid_color('nonsense'))
        self.assertEqual(anti_common.resolve_color('gold'),(1.,.84314,0.,1.))
        self.assertEqual(offview.background_hex('red'),'ff0000')
        self.assertEqual(offanim.background_rgb('red'),(1,0,0))

    def test_missing_program_color_boolean(self):
        with mock.patch.object(anti_common, '_resolve_program', side_effect=anti_common.CommandError('missing')):
            self.assertFalse(anti_common.valid_color('red'))

    def test_byte_filter_and_explicit_pipeline(self):
        self.assertEqual(anti_common.run_filter(['off_color','-v','gold'], CUBE),CUBE)
        # Intentional explicit shell pipeline (no alias requirement).
        self.assertEqual(anti_common.run_filter('cat | cat',CUBE,shell=True), CUBE)
        with self.assertRaises(anti_common.CommandError):
            anti_common.run_filter(['off_color','-v','nonsense'],anti_common.COLOR_TEST_OFF)

    def test_builtin_resolution(self):
        model_path=self.tmp/'model.off'; model_path.write_bytes(CUBE)
        self.assertEqual(anti_common.read_off_bytes(model_path),CUBE)
        self.assertEqual(anti_common.read_off_bytes('cube'),b'OFF\n1 0 0\n0 0 0\n')
        with self.assertRaises(anti_common.CommandError):
            anti_common.read_off_bytes('missing')
        with self.assertRaises(anti_common.CommandError):
            anti_common.read_off_bytes('*.off')

    def test_offanim_input_and_hold(self):
        out = self.tmp/'movie.x3dvz'
        with mock.patch.object(sys, 'argv', ['offanim','cube','-T','Test', '--hold','1=4', '-o',str(out)]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(offanim.main(),0)
        decoded=gzip.decompress(out.read_bytes()).decode()
        self.assertIn('WorldInfo { title "Test" }',decoded)
        self.assertIn('geometry Sphere', decoded)
        self.assertIn('geometry Cylinder', decoded) if 'Cylinder' in decoded else None

    def test_offanim_holds_two_files(self):
        for name in ['a2.off','a10.off']:
            (self.tmp/name).write_bytes(CUBE)
        dest=self.tmp/'moves.x3dv'
        with contextlib.redirect_stdout(io.StringIO()):
            offanim.main([str(self.tmp/'a*.off'),'--ping-pong',
                          '--hold','1=3,2=1','-d','0.5','-o',str(dest)])
        s=dest.read_text()
        self.assertIn('IntegerSequencer',s)
        self.assertIn('cycleInterval 4',s)
        self.assertIn('a2.off',s)
        self.assertIn('a10.off',s)
        self.assertLess(s.index('a2.off'),s.index('a10.off'))

    def test_bundled_vrml1_conversion(self):
        sample=(b"#VRML V1.0 ascii\nSeparator { Coordinate3 { point [0 0 0, 1 0 0, 0 1 0] } "
                b"IndexedFaceSet { coordIndex [0,1,2,-1] } }\n")
        result=x3dview.convert_vrml1(sample)
        self.assertTrue(result.startswith(b"#VRML V2.0"))
        self.assertIn(b"IndexedFaceSet",result)

    def test_stream_pipeline(self):
        source=self.tmp/'from.off'
        dest=self.tmp/'to.off'
        source.write_bytes(CUBE)
        with source.open('rb') as sin, dest.open('wb') as sout:
            anti_common.run_pipeline([['cat'], ['cat']], stdin=sin,
                                     stdout=sout)
        self.assertEqual(dest.read_bytes(), CUBE)

    def test_shared_read_off_file_builtin(self):
        dest=anti_common.read_off_file('cube',self.tmp,'cube_copy.off')
        self.assertEqual(dest.read_bytes(),b'OFF\n1 0 0\n0 0 0\n')
        staged=self.tmp/'cube_stella_copy.off'
        stella.stage_input('cube',staged,self.tmp)
        self.assertEqual(staged.read_bytes(),dest.read_bytes())

    def test_stella_launch_strips_incompatible_colors(self):
        original = (b'OFF\n2 1 0\n0 0 0\n1 0 0\n'
                    b'2 0 1 0.8 0.6 0.8 1\n')
        source = self.tmp/'colored model.off'
        source.write_bytes(original)
        exe = self.tmp/'fake_stella'
        exe.write_text("""#!/usr/bin/env python3
from pathlib import Path
import os, sys
source = Path(sys.argv[1]); target=Path(os.environ['FAKE_STELLA_CAPTURE'])
target.write_bytes(source.read_bytes())
# On Cygwin, Stella is passed a native Windows path. POSIX
# pathlib does not recognize backslashes as separators.
from pathlib import PureWindowsPath
raw = sys.argv[1]
name = PureWindowsPath(raw).name if chr(92) in raw else source.name
Path(str(target)+'.name').write_text(name)
""")
        exe.chmod(0o755)
        capture=self.tmp/'capture.off'
        folder=self.tmp/'stella-temp'
        folder.mkdir()
        with mock.patch.dict(os.environ,{'FAKE_STELLA_CAPTURE':str(capture)}):
            with mock.patch.object(stella,'stella_executable',return_value=str(exe)):
                with mock.patch.object(stella.tempfile,'mkdtemp',return_value=str(folder)):
                    with mock.patch.object(sys,'argv',['stella',str(source)]):
                        self.assertEqual(stella.main(),0)
        self.assertEqual(capture.read_bytes(),
                         original.replace(b'2 0 1 0.8 0.6 0.8 1', b'2 0 1'))
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(Path(str(capture)+'.name').read_text(),
                         'colored model_copy.off')

    def test_stella_stage_preserves_colored_off(self):
        colored = CUBE+b'#colors kept\n'
        model=self.tmp/'colored.off'; model.write_bytes(colored)
        dest=self.tmp/'colored_copy.off'
        stella.stage_input(str(model),dest,self.tmp)
        self.assertEqual(dest.read_bytes(),colored)

    def test_stella_executable_requires_explicit_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(sys, 'argv', ['stella', '--version']):
                with self.assertRaises(SystemExit) as out:
                    stella.main()
            self.assertEqual(out.exception.code, 0)
            with mock.patch.object(sys, 'argv', ['stella', 'cube']):
                with contextlib.redirect_stderr(io.StringIO()) as error:
                    with self.assertRaises(SystemExit) as out:
                        stella.main()
            self.assertEqual(out.exception.code, 1)
            self.assertIn('set STELLA_EXE', error.getvalue())

    def test_stella_accepts_arbitrary_configured_exe_name(self):
        exe = self.tmp / 'my_own_stella_name'
        exe.write_bytes(b'fake')
        with mock.patch.dict(os.environ, {'STELLA_EXE': str(exe)}):
            self.assertEqual(stella.stella_executable(), str(exe))

    def test_anemone_epsilon_switch_and_scrunchie_tolerance(self):
        import scrunchie
        self.assertEqual(anti_common.DEFAULT_LIMIT, 12)
        self.assertEqual(anti_common.DEFAULT_EPSILON, 1e-12)
        self.assertEqual(scrunchie.CONGRUENCE_TOL, 1e-7)
        with mock.patch.object(sys, 'argv', ['anemone', '5/1', '-l', '9', '-v']):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                with contextlib.redirect_stderr(io.StringIO()) as status:
                    self.assertEqual(anemone.main(), 0)
        self.assertIn('  epsilon = 1e-09', status.getvalue())
        self.assertEqual(anemone.EPSILON, 1e-9)
        self.assertIn('OFF', output.getvalue())
        vertices, _ = anemone.generate_vertices(5, 1)
        self.assertEqual(len(anemone.unit_edges(vertices)), 60)
        # No argument should silently retain the preceding epsilon.
        with mock.patch.object(sys, 'argv', ['anemone', '5/1']):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(anemone.main(), 0)
        self.assertEqual(anemone.EPSILON, 1e-12)

    def test_all_cli_package_versions(self):
        import subprocess
        cli = ('anemone', 'noble', 'scrunchie', 'scrunchie_math',
               'color_wheel', 'stepview', 'vr1tovr2', 'offanim',
               'offview', 'x3dview', 'stella')
        for script in cli:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, str(PARENT / (script + '.py')),
                     '--version'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(anti_common.ADDONS_VERSION, result.stdout)

    def test_offview_served_filename_handshake(self):
        source=self.tmp/'a model.off'; source.write_bytes(CUBE)
        seen={}
        def fetch(url):
            parsed=urlsplit(url)
            model_url=parse_qs(parsed.query)['url'][0]
            parts = urlsplit(model_url)
            encoded = urlunsplit((parts.scheme, parts.netloc,
                                  quote(parts.path), parts.query, parts.fragment))
            with urlopen(encoded,timeout=4) as response:
                seen['bytes']=response.read()
                seen['cors']=response.headers.get('Access-Control-Allow-Origin')
            seen['url']=model_url
        with mock.patch.object(offview,'open_browser',side_effect=fetch):
            self.assertEqual(offview.main([str(source),'-B','red','-timeout','5']),0)
        self.assertEqual(seen['bytes'],CUBE)
        self.assertEqual(seen['cors'],'*')
        self.assertIn('a model_copy.off',seen['url'])

    def test_x3dview_served_filename_handshake(self):
        source=self.tmp/'my geometry.x3dvz'
        data=b'#X3D V4.0 utf8\nPROFILE Immersive\n'
        source.write_bytes(gzip.compress(data))
        seen={}
        def fetch(url):
            model_url=parse_qs(urlsplit(url).query)['url'][0]
            parts = urlsplit(model_url)
            encoded = urlunsplit((parts.scheme, parts.netloc,
                                  quote(parts.path), parts.query, parts.fragment))
            with urlopen(encoded,timeout=4) as response:
                seen['bytes']=response.read()
            seen['url']=model_url
        with mock.patch.object(x3dview,'open_browser',side_effect=fetch):
            with mock.patch.object(sys,'argv',['x3dview',str(source),'-timeout','5']):
                self.assertEqual(x3dview.main(),0)
        self.assertEqual(seen['bytes'],data)
        self.assertIn('my geometry_copy.x3dv',seen['url'])

if __name__=='__main__':unittest.main()
