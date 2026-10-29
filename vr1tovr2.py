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

"""Convert VRML 1.0 to VRML 2.0 (VRML97).

If the input is not VRML 1.0, it is passed through unchanged.
If input_file is omitted, input is read from standard input.
Output is written to standard output unless -o is used.

This converter focuses on geometry-oriented VRML 1.0 files and supports the
node families used by the Antiprism Addons sample corpus.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from anti_common import add_version_argument
import re
import sys



@dataclass
class Node:
    kind: str
    body: str
    def_name: str | None = None


@dataclass
class Use:
    name: str


@dataclass
class State:
    coord: str | None = None
    normal: str | None = None
    material: str | None = None
    material_binding: str = "OVERALL"
    normal_binding: str = "PER_VERTEX_INDEXED"
    shape_hints: str | None = None
    transforms: list[Node] = field(default_factory=list)

    def clone(self):
        return State(
            coord=self.coord,
            normal=self.normal,
            material=self.material,
            material_binding=self.material_binding,
            normal_binding=self.normal_binding,
            shape_hints=self.shape_hints,
            transforms=list(self.transforms),
        )


def strip_comments(text):
    out = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def matching(text, start, open_char, close_char):
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unmatched {open_char}")


def scan_items(text):
    items = []
    i = 0
    token = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    while i < len(text):
        m = token.search(text, i)
        if not m:
            break
        word = m.group(0)
        pos = m.end()

        if word == "USE":
            n = token.search(text, pos)
            if n:
                items.append(Use(n.group(0)))
                i = n.end()
                continue

        def_name = None
        kind = word
        if word == "DEF":
            n = token.search(text, pos)
            if not n:
                break
            def_name = n.group(0)
            k = token.search(text, n.end())
            if not k:
                break
            kind = k.group(0)
            pos = k.end()

        j = pos
        while j < len(text) and text[j].isspace():
            j += 1
        if j < len(text) and text[j] == "{":
            end = matching(text, j, "{", "}")
            items.append(Node(kind, text[j + 1:end], def_name))
            i = end + 1
        else:
            i = pos
    return items


def field_list(body, name):
    m = re.search(r"\b" + re.escape(name) + r"\s*\[", body)
    if not m:
        return None
    start = body.find("[", m.start())
    end = matching(body, start, "[", "]")
    return body[start + 1:end].strip()


def field_numbers(body, name, count):
    m = re.search(r"\b" + re.escape(name) + r"\b", body)
    if not m:
        return None
    rest = body[m.end():]
    if rest.lstrip().startswith("["):
        vals = field_list(body, name)
        return vals
    nums = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", rest)
    if len(nums) < count:
        return None
    return " ".join(nums[:count])


def field_number(body, name):
    return field_numbers(body, name, 1)


def field_word(body, name):
    m = re.search(r"\b" + re.escape(name) + r"\s+([A-Za-z_][A-Za-z0-9_]*)", body)
    return m.group(1) if m else None


def field_strings(body, name="string"):
    pat = re.compile(r"\b" + re.escape(name) + r'\s+("(?:\\.|[^"\\])*")')
    return pat.findall(body)


def indent(text, n=2):
    pad = " " * n
    return "\n".join(pad + line if line else line for line in text.splitlines())


def wrap_def(text, name):
    if not name:
        return text
    lines = text.splitlines()
    if not lines:
        return text
    lines[0] = f"DEF {name} " + lines[0]
    return "\n".join(lines)


def binding_is_per_vertex(binding):
    return binding in {"PER_VERTEX", "PER_VERTEX_INDEXED"}


def numeric_values(body, name):
    """Return all numeric values for a field, whether scalar or bracketed."""
    m = re.search(r"\b" + re.escape(name) + r"\b", body)
    if not m:
        return []

    rest = body[m.end():].lstrip()
    if rest.startswith("["):
        start = body.find("[", m.end())
        end = matching(body, start, "[", "]")
        rest = body[start + 1:end]

    return re.findall(
        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?",
        rest,
    )


def material_colors(material_body):
    if not material_body:
        return None, []
    for name in ("diffuseColor", "emissiveColor"):
        values = numeric_values(material_body, name)
        if values:
            return name, values
    return None, []


def material_appearance(material_body):
    """Create a VRML2 Material using the first value of each VRML1 field."""
    if not material_body:
        return None

    fields = []

    for src_name, dst_name, count in (
        ("diffuseColor", "diffuseColor", 3),
        ("emissiveColor", "emissiveColor", 3),
        ("specularColor", "specularColor", 3),
        ("shininess", "shininess", 1),
        ("transparency", "transparency", 1),
    ):
        values = numeric_values(material_body, src_name)
        if len(values) >= count:
            fields.append(f"{dst_name} {' '.join(values[:count])}")

    if not fields:
        return None

    return (
        "Appearance {\n"
        "  material Material {\n"
        + indent("\n".join(fields), 4)
        + "\n  }\n}"
    )


def color_node(state, geom_body):
    """Map non-OVERALL VRML1 material colors to a VRML2 Color node."""
    if state.material_binding == "OVERALL":
        return None, None, None

    _, values = material_colors(state.material)
    if len(values) <= 3:
        return None, None, None

    triples = [
        " ".join(values[i:i + 3])
        for i in range(0, len(values) - 2, 3)
    ]

    color = (
        "Color { color [\n"
        + indent(",\n".join(triples), 2)
        + "\n] }"
    )

    color_idx = field_list(geom_body, "materialIndex")
    per_vertex = binding_is_per_vertex(state.material_binding)
    return color, color_idx, per_vertex

def shape_hint_fields(state):
    """Translate VRML1 ShapeHints, including the VRML1 defaults.

    VRML1 defaults are UNKNOWN_ORDERING, UNKNOWN_SHAPE_TYPE, CONVEX,
    creaseAngle 0.5. The ancient converter maps those defaults to
    solid FALSE and creaseAngle 0.5 in VRML2.
    """
    body = state.shape_hints or ""

    ordering = field_word(body, "vertexOrdering") or "UNKNOWN_ORDERING"
    shape_type = field_word(body, "shapeType") or "UNKNOWN_SHAPE_TYPE"
    face_type = field_word(body, "faceType") or "CONVEX"
    crease = field_number(body, "creaseAngle") or "0.5"

    fields = []

    if ordering == "CLOCKWISE":
        fields.append("ccw FALSE")

    if shape_type != "SOLID":
        fields.append("solid FALSE")

    if face_type != "CONVEX":
        fields.append("convex FALSE")

    try:
        if float(crease) != 0.0:
            fields.append(f"creaseAngle {crease}")
    except ValueError:
        fields.append(f"creaseAngle {crease}")

    return fields

def transform_wrap(text, transforms):
    result = text
    for node in reversed(transforms):
        fields = []
        if node.kind == "Translation":
            v = field_numbers(node.body, "translation", 3)
            if v:
                fields.append(f"translation {v}")
        elif node.kind == "Rotation":
            v = field_numbers(node.body, "rotation", 4)
            if v:
                fields.append(f"rotation {v}")
        elif node.kind == "Scale":
            v = field_numbers(node.body, "scaleFactor", 3)
            if v:
                fields.append(f"scale {v}")
        elif node.kind == "Transform":
            for src, dst, count in (
                ("translation", "translation", 3),
                ("rotation", "rotation", 4),
                ("scaleFactor", "scale", 3),
                ("scaleOrientation", "scaleOrientation", 4),
                ("center", "center", 3),
            ):
                v = field_numbers(node.body, src, count)
                if v:
                    fields.append(f"{dst} {v}")
        if fields:
            result = "Transform {\n" + indent("\n".join(fields), 2) + "\n  children [\n" + indent(result, 4) + "\n  ]\n}"
    return result


def convert_indexed_face_set(node, state):
    body = node.body
    geom = ["IndexedFaceSet {"]

    if state.coord:
        pts = field_list(state.coord, "point")
        if pts is not None:
            geom.append("  coord Coordinate { point [\n" + indent(pts, 4) + "\n  ] }")

    idx = field_list(body, "coordIndex")
    if idx is not None:
        geom.append("  coordIndex [\n" + indent(idx, 4) + "\n  ]")

    color, color_idx, per_vertex = color_node(state, body)
    if color:
        geom.append("  color " + color)
        geom.append(f"  colorPerVertex {'TRUE' if per_vertex else 'FALSE'}")
        if color_idx is not None:
            geom.append("  colorIndex [\n" + indent(color_idx, 4) + "\n  ]")

    if state.normal:
        vec = field_list(state.normal, "vector")
        if vec is not None:
            geom.append("  normal Normal { vector [\n" + indent(vec, 4) + "\n  ] }")
        geom.append(f"  normalPerVertex {'TRUE' if binding_is_per_vertex(state.normal_binding) else 'FALSE'}")
        normal_idx = field_list(body, "normalIndex")
        if normal_idx is not None:
            geom.append("  normalIndex [\n" + indent(normal_idx, 4) + "\n  ]")

    tex_idx = field_list(body, "textureCoordIndex")
    if tex_idx is not None:
        geom.append("  texCoordIndex [\n" + indent(tex_idx, 4) + "\n  ]")

    for f in shape_hint_fields(state):
        geom.append("  " + f)
    geom.append("}")

    shape = ["Shape {"]
    appearance = material_appearance(state.material)
    if appearance and not color:
        shape.append("  appearance " + appearance)
    shape.append("  geometry " + "\n".join(geom))
    shape.append("}")
    result = "\n".join(shape)
    result = transform_wrap(result, state.transforms)
    return wrap_def(result, node.def_name)


def convert_indexed_line_set(node, state):
    body = node.body
    geom = ["IndexedLineSet {"]
    if state.coord:
        pts = field_list(state.coord, "point")
        if pts is not None:
            geom.append("  coord Coordinate { point [\n" + indent(pts, 4) + "\n  ] }")
    idx = field_list(body, "coordIndex")
    if idx is not None:
        geom.append("  coordIndex [\n" + indent(idx, 4) + "\n  ]")
    color, color_idx, per_vertex = color_node(state, body)
    if color:
        geom.append("  color " + color)
        geom.append(f"  colorPerVertex {'TRUE' if per_vertex else 'FALSE'}")
        if color_idx is not None:
            geom.append("  colorIndex [\n" + indent(color_idx, 4) + "\n  ]")
    geom.append("}")
    shape = ["Shape {"]
    appearance = material_appearance(state.material)
    if appearance and not color:
        shape.append("  appearance " + appearance)
    shape.append("  geometry " + "\n".join(geom))
    shape.append("}")
    result = transform_wrap("\n".join(shape), state.transforms)
    return wrap_def(result, node.def_name)


def convert_light(node):
    fields = []
    specs = {
        "DirectionalLight": (("direction", 3), ("color", 3), ("intensity", 1), ("on", 1)),
        "PointLight": (("location", 3), ("color", 3), ("intensity", 1), ("on", 1), ("radius", 1)),
    }
    for name, count in specs[node.kind]:
        v = field_numbers(node.body, name, count)
        if v:
            fields.append(f"{name} {v}")
    result = node.kind + " {\n" + indent("\n".join(fields), 2) + "\n}"
    return wrap_def(result, node.def_name)


def convert_camera(node):
    fields = []
    for src, dst, count in (
        ("position", "position", 3),
        ("orientation", "orientation", 4),
        ("heightAngle", "fieldOfView", 1),
    ):
        v = field_numbers(node.body, src, count)
        if v:
            fields.append(f"{dst} {v}")
    result = "Viewpoint {\n" + indent("\n".join(fields), 2) + "\n}"
    return wrap_def(result, node.def_name)


def convert_info(node):
    strings = field_strings(node.body)
    if not strings:
        return ""
    if node.def_name == "BackgroundColor":
        raw = strings[0].strip('"')
        nums = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", raw)
        if len(nums) >= 3:
            return f"Background {{ skyColor [ {' '.join(nums[:3])} ] }}"
    if node.def_name == "Viewer":
        return ""
    if node.def_name == "Title":
        return f"WorldInfo {{ title {strings[0]} }}"
    return "WorldInfo { info [\n" + indent(",\n".join(strings), 2) + "\n] }"


def collect_defs(text):
    """Collect every DEF node recursively so USE can be re-traversed."""
    defs = {}

    def visit(body):
        for item in scan_items(body):
            if isinstance(item, Node):
                if item.def_name:
                    defs[item.def_name] = item
                visit(item.body)

    visit(text)
    return defs


def process_item(item, state, defs, preserve_def=True):
    """Process one VRML1 item, mutating traversal state when appropriate."""
    if isinstance(item, Use):
        target = defs.get(item.name)
        if target is None:
            return f"# vr1tovr2: unresolved USE {item.name}"
        # VRML1 USE re-traverses the referenced node under current state.
        return process_item(target, state, defs, preserve_def=False)

    node = item
    kind = node.kind

    if kind == "Coordinate3":
        state.coord = node.body
        return ""
    if kind == "Normal":
        state.normal = node.body
        return ""
    if kind == "Material":
        state.material = node.body
        return ""
    if kind == "MaterialBinding":
        state.material_binding = field_word(node.body, "value") or "OVERALL"
        return ""
    if kind == "NormalBinding":
        state.normal_binding = (
            field_word(node.body, "value") or "PER_VERTEX_INDEXED"
        )
        return ""
    if kind == "ShapeHints":
        # A ShapeHints node replaces the complete ShapeHints state;
        # unspecified fields take that node's defaults.
        state.shape_hints = node.body
        return ""
    if kind in {"Translation", "Rotation", "Scale", "Transform"}:
        state.transforms.append(node)
        return ""

    return convert_node(
        node,
        state,
        defs,
        preserve_def=preserve_def,
    )


def convert_switch(node, state, defs, preserve_def=True):
    which = field_number(node.body, "whichChild") or "-1"
    children = []

    # Each Switch child is traversed from the state at entry to the Switch.
    for item in scan_items(node.body):
        child_state = state.clone()
        converted = process_item(item, child_state, defs)
        if converted:
            children.append(converted)

    result = (
        "Switch {\n"
        f"  whichChoice {which}\n"
        "  choice [\n"
        + indent("\n".join(children), 4)
        + "\n  ]\n}"
    )

    if preserve_def:
        return wrap_def(result, node.def_name)
    return result


def convert_separator(node, state, defs, preserve_def=True):
    local = state.clone()
    children = []

    for item in scan_items(node.body):
        converted = process_item(item, local, defs)
        if converted:
            children.append(converted)

    result = (
        "Group {\n"
        "  children [\n"
        + indent("\n".join(children), 4)
        + "\n  ]\n}"
    )

    if preserve_def:
        return wrap_def(result, node.def_name)
    return result


def convert_node(node, state, defs, preserve_def=True):
    original_def = node.def_name
    if not preserve_def and original_def:
        node = Node(node.kind, node.body, None)

    if node.kind == "Separator":
        return convert_separator(node, state, defs, preserve_def)

    if node.kind == "IndexedFaceSet":
        return convert_indexed_face_set(node, state)

    if node.kind == "IndexedLineSet":
        return convert_indexed_line_set(node, state)

    if node.kind in {"DirectionalLight", "PointLight"}:
        return convert_light(node)

    if node.kind == "PerspectiveCamera":
        return convert_camera(node)

    if node.kind == "Info":
        return convert_info(node)

    if node.kind == "Switch":
        return convert_switch(node, state, defs, preserve_def)

    if node.kind in {
        "Coordinate3",
        "Normal",
        "Material",
        "MaterialBinding",
        "NormalBinding",
        "ShapeHints",
        "Translation",
        "Rotation",
        "Scale",
        "Transform",
    }:
        return ""

    name = f" DEF {original_def}" if original_def else ""
    return f"# vr1tovr2: unsupported VRML 1.0 node {node.kind}{name}"

def convert_vrml1(text):
    clean = strip_comments(text)
    defs = collect_defs(clean)
    state = State()

    out = [
        "#VRML V2.0 utf8",
        "# Converted from VRML 1.0 by vr1tovr2.py",
    ]

    for item in scan_items(clean):
        converted = process_item(item, state, defs)
        if converted:
            out.append(converted)

    return "\n\n".join(out) + "\n"

def is_vrml1(data):
    first = data.splitlines()[0] if data else b""
    if first.startswith(b"\xef\xbb\xbf"):
        first = first[3:]
    return first.startswith(b"#VRML V1.0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", nargs="?", help="input file; default is stdin")
    parser.add_argument("-o", "--output", help="output file; default is stdout")
    add_version_argument(parser)
    args = parser.parse_args()

    try:
        data = Path(args.input_file).read_bytes() if args.input_file else sys.stdin.buffer.read()
    except OSError as exc:
        parser.exit(1, f"vr1tovr2: {exc}\n")

    if is_vrml1(data):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        try:
            output = convert_vrml1(text).encode("utf-8")
        except (ValueError, IndexError) as exc:
            parser.exit(1, f"vr1tovr2: conversion failed: {exc}\n")
    else:
        output = data

    try:
        if args.output:
            Path(args.output).write_bytes(output)
        else:
            sys.stdout.buffer.write(output)
    except OSError as exc:
        parser.exit(1, f"vr1tovr2: {exc}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
