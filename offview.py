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

"""Prepare an OFF model with Antiprism and view it in Wagyx's web viewer.

Reads an OFF file or stdin; all geometry and color transformations happen
locally, before the temporary OFF file is served to the browser. The
Python program serves model data only from localhost; it does not upload OFF
geometry to the viewer website.
"""

import argparse
from functools import partial
import http.server
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from urllib.parse import quote, unquote, urlsplit

from anti_common import (add_version_argument,
                         add_keep_temp_argument, temporary_workdir, name_to_copy,
                         read_off_bytes, resolve_color,
                         save_local_copy,
                         run_filter as common_filter)
import webbrowser


DEFAULT_PORT = 0
DEFAULT_TIMEOUT = 60.0
WINDOW_PAGE = "https://www.interocitors.com/polyhedra/offwin.html"
FULLSCREEN_PAGE = "https://www.interocitors.com/polyhedra/offview.html"


def float_range(minimum, maximum):
    def check(value):
        try:
            number = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a number") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be in range [{minimum} .. {maximum}]")
        return number
    return check


def coords_check(value):
    try:
        values = [float(piece) for piece in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("axis must be x,y,z") from exc
    if len(values) != 3 or not all(abs(x) < float("inf") for x in values):
        raise argparse.ArgumentTypeError("axis must be three finite numbers")
    return ",".join(f"{x:g}" for x in values)


def hide_check(value):
    if value and any(letter not in "vef" for letter in value):
        raise argparse.ArgumentTypeError("use any of v, e, f (e.g. -x ve)")
    return "".join(letter for letter in "vef" if letter in value)


def transparency_check(value):
    pieces = value.split(",")
    if len(pieces) > 2:
        raise argparse.ArgumentTypeError("use OPACITY[,vef|a], 0-255")
    try:
        opacity = int(pieces[0])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("opacity must be 0-255") from exc
    if not 0 <= opacity <= 255:
        raise argparse.ArgumentTypeError("opacity must be 0-255")
    elements = pieces[1] if len(pieces) == 2 else "f"
    if elements == "a":
        elements = "vef"
    if not elements or any(letter not in "vef" for letter in elements):
        raise argparse.ArgumentTypeError("elements must be v, e, f or a")
    elements = "".join(letter for letter in "vef" if letter in elements)
    return opacity, elements


def port_check(value):
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def in_wsl():
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def open_browser(url):
    if sys.platform == "win32":
        os.startfile(url)
        return
    if sys.platform == "cygwin" or in_wsl():
        subprocess.Popen(
            ["rundll32.exe", "url.dll,FileProtocolHandler", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    if not webbrowser.open(url, new=2):
        raise RuntimeError("could not open a web browser")


class OffRequestHandler(http.server.SimpleHTTPRequestHandler):
    fetched_event = None
    served_name = None

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        requested = unquote(urlsplit(self.path).path)
        try:
            super().do_GET()
        finally:
            if (requested == "/" + self.served_name
                    and self.fetched_event is not None):
                self.fetched_event.set()


def run_off_tool(program, options, data, label):
    """Filter an OFF model with the shared byte-oriented runner."""
    return common_filter([program, *options], data, label=label)


def background_hex(color):
    """Resolve Antiprism syntax to the RGB[A] hex Wagyx understands."""
    if color.lower() in ("invisible", "none"):
        return "invisible"
    if re.fullmatch(r"[0-9a-fA-F]{6}", color):
        color = "x" + color  # Maintain historic bare-hex -B input.
    elif re.fullmatch(r"[0-9a-fA-F]{8}", color):
        color = ",".join(str(int(color[i:i+2], 16))
                         for i in range(0, 8, 2))
    rgba = resolve_color(color)
    if rgba[3] == 0:
        return "invisible"
    channels = [round(value * 255) for value in rgba]
    if rgba[3] == 1:
        channels = channels[:3]
    return "".join(f"{v:02x}" for v in channels)


def run_preprocess(command, data):
    """Run a user-supplied command or shell pipeline."""
    return common_filter(command, data, label="pre-process", shell=True)


def preprocess_off(data, args):
    # A requested filter acts on the original input, before any of our own
    # operations. Quoting and pipelines are controlled by the CLI user.
    if args.pre_process:
        data = run_preprocess(args.pre_process, data)

    # FIRST built-in operation: materialize implicit edges with Antiview's
    # default edge color. -E I selects only implicit edges, leaving existing
    # explicitly colored edges untouched. Unlike uncolored edges from
    # off_util -e, these edges can subsequently have their alpha changed.
    data = run_off_tool(
        "off_color", ["-e", "0.8,0.6,0.8", "-E", "I"],
        data, "off_color implicit edges")

    # -l is simply shorthand for -V black -E black. It takes precedence
    # over individual -V/-E settings, like the earlier viewer's shortcut.
    vertex_color = "black" if args.black_edges else args.vertex_color
    edge_color = "black" if args.black_edges else args.edge_color

    color_args = []
    for flag, color in (("-f", args.face_color),
                        ("-e", edge_color),
                        ("-v", vertex_color)):
        if color is not None:
            color_args.extend((flag, color))

    if color_args:
        data = run_off_tool("off_color", color_args, data, "off_color")

    if args.transparency is not None:
        opacity, elements = args.transparency
        # Remap only alpha; leave any pre-existing RGB colors intact.
        alpha = f"{opacity / 255:.12g}"
        data = run_off_tool("off_color", ["-r", f"A{alpha},{elements}"],
                            data, "off_color transparency")

    if args.hide:
        data = run_off_tool("off_util", ["-x", args.hide],
                            data, "off_util hide")
    return data


def make_query(args, background, off_name, port):
    model_url = f"http://127.0.0.1:{port}/{quote(off_name)}"
    edge_radius = (args.edge_radius if args.edge_radius is not None
                   else args.vertex_radius / 1.5)
    params = {
        "url": model_url,
        "data-vertex-radius": f"{args.vertex_radius:g}",
        "data-edge-radius": f"{edge_radius:g}",
        "data-background-color": background,
        "data-rotation-speed": f"{args.rotation_speed:g}",
        "data-rotation-axis": args.rotation_axis,
    }
    for letter, param in (("v", "data-vertices-active"),
                          ("e", "data-edges-active"),
                          ("f", "data-faces-active")):
        if letter in args.hide:
            params[param] = "false"
    page = FULLSCREEN_PAGE if args.fullscreen else WINDOW_PAGE
    # The site's established getUrlVars()/getAll() functions expect literal
    # commas in data-rotation-axis; avoid changing their query conventions.
    # Every value is program-generated or validated, and the model filename
    # is individually URL-quoted above.
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return page + "?" + query


def read_input(filename):
    if filename and filename != "-":
        try:
            return Path(filename).read_bytes()
        except OSError as exc:
            raise RuntimeError(f"{filename}: {exc.strerror or exc}") from exc
    data = sys.stdin.buffer.read()
    if not data.strip():
        raise RuntimeError("empty input")
    return data


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("off_file", nargs="?", metavar="OFF",
                        help="OFF file (default: standard input)")
    parser.add_argument("-v", dest="vertex_radius", type=float_range(0, 1),
                        default=0.03, metavar="SIZE",
                        help="vertex radius (default: %(default)s)")
    parser.add_argument("-e", dest="edge_radius", type=float_range(0, 1),
                        default=None, metavar="SIZE",
                        help="edge radius (default: -v / 1.5)")
    parser.add_argument("-x", dest="hide", type=hide_check, default="",
                        metavar="ELMS", help="hide elements (v, e, f)")
    parser.add_argument("-l", dest="black_edges", action="store_true",
                        help="shortcut for -V black -E black")
    parser.add_argument("-V", dest="vertex_color", metavar="COLOR",
                        help="vertex coloring passed to off_color -v")
    parser.add_argument("-E", dest="edge_color", metavar="COLOR",
                        help="edge coloring passed to off_color -e")
    parser.add_argument("-F", dest="face_color", metavar="COLOR",
                        help="face coloring passed to off_color -f")
    parser.add_argument("-t", dest="transparency", type=transparency_check,
                        metavar="N[,ELMS]",
                        help="opacity 0-255; v,e,f,a (default f)")
    parser.add_argument("-B", dest="background_color", default=None,
                        metavar="COLOR",
                        help="background color; any valid Antiprism color")
    parser.add_argument("-rot", dest="rotation_speed", type=float, default=0,
                        metavar="SPEED", help="initial spin speed (can be positive or negative)")
    parser.add_argument("-rotax", dest="rotation_axis", type=coords_check,
                        default="0,1,0", metavar="X,Y,Z", help="rotation axis")
    parser.add_argument("-p", "--pre-process", dest="pre_process",
                        metavar="COMMAND",
                        help="quoted command/pipeline before processing")
    parser.add_argument("-s", "--save-local-copy", action="store_true",
                        help="save processed OFF in current directory; "
                             "number copies rather than overwrite")
    parser.add_argument("--fullscreen", action="store_true",
                        help="use interocitors.com full-window viewer")
    parser.add_argument("-port", type=port_check, default=DEFAULT_PORT,
                        metavar="PORT", help="localhost port (default: auto)")
    parser.add_argument("-timeout", type=float_range(1, 3600),
                        default=DEFAULT_TIMEOUT, metavar="SEC",
                        help="maximum wait for browser fetch (default: 60)")
    add_keep_temp_argument(parser)
    add_version_argument(parser)
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    invocation_dir = Path.cwd()
    try:
        off_data = read_off_bytes(args.off_file)
        if not off_data.strip():
            raise RuntimeError("empty input")
        off_data = preprocess_off(off_data, args)
        background = ("cccccc" if args.background_color is None
                      else background_hex(args.background_color))

        # Use the actual input name, not a generic offview.off placeholder.
        off_name = name_to_copy(args.off_file, ".off")
        with temporary_workdir("offview-", keep=args.keep_temp,
                               program="offview") as tmp_name:
            tmp_dir = Path(tmp_name)
            staged = tmp_dir / off_name
            staged.write_bytes(off_data)
            if args.save_local_copy:
                saved = save_local_copy(staged, directory=invocation_dir)
                print(f"offview: saved local copy: {saved}", file=sys.stderr)

            fetched = threading.Event()

            class Handler(OffRequestHandler):
                fetched_event = fetched
                served_name = off_name

            handler = partial(Handler, directory=str(tmp_dir))
            server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port),
                                                       handler)
            port = server.server_address[1]
            server_thread = threading.Thread(target=server.serve_forever,
                                              daemon=True)
            server_thread.start()
            try:
                url = make_query(args, background, off_name, port)
                open_browser(url)
                if not fetched.wait(args.timeout):
                    raise RuntimeError(
                        f"viewer did not fetch {off_name} "
                        f"within {args.timeout:g} seconds")
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"offview: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
