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

"""
anemone.py

Generate LuisHPhi's "anemone" Coptic biform deltahedra.

Antiprism-style usage:
    anemone 5 | antiview
    anemone 7/3 | antiview
    anemone -v 100/21 > model.off
    anemone --allow-degenerate 3/2 | antiview

Input:
    n/d    d is the step (default 1), not a denominator.
           Values are not reduced; non-reduced inputs may be compounds.

Output:
    OFF geometry is written to stdout by default.
    -o FILE writes OFF output to FILE instead.
    -s writes OFF output using the standard filename n_d-anemone.off
       in the current directory.

Tolerance:
    -l LIM sets epsilon to 10**(-LIM), default 12 (1e-12).

Diagnostics:
    Errors are written to stderr.
    With -v / --verbose, geometry analysis is also written to stderr.

The ordinary family has:
    V = 4n
    E = 12n
    F = 8n

Edge length is normalized to 1.
"""

import argparse
import math
import sys
from pathlib import Path

from anti_common import (
    DEFAULT_LIMIT, DEFAULT_EPSILON, add_version_argument,
    POLYGON_NOTATION_HELP, POLYGON_NOTATION_METAVAR,
)


EPSILON = DEFAULT_EPSILON


def parse_parameter(text):
    """Parse n or n/d notation, with d defaulting to 1; do not reduce."""
    parts = text.split("/")

    if len(parts) == 1:
        n = int(parts[0])
        d = 1
    elif len(parts) == 2 and parts[0] and parts[1]:
        n = int(parts[0])
        d = int(parts[1])
    else:
        raise ValueError("expected n or n/d")

    return n, d


def generate_vertices(n, d):
    if n < 3:
        raise ValueError("n must be at least 3")
    if d <= 0 or d >= n:
        raise ValueError("d must satisfy 0 < d < n")
    alpha = math.pi * d / n
    s = math.sin(alpha)
    c = math.cos(alpha)

    if abs(s) < EPSILON:
        raise ValueError("degenerate sine")

    # One ring radius is forced by its unit star-polygon edges:
    #
    #     2 R sin(alpha) = 1
    #
    R = 1.0 / (2.0 * s)

    # Closed-form solution for b^2.
    disc = 16.0 * s**4 - 28.0 * s**2 + 13.0
    if disc < -EPSILON:
        raise ValueError("no real geometric solution")
    disc = max(disc, 0.0)

    candidates = (
        (4.0 * s * s - math.sqrt(disc) - 3.0) / (8.0 * s * s),
        (4.0 * s * s + math.sqrt(disc) - 3.0) / (8.0 * s * s),
    )

    solution = None

    for b2 in candidates:
        if b2 <= EPSILON or abs(c) < EPSILON:
            continue

        S2 = (0.25 - b2) / (c * c)
        if S2 < -EPSILON:
            continue

        b = math.sqrt(b2)
        S = math.sqrt(max(S2, 0.0))
        a = S * R * c / b

        solution = (R, S, a, b)
        break

    if solution is None:
        raise ValueError("no physical four-ring solution for this n/d")

    R, S, a, b = solution

    # Ring phase classes, in units of pi/n.
    phases = [
        0,
        (n - d) & 1,
        d & 1,
        n & 1,
    ]

    # Four rings: S-, R-, R+, S+
    rings = [
        (S, -b, phases[0]),
        (R, -a, phases[1]),
        (R,  a, phases[2]),
        (S,  b, phases[3]),
    ]

    vertices = []

    for radius, y, phase_units in rings:
        phase = phase_units * math.pi / n

        for j in range(n):
            angle = phase + 2.0 * math.pi * j / n
            vertices.append(
                (
                    radius * math.cos(angle),
                    y,
                    radius * math.sin(angle),
                )
            )

    return vertices, {
        "alpha": alpha,
        "R": R,
        "S": S,
        "a": a,
        "b": b,
        "disc": disc,
        "phases": phases,
    }


def distance2(p, q):
    return (
        (p[0] - q[0]) ** 2
        + (p[1] - q[1]) ** 2
        + (p[2] - q[2]) ** 2
    )


def coincident_pairs(vertices, tol=None):
    if tol is None:
        tol = EPSILON
    tol2 = tol * tol
    pairs = []

    for i in range(len(vertices)):
        for j in range(i):
            if distance2(vertices[i], vertices[j]) < tol2:
                pairs.append((j, i))

    return pairs


def unit_edges(vertices, tol=None):
    if tol is None:
        tol = EPSILON
    lo = (1.0 - tol) ** 2
    hi = (1.0 + tol) ** 2
    edges = set()

    for i in range(len(vertices)):
        for j in range(i + 1, len(vertices)):
            d2 = distance2(vertices[i], vertices[j])

            if lo <= d2 <= hi:
                edges.add((i, j))

    return edges


def triangular_faces(vertex_count, edges):
    adjacency = [set() for _ in range(vertex_count)]

    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)

    faces = []

    for a in range(vertex_count):
        for b in adjacency[a]:
            if b <= a:
                continue

            for c in adjacency[a].intersection(adjacency[b]):
                if c > b:
                    faces.append((a, b, c))

    return faces


