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

"""Create static or animated X3D Classic from OFF models.

Reads OFF files in natural order, optionally pre-processes them with an OFF
command/pipeline, and applies Antiprism off_color for V/E/F color overrides.
Face boundaries supply implicit edges; explicit OFF edges take precedence.
The X3D renderer does not materialize implicit edges with off_util -e.

By default, vertices and edges are genuine shared spheres and cylinders;
--compact uses screen-sized points and lines instead. Output is compressed
.x3dvz by default. Use --no-compress for readable .x3dv output.

Timing: -d SECS controls ordinary frame duration. --hold "5=3,12=2,18-20=1"
sets absolute durations for one-based positions in the sorted model list.
Ping-pong playback applies the same hold to each visit to a frame.
"""

import argparse
import glob
import gzip
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from anti_common import (add_version_argument, read_off_bytes,
                         resolve_color, run_filter as common_filter)

VERTEX_COLOR = (1.0, 0.5, 0.0, 1.0)
EDGE_COLOR = (0.8, 0.6, 0.8, 1.0)
FACE_COLOR = (0.8, 0.9, 0.9, 1.0)

def natural_key(path):
    return [(1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"(\d+)", str(path.name))]


def collect_inputs(patterns):
    paths = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        paths.extend(Path(name) for name in (matches or [pattern]))
    unique = list(dict.fromkeys(path.resolve() for path in paths))
    for path in unique:
        if not path.is_file():
            raise ValueError(f"input OFF file not found: {path}")
    return sorted(unique, key=natural_key)


def number(value):
    return format(value, ".10g")


def vector(values):
    return " ".join(number(v) for v in values)


