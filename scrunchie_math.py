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

#!/usr/bin/python3

# ChatGPT assisted utility script

"""
scrunchie_math.py

Generate LuisHPhi's "scrunchie" Coptic biform deltahedra directly from
the parametrization in his GeoGebra construction.

Usage:
    scrunchie_math 6/3 4 | antiview
    scrunchie_math 10/4 7 | antiview
    scrunchie_math 10/4 -L
    scrunchie_math 20/7 8 -v | antiview
    scrunchie_math 10/4 7 -o model.off
    scrunchie_math 10/4 7 -s

Input:
    n/d    d is the step (default 1), not a denominator.
           Values are not reduced.
    j      Luis's GeoGebra j value.

Output:
    OFF geometry is written to stdout by default.

Options:
    -L, --list
           list all j values allowed by Luis's validity conditions,
           including negative values and j=0, then exit

    -l LIM, --limit LIM
           minimum distance for unique vertex locations as negative exponent
           (default: 12 giving 1e-12)

    -o FILE, --output FILE
           write OFF output to FILE instead of stdout

    -s, --save
           write OFF output using:
               n_d_jJ-scrunchie-luis.off

    -v, --verbose
           write parameter and mesh analysis to stderr

The formulas below are transcribed from LuisHPhi's
"Scrunchies Parametrization.ggb".
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
    """Parse n or n/d without reducing the values."""
    parts = text.split("/")

    if len(parts) == 1:
        n = int(parts[0])
        d = 1
    elif len(parts) == 2 and parts[0] and parts[1]:
        n = int(parts[0])
        d = int(parts[1])
    else:
        raise ValueError("expected n or n/d")

    if n < 3:
        raise ValueError("n must be at least 3")
    if d <= 0:
        raise ValueError("d must be positive")

    return n, d


def geogebra_valid(n, d, j):
    """Luis's epsilon validity test from the GeoGebra construction."""
    angle = d * math.pi / n
    cosine = math.cos(angle)

    p1 = (
        1.0 / 3.0 < cosine
        and -d / 2.0 < j < d
    )

    p2 = (
        cosine < 1.0 / 3.0
        and d + 2 * j < 2 * n
        and d < j
    )

    p3 = (
        1.0 / 4.0 < cosine < 1.0 / 3.0
        and n < d + 2 * j
        and j <= d
    )

    return p1 or p2 or p3


def cot(x):
    """Cotangent."""
    value = math.tan(x)

    if abs(value) < EPSILON:
        raise ValueError("undefined cotangent in parametrization")

    return 1.0 / value


def luis_parameters(n, d, j):
    """Evaluate Luis's rho, sigma, h, t, c and r formulas."""
    if not geogebra_valid(n, d, j):
        raise ValueError(
            f"{n}/{d}, j={j} is outside Luis's GeoGebra validity conditions"
        )

    dpi_n = d * math.pi / n
    half_dpi_n = d * math.pi / (2 * n)
    jpi_n = j * math.pi / n
    djpi_n = (d + j) * math.pi / n
    half_jpi_n = j * math.pi / (2 * n)
    half_djpi_n = (d + j) * math.pi / (2 * n)

    # GeoGebra boolean a = (j < d). In the exponent (-1)^(a+1),
    # True acts as 1 and False as 0.
    a = 1 if j < d else 0

    radicand = (
        math.sin(dpi_n) ** 2
        - (
            4
            * (1 - 2 * math.cos(dpi_n))
            * math.sin(jpi_n)
            * math.sin(djpi_n)
        )
    )

    if radicand < -EPSILON:
        raise ValueError(
            f"negative rho radicand ({radicand:.12g})"
        )

    radicand = max(0.0, radicand)

    denominator = (
        2
        * math.cos(half_dpi_n) ** 2
        * (
            math.sin((d + 2 * j) * math.pi / (2 * n))
            - math.sin(half_dpi_n)
        )
    )

    if abs(denominator) < EPSILON:
        raise ValueError("singular rho denominator")

    rho = (
        (
            (-1) ** (a + 1)
            * math.cos(half_dpi_n)
            * math.sqrt(radicand)
        )
        - (
            math.sin(half_dpi_n)
            * (
                math.cos(jpi_n)
                + math.cos(djpi_n)
            )
        )
    ) / denominator

    sigma = (
        math.tan(half_jpi_n)
        * cot(half_djpi_n)
        * rho
    )

    first = (1 + sigma) * (1 + rho)
    second = (1 - sigma) * (1 - rho)

    if first < -EPSILON or second < -EPSILON:
        raise ValueError(
            "invalid square-root term in h/t parametrization"
        )

    first = math.sqrt(max(0.0, first))
    second = math.sqrt(max(0.0, second))

    h = 0.5 * (first - second)
    t = 0.5 * (first + second)

    radius_denominator = (
        2 - 2 * math.cos(dpi_n)
    )

    if radius_denominator <= EPSILON:
        raise ValueError("singular orbit radius")

    c2 = (1 - h * h) / radius_denominator
    r2 = (1 - t * t) / radius_denominator

    if c2 < -EPSILON or r2 < -EPSILON:
        raise ValueError("invalid orbit radius")

    c = math.sqrt(max(0.0, c2))
    r = math.sqrt(max(0.0, r2))

    return {
        "rho": rho,
        "sigma": sigma,
        "h": h,
        "t": t,
        "c": c,
        "r": r,
    }