def orient_faces(vertices, faces):
    """
    Orient neighboring faces oppositely along each shared edge.

    These are self-intersecting toroids, so there is no globally meaningful
    "outside", but the mesh can still be consistently orientable.
    """
    edge_faces = {}

    for fi, face in enumerate(faces):
        a, b, c = face

        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_faces.setdefault(key, []).append(fi)

    neighbors = [[] for _ in faces]

    for key, face_list in edge_faces.items():
        if len(face_list) == 2:
            f0, f1 = face_list
            neighbors[f0].append((f1, key))
            neighbors[f1].append((f0, key))

    oriented = [None] * len(faces)

    def edge_direction(face, u, v):
        a, b, c = face
        cycle = ((a, b), (b, c), (c, a))

        if (u, v) in cycle:
            return 1
        if (v, u) in cycle:
            return -1

        raise RuntimeError("edge not found in face")

    for start in range(len(faces)):
        if oriented[start] is not None:
            continue

        oriented[start] = faces[start]
        stack = [start]

        while stack:
            fi = stack.pop()
            face = oriented[fi]

            for fj, (u, v) in neighbors[fi]:
                direction_i = edge_direction(face, u, v)

                if oriented[fj] is None:
                    other = faces[fj]
                    direction_j = edge_direction(other, u, v)

                    if direction_j == direction_i:
                        other = (other[0], other[2], other[1])

                    oriented[fj] = other
                    stack.append(fj)

    return oriented


def write_off(fp, vertices, faces, comment=None):
    fp.write("OFF\n")

    if comment:
        fp.write(f"# {comment}\n")

    fp.write(f"{len(vertices)} {len(faces)} 0\n")

    for x, y, z in vertices:
        fp.write(f"{x:.15g} {y:.15g} {z:.15g}\n")

    for a, b, c in faces:
        fp.write(f"3 {a} {b} {c}\n")


def output_off(vertices, faces, n, d, output=None, save=False):
    """Write OFF to stdout or to the selected file."""

    if save:
        destination = Path.cwd() / f"{n}_{d}-anemone.off"
    elif output:
        destination = Path(output)
    else:
        destination = None

    comment = f"{n}/{d}-gonal Coptic biform deltahedron"

    if destination is None:
        write_off(sys.stdout, vertices, faces, comment=comment)
        return

    try:
        with destination.open("w", encoding="utf-8", newline="\n") as fp:
            write_off(fp, vertices, faces, comment=comment)
    except OSError as exc:
        sys.exit(f"anemone: cannot write {destination}: {exc}")


def verbose_report(n, d, params, vertices, edges, faces, coincidences, normal):
    fp = sys.stderr

    print(f"{n}/{d}", file=fp)
    print(
        f"  alpha = {math.degrees(params['alpha']):.12g} degrees",
        file=fp,
    )
    print(f"  epsilon = {EPSILON:.12g}", file=fp)
    print(f"  R = {params['R']:.15g}", file=fp)
    print(f"  S = {params['S']:.15g}", file=fp)
    print(f"  a = {params['a']:.15g}", file=fp)
    print(f"  b = {params['b']:.15g}", file=fp)
    print(
        f"  V/E/F = {len(vertices)}/{len(edges)}/{len(faces)}",
        file=fp,
    )
    print(
        f"  expected normal V/E/F = {4*n}/{12*n}/{8*n}",
        file=fp,
    )
    print(
        f"  coincident vertex pairs = {len(coincidences)}",
        file=fp,
    )

    if coincidences:
        print("  coincidences:", file=fp)

        for a, b in coincidences[:20]:
            print(f"    {a} == {b}", file=fp)

        if len(coincidences) > 20:
            print(
                f"    ... {len(coincidences) - 20} more",
                file=fp,
            )

    print(
        "  status = " + ("normal member" if normal else "DEGENERATE / SPECIAL"),
        file=fp,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate Coptic biform deltahedra as OFF on stdout."
        )
    )
    parser.add_argument(
        "parameter",
        metavar=POLYGON_NOTATION_METAVAR,
        help=POLYGON_NOTATION_HELP,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="write geometry analysis to stderr",
    )
    parser.add_argument(
        "-l", "--limit", type=int, default=DEFAULT_LIMIT, metavar="LIM",
        help="epsilon as 10**-LIM (default: %(default)s)",
    )
    parser.add_argument(
        "--allow-degenerate",
        action="store_true",
        help=(
            "emit OFF even if coincident vertices or unexpected counts occur"
        ),
    )

    output_group = parser.add_mutually_exclusive_group()

    output_group.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="write OFF output to FILE instead of stdout",
    )

    output_group.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="write OFF output as n_d-anemone.off in the current directory",
    )

    add_version_argument(parser)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("-l must be nonnegative")

    global EPSILON
    EPSILON = 10.0 ** (-args.limit)

    try:
        n, d = parse_parameter(args.parameter)
    except (ValueError, TypeError) as exc:
        parser.error(f"invalid n/d '{args.parameter}': {exc}")

    try:
        vertices, params = generate_vertices(n, d)
    except ValueError as exc:
        print(f"anemone: {n}/{d}: {exc}", file=sys.stderr)
        return 2

    coincidences = coincident_pairs(vertices)
    edges = unit_edges(vertices)
    faces = triangular_faces(len(vertices), edges)

    normal = (
        not coincidences
        and len(vertices) == 4 * n
        and len(edges) == 12 * n
        and len(faces) == 8 * n
    )

    if args.verbose:
        verbose_report(
            n,
            d,
            params,
            vertices,
            edges,
            faces,
            coincidences,
            normal,
        )

    if not normal and not args.allow_degenerate:
        print(
            f"anemone: {n}/{d}: degenerate/special model; "
            "use --allow-degenerate to emit it",
            file=sys.stderr,
        )
        return 1

    faces = orient_faces(vertices, faces)

    output_off(
        vertices,
        faces,
        n,
        d,
        output=args.output,
        save=args.save,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