def x3d_string(value):
    # Encode nonprintable chars as space, so no actual newline can escape.
    value = "".join(c if ord(c) >= 32 else " " for c in value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def color_spec(tokens, integer_binary_only):
    """Return normalized RGBA or None (unspecified color).

    The Antiprism OFF syntax supports indexed colors (one integer). They
    require a colormap, so we reject them rather than assign false colors.
    """
    if not tokens:
        return None
    if len(tokens) == 1:
        raise ValueError(
            f"indexed OFF color {tokens[0]!r} needs a color map; "
            "convert it to RGBA with off_color before export"
        )
    if len(tokens) not in (3, 4):
        raise ValueError("OFF color must have 3 or 4 numeric components")
    try:
        rgb = tuple(float(token) for token in tokens)
    except ValueError as exc:
        raise ValueError("invalid numeric OFF color") from exc
    if any(not math.isfinite(v) or v < 0 for v in rgb):
        raise ValueError("nonfinite or negative OFF color component")
    is_integer = all(re.fullmatch(r"[+-]?\d+", token) for token in tokens)
    if is_integer and not integer_binary_only:
        if any(v > 255 for v in rgb):
            raise ValueError("integer OFF color component exceeds 255")
        rgb = tuple(v / 255 for v in rgb)
    elif any(v > 1 for v in rgb):
        raise ValueError("floating-point OFF color must lie in 0..1")
    if len(rgb) == 3:
        rgb += (1.0,)
    return rgb


@dataclass
class OFFModel:
    vertices: list
    faces: list  # (vertex indices, RGBA or None)
    edges: dict  # unordered vertex pair -> RGBA or None
    vertex_colors: dict  # vertex index -> RGBA or None


def read_off(data):
    """Parse OFF bytes (or an OFF file path) into in-memory geometry."""
    if isinstance(data, (str, Path)):
        data = Path(data).read_bytes()
    lines = []
    for line_no, raw in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        line = raw.partition("#")[0].strip()
        if line:
            lines.append((line_no, line))
    if not lines:
        raise ValueError("empty OFF file")
    header, *tail = lines[0][1].split()
    if header not in ("OFF", "COFF"):
        raise ValueError("expected OFF or COFF header")
    pos = 1
    if tail:
        counts = tail
    else:
        if pos >= len(lines):
            raise ValueError("missing OFF counts")
        counts = lines[pos][1].split()
        pos += 1
    if len(counts) < 2:
        raise ValueError("expected vertex and face counts")
    try:
        nv, nr = (int(counts[0]), int(counts[1]))
    except ValueError as exc:
        raise ValueError("invalid OFF counts") from exc
    if nv < 0 or nr < 0 or nv + nr == 0:
        raise ValueError("OFF contains no elements")
    if len(lines) - pos < nv + nr:
        raise ValueError("truncated OFF model")

    vertices = []
    coff_specs = []
    for line_no, line in lines[pos:pos + nv]:
        tokens = line.split()
        if len(tokens) < 3:
            raise ValueError(f"line {line_no}: vertex needs three coordinates")
        try:
            vertex = tuple(float(s) for s in tokens[:3])
        except ValueError as exc:
            raise ValueError(
                f"line {line_no}: invalid vertex coordinate"
            ) from exc
        if any(not math.isfinite(c) for c in vertex):
            raise ValueError(f"line {line_no}: nonfinite vertex coordinate")
        vertices.append(vertex)
        coff_specs.append(tokens[3:] if header == "COFF" else [])
    pos += nv

    raw_records = []
    numeric_colors = [spec for spec in coff_specs if len(spec) in (3, 4)]
    for line_no, line in lines[pos:pos + nr]:
        tokens = line.split()
        try:
            n = int(tokens[0])
            indices = tuple(int(t) for t in tokens[1:n + 1])
        except (ValueError, IndexError) as exc:
            raise ValueError(f"line {line_no}: invalid OFF element") from exc
        if n < 1 or len(indices) != n:
            raise ValueError(f"line {line_no}: invalid element vertex count")
        if any(i < 0 or i >= nv for i in indices):
            raise ValueError(f"line {line_no}: vertex index out of bounds")
        color_tokens = tokens[n + 1:]
        if len(color_tokens) in (3, 4):
            numeric_colors.append(color_tokens)
        raw_records.append((line_no, indices, color_tokens))

    # OFF spec: all integer components 0/1 in the *file* mean floating 0/1.
    # Otherwise integer components represent byte values in 0..255.
    integer_binary_only = all(
        not all(re.fullmatch(r"[+-]?\d+", c) for c in spec)
        or all(int(c) in (0, 1) for c in spec)
        for spec in numeric_colors
    )
    vertex_colors = {}
    for i, spec in enumerate(coff_specs):
        if spec:
            vertex_colors[i] = color_spec(spec, integer_binary_only)
    faces = []
    edges = {}
    for line_no, indices, color_tokens in raw_records:
        try:
            color = color_spec(color_tokens, integer_binary_only)
        except ValueError as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc
        if len(indices) == 1:
            vertex_colors[indices[0]] = color
        elif len(indices) == 2:
            if indices[0] != indices[1]:
                edges[tuple(sorted(indices))] = color
        else:
            faces.append((indices, color))
    return OFFModel(vertices, faces, edges, vertex_colors)


def normalize(vertices):
    if not vertices:
        return []
    lo = [min(p[i] for p in vertices) for i in range(3)]
    hi = [max(p[i] for p in vertices) for i in range(3)]
    mid = [(a + b) / 2 for a, b in zip(lo, hi)]
    radius = max(math.dist(v, mid) for v in vertices)
    if radius == 0:
        return [(0.0, 0.0, 0.0) for _ in vertices]
    return [tuple((v[i] - mid[i]) / radius for i in range(3))
            for v in vertices]


def is_visible(color):
    # Antiprism invisible = (0,0,0,0). Alpha-zero has no visible effect.
    return color is None or color[3] > 0


def make_shape(kind, elements, colors, vertices, define_coord,
               coord_name, args):
    """One Shape per type, with one shared Coordinate node per model."""
    if not elements:
        return [], False
    defaults = {"face": FACE_COLOR, "edge": EDGE_COLOR,
                "vertex": VERTEX_COLOR}
    fallback = defaults[kind]
    values = [c if c is not None else fallback for c in colors]
    uniform = all(c == values[0] for c in values)
    material_color = values[0] if uniform else (1.0, 1.0, 1.0, 1.0)
    field = "diffuseColor" if kind == "face" else "emissiveColor"
    fields = [f"{field} {vector(material_color[:3])}"]
    if kind == "face":
        fields.append("specularColor 0.2 0.2 0.2")
    if uniform and material_color[3] < 1:
        fields.append(f"transparency {number(1 - material_color[3])}")
    text = ["        Shape {", "          appearance Appearance {",
            f"            material Material {{ {' '.join(fields)} }}"]
    if kind == "edge":
        text += ["            lineProperties LineProperties { applied TRUE",
                 f"              linewidthScaleFactor {number(args.edge_size)}",
                 "            }"]
    if kind == "vertex":
        text += ["            pointProperties PointProperties {",
                 f"              pointSizeScaleFactor "
                 f"{number(args.vertex_size)}",
                 f"              pointSizeMinValue {number(args.vertex_size)}",
                 f"              pointSizeMaxValue {number(args.vertex_size)}",
                 "            }"]
    text += ["          }"]
    geom_type = {"face": "IndexedFaceSet", "edge": "IndexedLineSet",
                 "vertex": "PointSet"}[kind]
    text.append(f"          geometry {geom_type} {{")
    if kind == "face":
        text += ["            solid FALSE", "            convex FALSE",
                 "            creaseAngle 0"]
    if kind in ("face", "edge") and not uniform:
        text.append("            colorPerVertex FALSE")
    prefix = "DEF " + coord_name if define_coord else "USE " + coord_name
    # A PointSet has no index list. When some vertices are invisible,
    # provide only the surviving coordinates so ColorRGBA stays aligned.
    filtered_points = (kind == "vertex" and
                       len(elements) != len(vertices))
    if define_coord or filtered_points:
        name = ("DEF " + coord_name + " " if define_coord
                and not filtered_points else "")
        text.append(f"            coord {name}Coordinate {{")
        text.append("              point [")
        positions = ([vertices[i] for i in elements]
                     if filtered_points else vertices)
        text.extend(f"                {vector(v)}," for v in positions)
        text += ["              ]", "            }"]
    else:
        text.append(f"            coord {prefix}")
    if kind in ("face", "edge"):
        text.append("            coordIndex [")
        text.extend("              " + " ".join(str(i) for i in element)
                    + " -1," for element in elements)
        text.append("            ]")
    if not uniform:
        text += ["            color ColorRGBA {", "              color ["]
        text.extend(f"                {vector(c)}," for c in values)
        text += ["              ]", "            }"]
        if kind in ("face", "edge"):
            text.append("            colorIndex [")
            text.extend(f"              {i}," for i in range(len(elements)))
            text.append("            ]")
    text += ["          }", "        }"]
    return text, True


def cylinder_transform(start, end):
    """Place a unit-height, Y-axis cylinder between two model vertices."""
    delta = tuple(b - a for a, b in zip(start, end))
    length = math.sqrt(sum(value * value for value in delta))
    if length <= 1e-14:
        return None
    direction = tuple(value / length for value in delta)
    midpoint = tuple((a + b) / 2 for a, b in zip(start, end))

    # +Y cross direction = (dz, 0, -dx).
    axis = (direction[2], 0.0, -direction[0])
    norm = math.hypot(axis[0], axis[2])
    if norm < 1e-12:
        axis = (1.0, 0.0, 0.0)
        angle = 0.0 if direction[1] >= 0 else math.pi
    else:
        axis = tuple(c / norm for c in axis)
        angle = math.acos(max(-1.0, min(1.0, direction[1])))
    return midpoint, axis, angle, length


def solid_material(color):
    fields = [f"diffuseColor {vector(color[:3])}",
              "specularColor 0.2 0.2 0.2"]
    if color[3] < 1:
        fields.append(f"transparency {number(1 - color[3])}")
    return "Material { " + " ".join(fields) + " }"


def solid_instances(kind, objects, radius, model_index):
    """Instance a shared Shape per color, never at an extra origin location."""
    if radius <= 0:
        return []
    text = []
    definitions = {}
    for transform, color in objects:
        if not is_visible(color):
            continue
        if color not in definitions:
            name = f"{kind}_{model_index}_{len(definitions)}"
            definitions[color] = name
            shape = [f"DEF {name} Shape {{",
                     "  appearance Appearance {",
                     f"    material {solid_material(color)}",
                     "  }", "  geometry " +
                     (f"Sphere {{ radius {number(radius)} }}"
                      if kind == "BALL" else
                      f"Cylinder {{ radius {number(radius)} height 1 "
                      "top FALSE bottom FALSE }"),
                     "}"]
            child = "\n".join(shape)
        else:
            child = f"USE {definitions[color]}"
        text += [f"        Transform {{ {transform}",
                 "          children [",
                 *["            " + line for line in child.splitlines()],
                 "          ]",
                 "        }"]
    return text


def with_opacity(color, kind, args):
    """Apply absolute -t opacity to effective RGBA, not just colored OFF."""
    effective = color if color is not None else {
        "v": VERTEX_COLOR, "e": EDGE_COLOR, "f": FACE_COLOR
    }[kind]
    if args.opacity is not None and kind in args.opacity[1]:
        return (*effective[:3], args.opacity[0] / 255)
    return effective


def make_model(model, index, args):
    pts = normalize(model.vertices)
    edges = {}
    for indices, _ in model.faces:
        for i in range(len(indices)):
            a, b = indices[i], indices[(i + 1) % len(indices)]
            if a != b:
                edges.setdefault(tuple(sorted((a, b))), None)
    # Explicit edges override implicit edges, even when alpha = 0.
    edges.update(model.edges)

    faces = [(indices, with_opacity(col, "f", args))
             for indices, col in model.faces
             if is_visible(with_opacity(col, "f", args))]
    if "f" in args.hide:
        faces = []
    edge_records = [(pair, with_opacity(col, "e", args))
                    for pair, col in sorted(edges.items())
                    if is_visible(with_opacity(col, "e", args))]
    if "e" in args.hide:
        edge_records = []
    vertex_colors = [with_opacity(model.vertex_colors.get(i), "v", args)
                     for i in range(len(pts))]

    text = ["    Group {", "      children ["]
    if args.compact:
        # Original compact geometry; keep it intact as a fallback.
        assigned = False
        for kind, elements, colors in (
            ("face", [f for f, c in faces], [c for f, c in faces]),
            ("edge", [e for e, c in edge_records] if args.edge_size > 0 else [],
             [c for e, c in edge_records] if args.edge_size > 0 else []),
            ("vertex", [i for i, c in enumerate(vertex_colors) if is_visible(c)]
             if args.vertex_size > 0 and "v" not in args.hide else [],
             [c for c in vertex_colors if is_visible(c)]
             if args.vertex_size > 0 and "v" not in args.hide else []),
        ):
            group, made = make_shape(kind, elements, colors, pts,
                                     not assigned, f"COORD_{index}", args)
            if made:
                assigned = True
                text.extend(group)
    else:
        # One IndexedFaceSet, then shared shapes in translated/scaled
        # Transforms. No extra cylinder or sphere at (0, 0, 0).
        face_group, _ = make_shape(
            "face", [f for f, c in faces], [c for f, c in faces],
            pts, True, f"COORD_{index}", args)
        text.extend(face_group)

        if args.edge_size > 0:
            cylinders = []
            for (a, b), col in edge_records:
                placement = cylinder_transform(pts[a], pts[b])
                if placement is None:
                    continue
                mid, axis, angle, length = placement
                transform = (f"translation {vector(mid)} "
                             f"rotation {vector(axis)} {number(angle)} "
                             f"scale 1 {number(length)} 1")
                cylinders.append((transform, col or EDGE_COLOR))
            text.extend(solid_instances("ROD", cylinders, args.edge_size,
                                        index))

        if args.vertex_size > 0 and "v" not in args.hide:
            spheres = [(f"translation {vector(pt)}", color)
                       for pt, color in zip(pts, vertex_colors)
                       if is_visible(color)]
            text.extend(solid_instances("BALL", spheres, args.vertex_size,
                                        index))

    text += ["      ]", "    }"]
    return "\n".join(text)




def parse_opacity(value):
    """Read -t N[,ELMS]; 0 invisible, 255 opaque, default target f."""
    parts = value.split(",")
    if len(parts) not in (1, 2):
        raise argparse.ArgumentTypeError("use N[,ELMS], where N is 0-255")
    try:
        n = int(parts[0])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("opacity must be 0-255") from exc
    if not 0 <= n <= 255:
        raise argparse.ArgumentTypeError("opacity must be 0-255")
    elements = parts[1] if len(parts) == 2 else "f"
    if elements == "a":
        elements = "vef"
    if not elements or any(c not in "vef" for c in elements):
        raise argparse.ArgumentTypeError("elements must contain v, e, f or a")
    return n, "".join(c for c in "vef" if c in elements)


def parse_holds(spec, count=None):
    """Return one-based frame -> absolute duration, checking all syntax."""
    durations = {}
    if not spec:
        return durations
    for item in spec.split(","):
        match = re.fullmatch(
            r"\s*(\d+)(?:-(\d+))?\s*=\s*"
            r"(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*",
            item,
        )
        if not match:
            raise ValueError(
                f"invalid --hold entry {item!r}; use 5=3 or 8-10=1"
            )
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        duration = float(item.split("=", 1)[1].strip())
        if first < 1 or last < first:
            raise ValueError(f"invalid --hold frame range {first}-{last}")
        if count is not None and last > count:
            raise ValueError(
                f"--hold frame {last} exceeds model count ({count})"
            )
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("--hold durations must be positive and finite")
        for frame in range(first, last + 1):
            if frame in durations:
                raise ValueError(
                    f"--hold frame {frame} specified more than once"
                )
            durations[frame] = duration
    return durations


def make_scene(models, args):
    n = len(models)
    sequence = list(range(n))
    if args.ping_pong and n > 2:
        sequence.extend(range(n - 2, 0, -1))
    parts = ["#X3D V4.0 utf8", "PROFILE Immersive", "COMPONENT Shape:4",
             "COMPONENT EventUtilities:1", "", "# Generated by offanim.py",
             f"WorldInfo {{ title {x3d_string(args.title)} }}",
             f"Background {{ skyColor [ {vector(args.background)} ] }}",
             'NavigationInfo { type [ "EXAMINE" "ANY" ] }',
             'Viewpoint { position 0 0 3.5 description "OFF animation" }',
             "", "DEF MODELS Switch {", "  whichChoice 0", "  children ["]
    for idx, (path, model) in enumerate(models):
        parts.append(f"    # Model {idx}: {path.name}")
        parts.append(make_model(model, idx, args))
    parts.extend(["  ]", "}"])
    if n == 1:
        return "\n".join(parts) + "\n"
    durations = [args.holds.get(idx + 1, args.duration) for idx in sequence]
    total = sum(durations)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("animation cycle duration is not finite")
    starts = [0.0]
    elapsed = 0.0
    for length in durations[:-1]:
        elapsed += length
        starts.append(elapsed / total)
    parts.extend(["", "DEF CLOCK TimeSensor {",
                  f"  cycleInterval {number(total)}",
                  "  loop TRUE", "}", "",
                  "DEF FRAME_SELECTOR IntegerSequencer {",
                  "  key [ " + ", ".join(number(t) for t in starts) + " ]",
                  "  keyValue [ " + ", ".join(str(i) for i in sequence) + " ]",
                  "}", "",
                  "ROUTE CLOCK.fraction_changed TO FRAME_SELECTOR.set_fraction",
                  "ROUTE FRAME_SELECTOR.value_changed "
                  "TO MODELS.set_whichChoice", ""])
    return "\n".join(parts)


def run_filter(command, data, label, verbose=False, shell=False):
    """Compatibility wrapper for shared Antiprism byte filters."""
    return common_filter(command, data, label=label,
                         verbose=verbose, shell=shell)


def background_rgb(color, verbose=False):
    """Resolve names and numeric colors through shared Antiprism logic."""
    if color == "0,0,0":
        return (0.0, 0.0, 0.0)
    return resolve_color(color, verbose=verbose)[:3]


def make_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="+", metavar="OFF",
                        help="OFF files or quoted glob patterns")
    parser.add_argument("-o", "--output", default=None, metavar="FILE",
                        help="output file (default: anim.x3dvz)")
    parser.add_argument("--no-compress", action="store_true",
                        help="write readable .x3dv rather than gzip .x3dvz")
    parser.add_argument("-T", dest="title", default="Antiprism",
                        metavar="TITLE", help="X3D scene title")
    parser.add_argument("-t", dest="opacity", type=parse_opacity, default=None,
                        metavar="N[,ELMS]",
                        help="opacity 0-255; v,e,f,a (default f)")
    parser.add_argument("-d", "--frame-time", dest="duration", type=float,
                        default=0.2, metavar="SECS",
                        help="seconds per frame (default: %(default)s)")
    parser.add_argument("--hold", metavar="SPEC",
                        help='frame durations, e.g. "5=3,12=2,18-20=1"')
    parser.add_argument("--ping-pong", action="store_true",
                        help="animate forwards then backwards")
    parser.add_argument("--compact", action="store_true",
                        help="draw flat points/lines instead of 3D geometry")
    parser.add_argument("-v", dest="vertex_size", type=float, default=None,
                        metavar="SIZE", help="vertex radius (default 0.02), or"
                        " --compact point size (default 3)")
    parser.add_argument("-e", dest="edge_size", type=float, default=None,
                        metavar="SIZE",
                        help="edge radius or compact line width"
                        " (default: -v / 1.5)")
    parser.add_argument("-B", dest="background", default="0,0,0",
                        metavar="COLOR",
                        help="background color; any valid Antiprism color")
    parser.add_argument("-x", dest="hide", default="", metavar="ELMS",
                        help="hide elements (v, e, f)")
    parser.add_argument("-V", dest="vertex_color", metavar="COLOR",
                        help="vertex coloring passed to off_color -v")
    parser.add_argument("-E", dest="edge_color", metavar="COLOR",
                        help="edge coloring passed to off_color -e")
    parser.add_argument("-F", dest="face_color", metavar="COLOR",
                        help="face coloring passed to off_color -f")
    parser.add_argument("-p", "--pre-process", dest="pre_process",
                        metavar="COMMAND",
                        help="quoted command/pipeline before processing")
    parser.add_argument("--verbose", action="store_true",
                        help="print subprocess commands and model progress")
    parser.epilog = (
        "OFF default colors: vertex orange, edge lavender, face pale blue.\n"
        "Frames are numbered 1..N in naturally sorted input order.\n"
        "--hold assigns absolute durations and repeats on ping-pong visits.\n"
        "The default X3D output is gzip-compressed."
    )
    add_version_argument(parser)
    return parser


