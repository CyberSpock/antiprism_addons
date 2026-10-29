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

"""View a VRML/X3D file with the online X_ITE viewer.

The input may be a file or standard input. Gzip-compressed input is accepted
automatically. Python serves model data only from localhost; it does not
upload VRML/X3D geometry to the viewer website. The temporary server shuts
down as soon as the viewer has successfully fetched the file.

Examples:
    x3dview model.wrl
    cat model.wrl | x3dview
    gzip -c model.wrl | x3dview
"""

import argparse
from functools import partial
import gzip
import http.server
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from anti_common import (add_version_argument,
                         add_keep_temp_argument, temporary_workdir, name_to_copy,
                         save_local_copy)
import subprocess
import sys
import threading
import webbrowser


DEFAULT_PORT = 0
DEFAULT_TIMEOUT = 60.0
WINDOW_PAGE = "https://www.interocitors.com/polyhedra/x3dwin.html"
FULLSCREEN_PAGE = "https://www.interocitors.com/polyhedra/x3dview.html"


def float_range(minimum, maximum):
    def check(value):
        try:
            number = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a floating point number") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be in range [{minimum} .. {maximum}]"
            )
        return number
    return check


def port_check(value):
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def in_wsl():
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def open_browser(url):
    """Open URL in the user's default graphical browser."""
    if sys.platform == "win32" or sys.platform == "cygwin" or in_wsl():
        subprocess.Popen(
            ["rundll32.exe", "url.dll,FileProtocolHandler", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if not webbrowser.open(url, new=2):
        raise RuntimeError("could not open a web browser")


class X3DRequestHandler(http.server.SimpleHTTPRequestHandler):
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


def read_input(filename):
    if filename:
        try:
            return Path(filename).read_bytes()
        except OSError as exc:
            raise RuntimeError(f"{filename}: {exc.strerror or exc}") from exc

    data = sys.stdin.buffer.read()
    if not data:
        raise RuntimeError("empty input")
    return data


def gunzip_if_needed(data):
    if data[:2] != b"\x1f\x8b":
        return data
    try:
        return gzip.decompress(data)
    except OSError as exc:
        raise RuntimeError(f"invalid gzip input: {exc}") from exc


def is_vrml1(data):
    """Return True when the first line identifies VRML 1.0."""
    if not data:
        return False

    first_line = data.splitlines()[0]

    if first_line.startswith(b"\xef\xbb\xbf"):
        first_line = first_line[3:]

    return first_line.startswith(b"#VRML V1.0")


def convert_vrml1(data):
    """Use the bundled VRML1 converter without a separate executable."""
    from vr1tovr2 import convert_vrml1 as convert

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    try:
        result = convert(text).encode("utf-8")
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"vr1tovr2 conversion failed: {exc}") from exc
    if not result:
        raise RuntimeError("vr1tovr2 conversion produced empty output")
    return result


def normalize_utf8(data):
    """Drop invalid UTF-8 bytes, matching the old iconv -c behavior."""
    return data.decode("utf-8", errors="ignore").encode("utf-8")


def make_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "x3d_file",
        nargs="?",
        help="VRML/X3D file; if omitted, read from standard input",
    )
    parser.add_argument(
        "-s", "--save-local-copy", action="store_true",
        help="save processed VRML/X3D in current directory; "
             "number copies rather than overwrite",
    )
    parser.add_argument(
        "--fullscreen", action="store_true",
        help="use interocitors.com full-window viewer",
    )
    parser.add_argument(
        "-port", "--port",
        type=port_check,
        default=DEFAULT_PORT,
        help="localhost port; 0 chooses an unused port (default: %(default)s)",
    )
    parser.add_argument(
        "-timeout", "--timeout",
        type=float_range(1.0, 3600.0),
        default=DEFAULT_TIMEOUT,
        help="safety timeout waiting for viewer fetch (default: %(default)s seconds)",
    )
    add_keep_temp_argument(parser)
    add_version_argument(parser)

    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    invocation_dir = Path.cwd()

    try:
        data = read_input(args.x3d_file)
        data = gunzip_if_needed(data)

        converted_vrml1 = is_vrml1(data)
        if converted_vrml1:
            data = convert_vrml1(data)

        data = normalize_utf8(data)

        if not data:
            raise RuntimeError("empty input")

        with temporary_workdir("x3dview-", keep=args.keep_temp,
                               program="x3dview") as tmp_name:
            tmp_dir = Path(tmp_name)
            # Serve a meaningful filename, preserving the *actual* format.
            source_ext = (Path(args.x3d_file).suffix.lower()
                          if args.x3d_file else "")
            if converted_vrml1:
                ext = ".wrl"
            elif data.startswith(b"#X3D"):
                ext = ".x3dv"
            elif data.startswith(b"#VRML"):
                ext = ".wrl"
            elif source_ext in (".x3d", ".x3dz"):
                ext = ".x3d"
            else:
                ext = ".wrl"
            view_name = name_to_copy(args.x3d_file, ext)
            view_path = tmp_dir / view_name
            view_path.write_bytes(data)
            if args.save_local_copy:
                saved = save_local_copy(view_path, directory=invocation_dir)
                print(f"x3dview: saved local copy: {saved}", file=sys.stderr)

            fetched = threading.Event()

            class Handler(X3DRequestHandler):
                fetched_event = fetched
                served_name = view_name

            handler = partial(Handler, directory=str(tmp_dir))

            server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", args.port),
                handler,
            )
            actual_port = server.server_address[1]
            server_thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            server_thread.start()

            try:
                page = FULLSCREEN_PAGE if args.fullscreen else WINDOW_PAGE
                url = (f"{page}?url=http://127.0.0.1:{actual_port}/"
                       f"{quote(view_name)}")
                open_browser(url)

                if not fetched.wait(args.timeout):
                    raise RuntimeError(
                        f"viewer did not fetch {view_name} within {args.timeout:g} seconds"
                    )
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"x3dview: {exc}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