def add_unique(vertices, point, tol=None):
    """Append point unless a numerically identical point is already present."""
    if tol is None:
        tol = EPSILON

    tol2 = tol * tol

    for old in vertices:
        if (
            (point[0] - old[0]) ** 2
            + (point[1] - old[1]) ** 2
            + (point[2] - old[2]) ** 2
            <= tol2
        ):
            return

    vertices.append(point)


def generate_vertices(n, d, j, params):
    """
    Generate the two GeoGebra vertex lists l1 and l2.

    GeoGebra nests the k sequence inside g=1..gcd(n,d). Repeated
    coordinates from the compound construction are merged here because
    an OFF vertex list should contain each geometric point once.
    """
    h = params["h"]
    t = params["t"]
    c = params["c"]
    r = params["r"]

    vertices = []
    compound = math.gcd(n, d)

    for g in range(1, compound + 1):
        for k in range(2 * n):
            angle = (
                (d * k + 2 * g)
                * math.pi
                / n
            )

            point = (
                c * math.cos(angle),
                c * math.sin(angle),
                0.5 * ((-1) ** k) * h,
            )

            add_unique(vertices, point)

    for g in range(1, compound + 1):
        for k in range(2 * n):
            angle = (
                (d * k + j + 2 * g)
                * math.pi
                / n
            )

            point = (
                r * math.cos(angle),
                r * math.sin(angle),
                0.5 * ((-1) ** (k + 1)) * t,
            )

            add_unique(vertices, point)

    return vertices


def distance2(a, b):
    return (
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
    )


def unit_edges(vertices):
    """Return all vertex pairs at unit distance."""
    lo = (1.0 - EPSILON) ** 2
    hi = (1.0 + EPSILON) ** 2
    edges = set()

    for i in range(len(vertices)):
        for j in range(i + 1, len(vertices)):
            value = distance2(vertices[i], vertices[j])

            if lo <= value <= hi:
                edges.add((i, j))

    return edges


def triangular_faces(vertex_count, edges):
    """Return all triangular 3-cliques in the unit-edge graph."""
    adjacency = [set() for _ in range(vertex_count)]

    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)

    faces = []

    for a in range(vertex_count):
        for b in adjacency[a]:
            if b <= a:
                continue

            common = adjacency[a].intersection(adjacency[b])

            for c in common:
                if c > b:
                    faces.append((a, b, c))

    return faces, adjacency


def edge_face_counts(faces):
    counts = {}

    for a, b, c in faces:
        for u, v in ((a, b), (b, c), (c, a)):
            edge = (u, v) if u < v else (v, u)
            counts[edge] = counts.get(edge, 0) + 1

    return counts


def orient_faces(faces):
    """Orient adjacent faces oppositely along their common edge."""
    edge_faces = {}

    for index, face in enumerate(faces):
        a, b, c = face

        for u, v in ((a, b), (b, c), (c, a)):
            edge = (u, v) if u < v else (v, u)
            edge_faces.setdefault(edge, []).append(index)

    neighbors = [[] for _ in faces]

    for edge, owners in edge_faces.items():
        if len(owners) == 2:
            first, second = owners
            neighbors[first].append((second, edge))
            neighbors[second].append((first, edge))

    oriented = [None] * len(faces)

    def direction(face, u, v):
        a, b, c = face

        if (u, v) in ((a, b), (b, c), (c, a)):
            return 1

        if (v, u) in ((a, b), (b, c), (c, a)):
            return -1

        raise RuntimeError("edge not found in face")

    for start in range(len(faces)):
        if oriented[start] is not None:
            continue

        oriented[start] = faces[start]
        stack = [start]

        while stack:
            current = stack.pop()
            face = oriented[current]

            for other_index, edge in neighbors[current]:
                if oriented[other_index] is not None:
                    continue

                other = faces[other_index]
                u, v = edge

                if direction(face, u, v) == direction(other, u, v):
                    other = (other[0], other[2], other[1])

                oriented[other_index] = other
                stack.append(other_index)

    return oriented


def mesh_data(n, d, j):
    """Generate and analyze one Luis-parametrized model."""
    params = luis_parameters(n, d, j)
    vertices = generate_vertices(n, d, j, params)
    edges = unit_edges(vertices)
    faces, adjacency = triangular_faces(len(vertices), edges)

    return {
        "params": params,
        "vertices": vertices,
        "edges": edges,
        "faces": faces,
        "adjacency": adjacency,
    }


def write_off(fp, n, d, j, vertices, faces):
    fp.write("OFF\n")
    fp.write(
        f"# LuisHPhi scrunchie {n}/{d}, j={j}\n"
    )
    fp.write(f"{len(vertices)} {len(faces)} 0\n")

    for x, y, z in vertices:
        fp.write(f"{x:.15g} {y:.15g} {z:.15g}\n")

    for a, b, c in faces:
        fp.write(f"3 {a} {b} {c}\n")


