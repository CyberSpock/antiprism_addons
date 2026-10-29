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

"""Local tests for offview.py; Antiprism executables are mocked."""

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

# Run equally well from this source tree or an installed scripts directory.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anti_common
import offview


CUBE = b"OFF\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n"


class ViewerTests(unittest.TestCase):
    def test_options(self):
        p = offview.make_parser()
        a = p.parse_args(["cube.off", "-x", "fev", "-t", "128,a"])
        self.assertEqual(a.hide, "vef")
        self.assertEqual(a.transparency, (128, "vef"))
        self.assertEqual(p.parse_args(["-t", "255"]).transparency, (255, "f"))
        self.assertEqual(p.parse_args(["-t", "90,ev"]).transparency,
                         (90, "ve"))
        self.assertEqual(
            p.parse_args(["-p", "off_trans -R 0,10,0"]).pre_process,
            "off_trans -R 0,10,0")
        self.assertIsNone(p.parse_args([]).edge_radius)

    def test_invalid_options(self):
        for args in (["-t", "256"], ["-t", "3.5,f"],
                     ["-t", "10,z"], ["-x", "foo"]):
            with (self.subTest(args=args),
                  mock.patch("sys.stderr", io.StringIO())):
                with self.assertRaises(SystemExit):
                    offview.make_parser().parse_args(args)

    def test_background_conversion(self):
        # Background colors now go through anti_common.resolve_color().
        # Mock the actual Antiprism boundary, not offview.run_off_tool().
        probe = b"OFF\n1 1 0\n0 0 0\n1 0 1.0 0.5 0.0 0.25\n"
        with mock.patch.object(anti_common, "run_filter",
                               return_value=probe) as run:
            self.assertEqual(offview.background_hex("orange"), "ff800040")
            self.assertEqual(run.call_args.args[0],
                             ["off_color", "-v", "orange"])
            offview.background_hex("112233")
            self.assertEqual(run.call_args.args[0],
                             ["off_color", "-v", "x112233"])
            offview.background_hex("11223344")
            self.assertEqual(run.call_args.args[0],
                             ["off_color", "-v", "17,34,51,68"])
        self.assertEqual(offview.background_hex("invisible"), "invisible")
        self.assertEqual(offview.background_hex("none"), "invisible")

    def test_background_byte_rgb(self):
        # OFF color channels may be integer bytes instead of floats.
        probe = b"OFF\n1 1 0\n0 0 0\n1 0 255 128 0 64\n"
        with mock.patch.object(anti_common, "run_filter",
                               return_value=probe):
            self.assertEqual(offview.background_hex("orange"), "ff800040")

    def test_bad_background(self):
        with mock.patch.object(
            anti_common, "run_filter", side_effect=anti_common.CommandError(
                "invalid colouring")):
            with self.assertRaisesRegex(anti_common.CommandError,
                                        "invalid colouring"):
                offview.background_hex("nonsense")

    def test_colors_transparency_and_hiding(self):
        args = offview.make_parser().parse_args(
            ["-V", "gold", "-E", "lightgrey", "-F", "yellow",
             "-t", "128,a", "-x", "f"])
        calls = []
        def filtered(program, options, data, label):
            calls.append((program, list(options), label))
            return data
        with mock.patch.object(offview, "run_off_tool", side_effect=filtered):
            self.assertEqual(offview.preprocess_off(CUBE, args), CUBE)
        self.assertEqual(calls, [
            ("off_color", ["-e", "0.8,0.6,0.8", "-E", "I"],
             "off_color implicit edges"),
            ("off_color", ["-f", "yellow", "-e", "lightgrey",
                           "-v", "gold"], "off_color"),
            ("off_color", ["-r", f"A{128/255:.12g},vef"],
             "off_color transparency"),
            ("off_util", ["-x", "f"], "off_util hide"),
        ])

    def test_hide_other_types(self):
        args = offview.make_parser().parse_args(["-x", "vef"])
        with mock.patch.object(offview, "run_off_tool",
                               return_value=CUBE) as run:
            offview.preprocess_off(CUBE, args)
            self.assertEqual(run.call_args.args[1], ["-x", "vef"])
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[1],
                             ["-e", "0.8,0.6,0.8", "-E", "I"])

    def test_color_implicit_edges_on_every_input(self):
        args = offview.make_parser().parse_args([])
        with mock.patch.object(offview, "run_off_tool",
                               return_value=CUBE) as run:
            self.assertEqual(offview.preprocess_off(CUBE, args), CUBE)
            run.assert_called_once_with(
                "off_color", ["-e", "0.8,0.6,0.8", "-E", "I"],
                CUBE, "off_color implicit edges")

    def test_implicit_edge_opacity_without_edge_override(self):
        # This was the real-world failure with off_util -e: its uncolored
        # explicit edges couldn't acquire useful alpha information.
        args = offview.make_parser().parse_args(["-t", "128,e"])
        calls = []

        def filtered(program, options, data, label):
            calls.append((program, list(options)))
            return data

        with mock.patch.object(offview, "run_off_tool",
                               side_effect=filtered):
            offview.preprocess_off(CUBE, args)

        self.assertEqual(calls, [
            ("off_color", ["-e", "0.8,0.6,0.8", "-E", "I"]),
            ("off_color", ["-r", f"A{128/255:.12g},e"]),
        ])

    def test_help_labels(self):
        help_text = offview.make_parser().format_help()
        self.assertIn("use interocitors.com full-window viewer", help_text)
        self.assertIn("quoted command/pipeline before processing", help_text)
        self.assertIn("initial spin speed (can be positive or negative)", help_text)

    def test_black_shortcut_colors_off_not_url(self):
        args = offview.make_parser().parse_args(
            ["-V", "gold", "-E", "lightgrey", "-F", "yellow", "-l"])
        calls = []
        def filtered(program, options, data, label):
            calls.append((program, list(options)))
            return data
        with mock.patch.object(offview, "run_off_tool", side_effect=filtered):
            offview.preprocess_off(CUBE, args)
        self.assertEqual(calls, [
            ("off_color", ["-e", "0.8,0.6,0.8", "-E", "I"]),
            ("off_color", ["-f", "yellow", "-e", "black", "-v", "black"]),
        ])
        url = offview.make_query(args, "cccccc", "cube_copy.off", 1234)
        params = parse_qs(urlparse(url).query)
        self.assertNotIn("data-vertex-color", params)
        self.assertNotIn("data-edge-color", params)

    def test_pre_process_before_coloring_implicit_edges(self):
        args = offview.make_parser().parse_args(
            ["-p", "off_trans -R 0,10,0", "-x", "f"])
        order = []
        def filtered(program, options, data, label):
            order.append((program, options))
            return data
        with mock.patch.object(offview, "run_preprocess",
                               side_effect=lambda cmd, data: (
                                   order.append(("pre", cmd)), data)[1]):
            with mock.patch.object(offview, "run_off_tool",
                                   side_effect=filtered):
                offview.preprocess_off(CUBE, args)
        self.assertEqual(order, [
            ("pre", "off_trans -R 0,10,0"),
            ("off_color", ["-e", "0.8,0.6,0.8", "-E", "I"]),
            ("off_util", ["-x", "f"]),
        ])

    @unittest.skipUnless(shutil.which("cat"), "requires a POSIX cat")
    def test_pre_process_shell_pipeline(self):
        self.assertEqual(offview.run_preprocess("cat | cat", CUBE), CUBE)

    def test_pre_process_failure(self):
        args = offview.make_parser().parse_args(["-p", "broken-filter"])
        with mock.patch.object(offview, "run_preprocess",
                               side_effect=RuntimeError("pre-process failed")):
            with self.assertRaisesRegex(RuntimeError, "pre-process failed"):
                offview.preprocess_off(CUBE, args)

    def test_explicit_edge_radius_and_default(self):
        parser = offview.make_parser()
        base = offview.make_query(parser.parse_args([]),
                                  "cccccc", "cube_copy.off", 5555)
        params = parse_qs(urlparse(base).query)
        self.assertEqual(float(params["data-edge-radius"][0]), 0.02)

        args = parser.parse_args(["-v", "0.06"])
        url = offview.make_query(args, "cccccc", "cube_copy.off", 5555)
        params = parse_qs(urlparse(url).query)
        self.assertAlmostEqual(float(params["data-edge-radius"][0]), 0.04)

        args = parser.parse_args(["-v", "0.06", "-e", "0.01"])
        url = offview.make_query(args, "cccccc", "cube_copy.off", 5555)
        params = parse_qs(urlparse(url).query)
        self.assertEqual(float(params["data-edge-radius"][0]), 0.01)

    def test_url_query(self):
        args = offview.make_parser().parse_args(
            ["-x", "ef", "-l", "-rot", "0.3", "--fullscreen"])
        query = offview.make_query(args, "f0e1d2", "my model_copy.off", 5555)
        self.assertTrue(query.startswith(offview.FULLSCREEN_PAGE + "?"))
        params = parse_qs(urlparse(query).query)
        self.assertEqual(params["url"],
                         ["http://127.0.0.1:5555/my model_copy.off"])
        self.assertIn("data-rotation-axis=0,1,0", query)
        self.assertEqual(params["data-background-color"], ["f0e1d2"])
        self.assertEqual(params["data-edges-active"], ["false"])
        self.assertEqual(params["data-faces-active"], ["false"])
        self.assertNotIn("data-vertices-active", params)
        self.assertNotIn("data-edge-color", params)
        self.assertNotIn("data-vertex-color", params)
        self.assertEqual(params["data-rotation-speed"], ["0.3"])
        self.assertNotIn("data-face-color", params)
        self.assertNotIn("useBaseColor", params)

    def test_server_handshake(self):
        with tempfile.TemporaryDirectory() as temp:
            name = Path(temp) / "a model.off"
            name.write_bytes(CUBE)
            fetched_urls = []
            def fake_browser(url):
                fetched_urls.append(url)
                query = urlparse(url).query
                model_url = query.split("&", 1)[0].split("=", 1)[1]
                with urlopen(model_url, timeout=3) as response:
                    self.assertEqual(response.read(), CUBE)
                    self.assertEqual(
                        response.headers["Access-Control-Allow-Origin"], "*")
            # The HTTP handshake is genuine, but Antiprism isn't installed
            # in this test environment, so fake the initial color pass.
            with mock.patch.object(offview, "run_off_tool",
                                   return_value=CUBE):
                with mock.patch.object(offview, "open_browser",
                                       side_effect=fake_browser):
                    self.assertEqual(
                        offview.main([str(name), "-timeout", "3"]), 0)
            self.assertIn("a%20model_copy.off", fetched_urls[0])
            self.assertFalse(list(Path(temp).glob("*_copy.off")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
