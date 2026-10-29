#!/usr/bin/env python3
"""Regression checks for merged offanim.py and X_ITE viewer."""
import os
import gzip
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import offanim
import x3dview
from unittest import mock
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request
import re

CUBE = """OFF
8 6 12
-1 -1 -1
-1 -1 1
-1 1 -1
-1 1 1
1 -1 -1
1 -1 1
1 1 -1
1 1 1
4 0 4 6 2
4 1 3 7 5
4 0 1 5 4
4 2 6 7 3
4 0 2 3 1
4 4 5 7 6
"""
WIRE = """OFF
4 2 0
0 0 0
1 0 0
0 1 0
0 0 1
2 0 1 255 0 0 255
2 2 3 0.0 1.0 0.0 0.3
"""
POINTS = """OFF
3 1 0
0 0 0
1 0 0
0 1 0
1 1 0 0 0 0
"""
MIXED = """OFF
5 4 0
0 0 0
1 0 0
0 1 0
0 0 1
1 1 1
3 0 1 2 0.2 0.3 0.4 0.5
2 0 3 0 0 0 0
2 2 4 0 255 0 255
1 3 1.0 0.5 0.0 0.75
"""

class TestRenderer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, contents):
        path = self.root / name
        path.write_text(contents)
        return path

    def render(self, files, *extra):
        out = self.root / "out.x3dv"
        result = subprocess.run([sys.executable, str(HERE / 'offanim.py'),
                                 *(str(f) for f in files), "-o", str(out), *extra],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        scene = out.read_text()
        self.assert_balanced_scene(scene)
        return scene

    def assert_balanced_scene(self, scene):
        # Ignore comments and quoted ECMAScript before checking brackets.
        stack = []
        in_string = False
        comment = False
        escaped = False
        for char in scene:
            if comment:
                if char == "\n":
                    comment = False
                continue
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '#':
                comment = True
            elif char == '"':
                in_string = True
            elif char in '{[':
                stack.append(char)
            elif char in '}]':
                self.assertTrue(stack, f"unmatched closing {char}")
                opening = stack.pop()
                self.assertEqual((opening, char) in (('{', '}'), ('[', ']')),
                                 True, f"incorrect bracket pair {opening}{char}")
        self.assertFalse(in_string, "unclosed X3D string")
        self.assertFalse(stack, f"unclosed X3D brackets: {stack}")

    def test_faces_only(self):
        s = self.render([self.write('cube.off', CUBE)])
        self.assertEqual(s.count('IndexedFaceSet {'), 1)
        self.assertNotIn('IndexedLineSet {', s)
        self.assertNotIn('PointSet {', s)
        self.assertEqual(s.count('Cylinder {'), 1)
        self.assertEqual(s.count('Sphere {'), 1)
        self.assertEqual(s.count('Transform {'), 20)  # 12 edges + 8 vertices
        self.assertNotIn('TimeSensor {', s)
        self.assertEqual(s.count('Coordinate {'), 1)
        self.assertLess(len(s), 10000)

    def test_wire_only_and_rgba(self):
        p = self.write('wire.off', WIRE)
        model = offanim.read_off(p)
        self.assertEqual(len(model.faces), 0)
        self.assertEqual(model.edges[(0,1)], (1, 0, 0, 1))
        s = self.render([p])
        self.assertNotIn('IndexedFaceSet {', s)
        self.assertEqual(s.count('Cylinder {'), 2)  # Two edge colors
        self.assertIn('transparency 0.7', s)
        self.assertIn('diffuseColor 0 1 0', s)

    def test_points_only(self):
        s = self.render([self.write('points.off', POINTS)])
        self.assertIn('Sphere {', s)
        self.assertNotIn('IndexedFaceSet {', s)
        self.assertNotIn('Cylinder {', s)

    def test_mixed_and_hidden(self):
        p = self.write('mixed.off', MIXED)
        model = offanim.read_off(p)
        self.assertEqual(model.faces[0][1], (.2, .3, .4, .5))
        self.assertEqual(model.edges[(0,3)], (0, 0, 0, 0))
        s = self.render([p])
        self.assertIn('IndexedFaceSet {', s)
        self.assertIn('Cylinder {', s)
        self.assertIn('Sphere {', s)
        self.assertIn('diffuseColor 0.2 0.3 0.4', s)
        self.assertIn('transparency 0.5', s)
        # Implicit triangle edges plus colored 2-4; hidden 0-3 is skipped.
        self.assertEqual(s.count('Transform {'), 9)  # 4 rods + 5 balls
        self.assertIn('transparency 0.25', s)
        for hide in ('v','e','f','vef'):
            out = self.render([p], '-x', hide)
            if 'v' in hide: self.assertNotIn('Sphere {', out)
            if 'e' in hide: self.assertNotIn('Cylinder {', out)
            if 'f' in hide: self.assertNotIn('IndexedFaceSet {', out)

    def test_per_face_rgba_and_free_vertex(self):
        scene = """OFF
5 4 0
0 0 0
1 0 0
0 1 0
0 0 1
2 2 2
3 0 1 2 1.0 0.0 0.0 0.2
3 0 2 3 0.0 0.0 1.0 0.8
2 1 4 0.0 1.0 0.0 1.0
1 4 1.0 0.0 1.0 0.5
"""
        p = self.write('colored.off', scene)
        s = self.render([p])
        self.assertEqual(s.count('ColorRGBA {'), 1)  # Face alpha
        self.assertIn('1 0 0 0.2', s)
        self.assertIn('0 0 1 0.8', s)
        self.assertIn('diffuseColor 1 0 1', s)
        self.assertIn('transparency 0.5', s)  # Vertex alpha
        self.assertIn('2 2 2', scene)
        self.assertLess(len(s), 10000)

    def test_single_point(self):
        s = self.render([self.write('one.off','OFF\n1 0 0\n0 0 0\n')])
        self.assertIn('Sphere {',s)

    def test_time_and_edge_ratio(self):
        a = self.write('a.off', CUBE)
        b = self.write('b.off', WIRE)
        c = self.write('c.off', POINTS)
        s = self.render([a,b,c], '--compact','-v','6','--ping-pong','-d','0.3', '-T', 'A "quote"')
        self.assertIn('linewidthScaleFactor 4',s)
        self.assertIn('cycleInterval 1.2',s)
        self.assertIn('keyValue [ 0, 1, 2, 1 ]',s)
        self.assertIn('WorldInfo { title "A \\"quote\\"" }', s)


    def test_compact_fallback(self):
        s = self.render([self.write('cube.off', CUBE)], '--compact')
        self.assertEqual(s.count('IndexedFaceSet {'), 1)
        self.assertEqual(s.count('IndexedLineSet {'), 1)
        self.assertEqual(s.count('PointSet {'), 1)
        self.assertNotIn('Cylinder {', s)
        self.assertNotIn('Sphere {', s)
        self.assertIn('pointSizeScaleFactor 3', s)
        self.assertIn('linewidthScaleFactor 2', s)

    def test_cylinder_rotation(self):
        import math
        for point in [(0, 1, 0), (0, -1, 0), (1, 0, 0),
                      (-1, 0, 0), (0, 0, 1), (0, 0, -1),
                      (2, 3, 4)]:
            result = offanim.cylinder_transform((0, 0, 0), point)
            self.assertIsNotNone(result)
            _, axis, angle, length = result
            # Rodrigues' formula applied to initial +Y.
            cosine, sine = math.cos(angle), math.sin(angle)
            x, y, z = axis
            rotated = (-z * sine + x*y*(1-cosine),
                       cosine + y*y*(1-cosine),
                       x*sine + z*y*(1-cosine))
            desired = tuple(v / length for v in point)
            for actual, expected in zip(rotated, desired):
                self.assertAlmostEqual(actual, expected, places=8)
        self.assertIsNone(offanim.cylinder_transform((0,0,0), (0,0,0)))

    def test_default_radii_and_shared_shapes(self):
        s = self.render([self.write('cube.off', CUBE)])
        self.assertIn('Sphere { radius 0.02 }', s)
        self.assertIn('Cylinder { radius 0.01333333333', s)
        self.assertIn('DEF ROD_0_0 Shape {', s)
        self.assertIn('DEF BALL_0_0 Shape {', s)
        self.assertEqual(s.count('USE ROD_0_0'), 11)
        self.assertEqual(s.count('USE BALL_0_0'), 7)
        # Shape declarations occur inside a Transform, not at the origin.
        self.assertIn('Transform { translation ', s)
        self.assertNotIn('\n        DEF BALL_0_0 Shape', s)
        self.assertNotIn('\n        DEF ROD_0_0 Shape', s)

    def test_wrapper_compact_forwarding(self):
        model = self.write('cube.off', CUBE)
        output = self.root / 'compact.x3dv'
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model),
             '--compact', '-v', '6', '-o', str(output)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        s = output.read_text()
        self.assertIn('pointSizeScaleFactor 6', s)
        self.assertIn('linewidthScaleFactor 4', s)
        self.assertNotIn('Cylinder {', s)

    def test_multiple_alpha_groups_in_solids(self):
        scene = """OFF
4 4 0
0 0 0
1 0 0
0 1 0
0 0 1
2 0 1 1 0 0 0.5
2 1 2 0 0 1 0.7
1 0 1 0 0 0.25
1 3 0 0 0 0
"""
        s = self.render([self.write('groups.off', scene)])
        self.assertEqual(s.count('Cylinder {'), 2)
        self.assertEqual(s.count('Sphere {'), 2)  # default and colored
        self.assertIn('transparency 0.5', s)
        self.assertIn('transparency 0.3', s)
        self.assertIn('transparency 0.75', s)
        self.assertEqual(s.count('Transform {'), 5)  # 2 edges, 3 balls
        self.assertNotIn('IndexedFaceSet {', s)

    def test_animation_default_3d(self):
        a = self.write('a.off', CUBE)
        b = self.write('b.off', WIRE)
        c = self.write('c.off', POINTS)
        s = self.render([a, b, c], '--ping-pong', '-d', '0.3')
        self.assertIn('DEF FRAME_SELECTOR IntegerSequencer {', s)
        self.assertIn('keyValue [ 0, 1, 2, 1 ]', s)
        self.assertIn('cycleInterval 1.2', s)
        self.assertIn('Sphere {', s)
        self.assertIn('Cylinder {', s)

    def test_index_diagnostic(self):
        p = self.write('indexed.off','OFF\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2 7\n')
        proc = subprocess.run([sys.executable,str(HERE/'offanim.py'),str(p)],
                              capture_output=True,text=True,cwd=self.root)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn('indexed OFF color',proc.stderr)

    def test_wrapper_no_filters(self):
        a = self.write('a.off', CUBE)
        b = self.write('b.off', WIRE)
        out = self.root / 'wrapper.x3dv'
        cmd = [sys.executable, str(HERE/'offanim.py'), str(a), str(b),
               '-o',str(out),'-x','e','-T','Wrapper']
        proc=subprocess.run(cmd,text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue(out.is_file())
        self.assertIn('WorldInfo { title "Wrapper" }',out.read_text())
        self.assertNotIn('Cylinder {',out.read_text())

    def test_gzip_default(self):
        model = self.write('cube.off', CUBE)
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model)],
            cwd=self.root, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        packed = self.root / 'anim.x3dvz'
        self.assertTrue(packed.is_file())
        self.assertEqual(packed.read_bytes()[:2], b"\x1f\x8b")
        with gzip.open(packed, 'rt', encoding='utf-8') as stream:
            text = stream.read()
        self.assertIn('IndexedFaceSet {', text)
        self.assertNotIn('TimeSensor {', text)

    def test_no_compress_default(self):
        model = self.write('cube.off', CUBE)
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model),
             '--no-compress'], cwd=self.root, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plain = self.root / 'anim.x3dv'
        self.assertTrue(plain.is_file())
        self.assertTrue(plain.read_text().startswith('#X3D V4.0 utf8'))
        self.assertFalse((self.root / 'anim.x3dvz').exists())

    def test_wrapper_default_compressed(self):
        model = self.write('cube.off', CUBE)
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model)],
            cwd=self.root, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with gzip.open(self.root / 'anim.x3dvz', 'rt', encoding='utf-8') as stream:
            self.assertIn('IndexedFaceSet {', stream.read())

    def test_wrapper_no_compress(self):
        model = self.write('cube.off', CUBE)
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model),
             '--no-compress'], cwd=self.root,
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'anim.x3dv').read_text().startswith('#X3D'))
        self.assertFalse((self.root / 'anim.x3dvz').exists())

    def test_compression_filename_and_conflict(self):
        model = self.write('cube.off', CUBE)
        raw = self.root / 'explicit.x3dv'
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model),
             '-o', str(raw)], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(raw.read_text().startswith('#X3D V4.0 utf8'))
        packed = self.root / 'explicit.x3dvz'
        result = subprocess.run(
            [sys.executable, str(HERE / 'offanim.py'), str(model),
             '-o', str(packed), '--no-compress'],
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('conflicts with .x3dvz', result.stderr)
        self.assertFalse(packed.exists())

    def test_wrapper_filter_and_colors(self):
        # Stub off_color confirms that offanim passes color options and
        # stdin OFF data; no local Antiprism installation is required.
        a = self.write('a.off', CUBE)
        exe = self.root / 'off_color'
        exe.write_text('''#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if args != ['-f','gold','-e','lightgrey','-v','yellow']:
    sys.exit(13)
sys.stdout.buffer.write(sys.stdin.buffer.read())
''')
        exe.chmod(0o755)
        env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ.get('PATH',''))
        out=self.root/'filter.x3dv'
        proc=subprocess.run([sys.executable,str(HERE/'offanim.py'),str(a),
                             '-p','cat','-F','gold','-E','lightgrey','-V','yellow',
                             '-o',str(out)],text=True,capture_output=True,env=env)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn('IndexedFaceSet {',out.read_text())


    def test_opacity_uncolored_implicit_edges(self):
        p = self.write('cube.off', CUBE)
        s = self.render([p], '-t', '128,e')
        self.assertEqual(s.count('Cylinder {'), 1)
        self.assertIn('diffuseColor 0.8 0.6 0.8', s)
        self.assertIn('transparency 0.4980392157', s)
        self.assertNotIn('IndexedLineSet {', s)
        # All twelve edges are still represented.
        self.assertEqual(s.count('USE ROD_0_0'), 11)

    def test_opacity_targets_and_replacement(self):
        p = self.write('mixed.off', MIXED)
        s = self.render([p], '-t', '255,a')
        self.assertNotIn('transparency 0.5', s)
        self.assertIn('diffuseColor 0.2 0.3 0.4', s)
        self.assertIn('diffuseColor 0 0 0', s)
        self.assertIn('Sphere {', s)
        self.assertIn('Cylinder {', s)
        # An explicitly transparent edge becomes visible when -t overrides.
        self.assertEqual(s.count('Transform {'), 10)
        hidden = self.render([p], '-t', '0,a')
        self.assertNotIn('Cylinder {', hidden)
        self.assertNotIn('Sphere {', hidden)
        self.assertNotIn('IndexedFaceSet {', hidden)
        s = self.render([p], '-t', '128')
        self.assertIn('transparency 0.4980392157', s)
        self.assertIn('transparency 0.25', s)

    def test_compact_partial_vertex_visibility(self):
        p = self.write('mixed.off', MIXED)
        s = self.render([p], '--compact', '-x', 'ef')
        self.assertIn('PointSet {', s)
        self.assertIn('ColorRGBA {', s)
        # Vertex 3 is visible; all vertices are still visible in MIXED.
        # Now construct a model with one alpha-zero vertex.
        q = self.write('hidden.off', '''OFF
3 1 0
0 0 0
1 0 0
0 1 0
1 0 0 0 0 0
''')
        out = self.render([q], '--compact')
        # Only two nonzero-alpha points should appear in the PointSet.
        point = out.split('geometry PointSet {', 1)[1]
        self.assertEqual(point.split('point [', 1)[1].split(']', 1)[0]
                         .count(','), 2)
        self.assertIn('PointSet {', out)

    def test_hold_keys_with_ping_pong(self):
        models = [self.write(f'{i}.off', CUBE) for i in range(1, 5)]
        s = self.render(models, '--ping-pong', '-d', '0.2',
                        '--hold', '2=2,4=1')
        self.assertIn('IntegerSequencer {', s)
        self.assertNotIn('Script {', s)
        self.assertIn('keyValue [ 0, 1, 2, 3, 2, 1 ]', s)
        self.assertIn('cycleInterval 5.6', s)
        keys = re.search(r'key \[ ([^]]+) \]', s).group(1)
        actual = [float(v.strip()) for v in keys.split(',')]
        expected = [0, .2, 2.2, 2.4, 3.4, 3.6]
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b / 5.6, places=8)

    def test_hold_validation_and_natural_sort(self):
        models = [self.write(f'50_{i}-scrunchie-001.off', CUBE)
                  for i in (10, 2, 3)]
        s = self.render(models, '--hold', '1=3,3=1')
        self.assertLess(s.index('50_2-scrunchie'), s.index('50_3-scrunchie'))
        self.assertLess(s.index('50_3-scrunchie'), s.index('50_10-scrunchie'))
        for spec in ('0=2', '4=1', '3-2=1', '1=-2', 'a=3',
                     '1=0', '2=3,2=4', '1-999999999=2'):
            cmd = [sys.executable, str(HERE/'offanim.py'),
                   *(str(x) for x in models), '--hold', spec,
                   '-o', str(self.root/'bad.x3dv')]
            proc = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(proc.returncode, 0, spec)

    def test_color_probe_and_preprocessing_pipeline(self):
        model = self.write('cube.off', CUBE)
        exe = self.root / 'off_color'
        exe.write_text('''#!/usr/bin/env python3
import sys
args = sys.argv[1:]
data = sys.stdin.buffer.read()
if args == ['-v', 'gold']:
    print('OFF\\n1 1 0\\n0 0 0\\n1 0 255 215 0')
elif args == ['-v', 'nonsense']:
    print('off_color: error: invalid colouring', file=sys.stderr)
    sys.exit(2)
elif args == ['-f', 'yellow', '-e', 'lightgrey', '-v', 'orange']:
    sys.stdout.buffer.write(data)
else:
    print('unexpected args: ', args, file=sys.stderr)
    sys.exit(3)
''')
        exe.chmod(0o755)
        env = dict(os.environ,
                   PATH=str(self.root) + os.pathsep + os.environ.get('PATH',''))
        out = self.root / 'col.x3dv'
        cmd = [sys.executable, str(HERE / 'offanim.py'), str(model),
               '-B', 'gold', '-F', 'yellow', '-E', 'lightgrey', '-V', 'orange',
               '-p', 'cat', '-o', str(out)]
        proc = subprocess.run(cmd, text=True, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Background { skyColor [ 1 0.8431372549 0 ] }',
                      out.read_text())
        bad = subprocess.run([sys.executable, str(HERE / 'offanim.py'),
                              str(model), '-B', 'nonsense', '-o', str(out)],
                             capture_output=True, text=True, env=env)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn('invalid colouring', bad.stderr)

    def test_x3dview_window_fullscreen_fetch_handshake(self):
        scene = self.write('sample.wrl', '#VRML V2.0 utf8\nGroup {}\n')
        urls = []
        def fetch(url):
            urls.append(url)
            source = parse_qs(urlparse(url).query)['url'][0]
            with urllib.request.urlopen(source, timeout=5) as result:
                self.assertEqual(result.status, 200)
                self.assertEqual(result.headers['Access-Control-Allow-Origin'], '*')
                self.assertIn(b'#VRML V2.0', result.read())
        for fullscreen in (False, True):
            with mock.patch.object(x3dview, 'open_browser', side_effect=fetch):
                with mock.patch('sys.argv', [str(HERE / 'x3dview.py'),
                                              str(scene)] +
                                (['--fullscreen'] if fullscreen else [])):
                    self.assertEqual(x3dview.main(), 0)
        self.assertIn('x3dwin.html', urls[0])
        self.assertIn('x3dview.html', urls[1])
        self.assertNotIn('-url', x3dview.make_parser().format_help())

    def test_merged_program_standalone(self):
        self.assertNotIn('import off2anim',
                         (HERE / 'offanim.py').read_text())
        self.assertFalse((HERE / 'off2anim.py').exists())
        self.assertIn('COMPONENT EventUtilities:1',
                      self.render([self.write('a.off', CUBE),
                                   self.write('b.off', CUBE)]))

if __name__=='__main__':
    unittest.main(verbosity=2)