def validate_args(args, parser, count):
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("-d must be a positive finite number")
    if args.vertex_size is None:
        args.vertex_size = 3.0 if args.compact else 0.02
    if args.edge_size is None:
        args.edge_size = args.vertex_size / 1.5
    if any(not math.isfinite(v) or v < 0
           for v in (args.vertex_size, args.edge_size)):
        parser.error("-v and -e must be nonnegative finite numbers")
    if any(c not in "vef" for c in args.hide):
        parser.error("-x may contain only v, e, f")
    try:
        args.holds = parse_holds(args.hold, count)
    except ValueError as exc:
        parser.error(str(exc))
    if any(frame > count for frame in args.holds):
        parser.error(f"--hold frame exceeds model count ({count})")


def output_settings(args):
    if args.output is None:
        name = "anim.x3dv" if args.no_compress else "anim.x3dvz"
        return Path(name), not args.no_compress
    output = Path(args.output)
    suffix = output.suffix.lower()
    if suffix == ".x3dvz":
        if args.no_compress:
            raise ValueError("--no-compress conflicts with .x3dvz filename")
        return output, True
    if suffix == ".x3dv":
        return output, False
    if not suffix:
        suffix = ".x3dv" if args.no_compress else ".x3dvz"
        return output.with_suffix(suffix), not args.no_compress
    raise ValueError("output must end in .x3dv or .x3dvz")