def standard_filename(n, d, j):
    return f"{n}_{d}_j{j}-scrunchie-luis.off"


def output_model(
    n,
    d,
    j,
    vertices,
    faces,
    output=None,
    save=False,
):
    if save:
        destination = Path.cwd() / standard_filename(n, d, j)
    elif output:
        destination = Path(output)
    else:
        destination = None

    if destination is None:
        write_off(
            sys.stdout,
            n,
            d,
            j,
            vertices,
            faces,
        )
        return

    try:
        with destination.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as fp:
            write_off(
                fp,
                n,
                d,
                j,
                vertices,
                faces,
            )
    except OSError as exc:
        sys.exit(
            f"scrunchie_math: cannot write {destination}: {exc}"
        )


def valid_j_values(n, d):
    """
    Return all integer j values allowed by Luis's validity conditions.

    Unlike the original GeoGebra slider, this search includes negative
    values and j=0. The inequalities themselves bound j to a finite
    interval, so no arbitrary periodic search range is needed.
    """
    values = []

    # The three validity branches imply:
    #
    #   -d/2 < j < d
    #    d   < j < n-d/2
    #   (n-d)/2 < j <= d
    #
    # Their union lies inside this finite interval.
    lower = math.floor(-d / 2.0) - 1
    upper = math.ceil(max(d, n - d / 2.0)) + 1

    for j in range(lower, upper + 1):
        if not geogebra_valid(n, d, j):
            continue

        try:
            luis_parameters(n, d, j)
        except ValueError:
            continue

        values.append(j)

    return values


def list_j_values(n, d):
    values = valid_j_values(n, d)

    print(
        f"{n}/{d}: {len(values)} valid "
        f"j value{'' if len(values) == 1 else 's'}"
    )

    if values:
        print("  j =", " ".join(str(value) for value in values))


def verbose_report(n, d, j, model):
    params = model["params"]
    vertices = model["vertices"]
    edges = model["edges"]
    faces = model["faces"]
    adjacency = model["adjacency"]
    counts = edge_face_counts(faces)

    print(
        f"scrunchie_math {n}/{d}, j={j}",
        file=sys.stderr,
    )
    print(
        f"  gcd(n,d) = {math.gcd(n, d)}",
        file=sys.stderr,
    )
    print(
        f"  epsilon = {EPSILON:.12g}",
        file=sys.stderr,
    )
    print(
        f"  rho   = {params['rho']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  sigma = {params['sigma']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  h     = {params['h']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  t     = {params['t']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  c     = {params['c']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  r     = {params['r']:.15g}",
        file=sys.stderr,
    )
    print(
        f"  V/E/F = "
        f"{len(vertices)}/{len(edges)}/{len(faces)}",
        file=sys.stderr,
    )

    degrees = sorted(
        {len(neighbors) for neighbors in adjacency}
    )

    print(
        "  vertex degrees = "
        + ", ".join(str(value) for value in degrees),
        file=sys.stderr,
    )

    incidences = sorted(set(counts.values()))

    print(
        "  edge face-incidences = "
        + ", ".join(str(value) for value in incidences),
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate LuisHPhi scrunchies using his GeoGebra construction."
        )
    )

    parser.add_argument(
        "parameter",
        metavar=POLYGON_NOTATION_METAVAR,
        help=POLYGON_NOTATION_HELP,
    )

    parser.add_argument(
        "j",
        nargs="?",
        type=int,
        help="Luis's GeoGebra j value",
    )

    parser.add_argument(
        "-L",
        "--list",
        action="store_true",
        help=(
            "list all j values allowed by Luis's validity conditions, "
            "including negative values and j=0, then exit"
        ),
    )

    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        metavar="LIM",
        help=(
            "minimum distance for unique vertex locations as negative "
            "exponent (default: 12 giving 1e-12)"
        ),
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="write construction and mesh analysis to stderr",
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
        help=(
            "write OFF output using the standard Luis "
            "scrunchie filename in the current directory"
        ),
    )

    add_version_argument(parser)

    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit must be nonnegative")

    global EPSILON
    EPSILON = 10.0 ** (-args.limit)

    try:
        n, d = parse_parameter(args.parameter)
    except (ValueError, TypeError) as exc:
        parser.error(
            f"invalid n/d '{args.parameter}': {exc}"
        )

    if args.list:
        list_j_values(n, d)
        return 0

    if args.j is None:
        parser.error("j is required unless --list is used")

    try:
        model = mesh_data(n, d, args.j)
    except ValueError as exc:
        print(
            f"scrunchie_math: {n}/{d}, j={args.j}: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.verbose:
        verbose_report(n, d, args.j, model)

    faces = orient_faces(model["faces"])

    output_model(
        n,
        d,
        args.j,
        model["vertices"],
        faces,
        output=args.output,
        save=args.save,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