def main(argv=None):
    parser = make_parser()
    args = parser.parse_intermixed_args(argv)
    try:
        # Exactly one non-glob name can be an Antiprism built-in model.
        if (len(args.files) == 1
                and not any(c in args.files[0] for c in "*?[]")
                and not Path(args.files[0]).is_file()):
            files = [Path(args.files[0])]
        else:
            files = collect_inputs(args.files)
        validate_args(args, parser, len(files))
        output, compress = output_settings(args)
        args.background = background_rgb(args.background, args.verbose)
        colors = []
        for flag, value in (("-f", args.face_color),
                            ("-e", args.edge_color),
                            ("-v", args.vertex_color)):
            if value is not None:
                colors.extend((flag, value))
        models = []
        for i, path in enumerate(files, 1):
            if args.verbose:
                print(f"model {i}/{len(files)}: {path.name}", file=sys.stderr)
            data = read_off_bytes(path, verbose=args.verbose)
            if args.pre_process:
                data = run_filter(args.pre_process, data,
                                  f"{path.name}: -p", args.verbose,
                                  shell=True)
            if colors:
                data = run_filter(["off_color", *colors], data,
                                  f"{path.name}: off_color", args.verbose)
            try:
                models.append((path, read_off(data)))
            except (OSError, ValueError, UnicodeError) as exc:
                raise ValueError(f"{path.name}: {exc}") from exc
        scene = make_scene(models, args)
        if compress:
            with gzip.open(output, "wt", encoding="utf-8", newline="\n") as out:
                out.write(scene)
        else:
            output.write_text(scene, encoding="utf-8", newline="\n")
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        parser.exit(1, f"offanim: error: {exc}\n")
    print(f"wrote {output} ({len(models)} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
