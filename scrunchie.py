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
scrunchie.py

Generate LuisHPhi's "scrunchie" Coptic biform deltahedra.

Usage:
    scrunchie 7/2 | antiview
    scrunchie 10/4 | antiview
    scrunchie 10/4 -i 2 | antiview
    scrunchie 10/5 -v | antiview
    scrunchie 20/7 -L
    scrunchie 10/4 -o model.off
    scrunchie 10/4 -i 2 -s

Input:
    n/d    d is the step (default 1), not a denominator.
           Values are not reduced. Compounds depend on gcd(n,d), so
           10/4 and 5/2 are intentionally different inputs.

Output:
    OFF geometry is written to stdout by default.

Options:
    -i N, --isomer N
           select isomer N; default is 1

    -L, --list
           list available isomers for the specified n/d and exit

    -l LIM, --limit LIM
           minimum distance for unique vertex locations as negative exponent
           (default: 12 giving 1e-12)

    -o FILE, --output FILE
           write OFF output to FILE instead of stdout

    -s, --save
           write OFF output using the standard filename:
               n_dd-scrunchie-NNN.off (for two-digit n)
           where the connection step is padded to the width of n,
           and NNN is the zero-padded three-digit isomer number.

    -v, --verbose
           write analysis to stderr

The construction uses two 2n-vertex orbits.  For each orbit,

    c = sqrt((1-h^2) / (2 - 2*cos(d*pi/n)))

and h is solved so that the cross-orbit edges are also unit length.
Different valid cross-orbit step patterns give the isomers.
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

# Distance-spectrum deduplication is an internal numerical fingerprint test,
# not the user-selectable geometric epsilon.  Congruent realizations can
# accumulate more floating-point noise than direct geometric predicates.
CONGRUENCE_TOL = 1.0e-7


def parse_parameter(text):
    """Parse n or n/d without reducing it; d is a connection step."""
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
    if d >= n:
        raise ValueError("d must be less than n")

    return n, d


def orbit_radius(h, n, d):
    """Return c for an orbit with height parameter h and unit orbit edges."""
    denom = 2.0 - 2.0 * math.cos(d * math.pi / n)

    if denom <= EPSILON:
        raise ValueError("degenerate orbit angle")

    value = (1.0 - h * h) / denom

    if value < -EPSILON:
        raise ValueError("invalid orbit height")

    return math.sqrt(max(0.0, value))


def make_vertices(n, d, h1, h2, phase_step=0, sign_flip=0):
    """
    Build the two 2n-vertex orbits.

    For odd d, a single orbit occupies all 2n angular positions, with
    alternating height sign.

    For even d, an orbit occupies n angular positions and contains both
    height signs at every position.  This automatically represents the
    compound-base cases without reducing n/d.
    """
    vertices = []

    for orbit_index, h in enumerate((h1, h2)):
        c = orbit_radius(h, n, d)
        phase = (phase_step if orbit_index else 0) * math.pi / n

        if d & 1:
            for q in range(2 * n):
                angle = q * math.pi / n + phase
                sign = 1 if (q & 1) == 0 else -1

                if orbit_index and sign_flip:
                    sign = -sign

                vertices.append(
                    (
                        c * math.cos(angle),
                        c * math.sin(angle),
                        0.5 * sign * h,
                    )
                )
        else:
            for q in range(n):
                angle = 2.0 * q * math.pi / n + phase

                for sign in (1, -1):
                    vertices.append(
                        (
                            c * math.cos(angle),
                            c * math.sin(angle),
                            0.5 * sign * h,
                        )
                    )

    return vertices


def distance2(a, b):
    return (
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
    )


def unit_edges(vertices):
    lo = (1.0 - EPSILON) ** 2
    hi = (1.0 + EPSILON) ** 2
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

    return faces, adjacency


def count_parts(adjacency):
    """Return the number of connected components in the mesh graph."""
    unseen = set(range(len(adjacency)))
    parts = 0

    while unseen:
        start = next(iter(unseen))
        unseen.remove(start)
        stack = [start]
        parts += 1

        while stack:
            a = stack.pop()

            for b in adjacency[a]:
                if b in unseen:
                    unseen.remove(b)
                    stack.append(b)

    return parts


def edge_face_counts(faces):
    counts = {}

    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edge = (a, b) if a < b else (b, a)
            counts[edge] = counts.get(edge, 0) + 1

    return counts


def coincident_vertices(vertices):
    tol2 = EPSILON * EPSILON

    for i in range(len(vertices)):
        for j in range(i):
            if distance2(vertices[i], vertices[j]) <= tol2:
                return True

    return False


def model_is_valid(vertices, n):
    edges = unit_edges(vertices)
    faces, adjacency = triangular_faces(len(vertices), edges)

    if len(vertices) != 4 * n:
        return None

    if len(edges) != 12 * n:
        return None

    if len(faces) != 8 * n:
        return None

    if any(len(neighbors) != 6 for neighbors in adjacency):
        return None

    if coincident_vertices(vertices):
        return None

    ef = edge_face_counts(faces)

    if len(ef) != len(edges):
        return None

    if any(count != 2 for count in ef.values()):
        return None

    parts = count_parts(adjacency)

    return edges, faces, adjacency, parts


def cross_equation_value(p, n, d, same_step, opposite_step):
    """
    Reduce the two cross-edge equations to one variable.

    Let p = h1/sqrt(1-h1^2) and q = h2/sqrt(1-h2^2).
    Subtracting the same-sign and opposite-sign unit-edge equations gives

        p*q = 2*(cos(B)-cos(A)) / D

    where A is the same-sign angular step, B the opposite-sign step, and

        D = 2 - 2*cos(d*pi/n).

    Substitution leaves one scalar equation in p.
    """
    D = 2.0 - 2.0 * math.cos(d * math.pi / n)

    angle_same = same_step * math.pi / n
    angle_opp = opposite_step * math.pi / n

    L = (
        2.0
        * (math.cos(angle_opp) - math.cos(angle_same))
        / D
    )

    if L <= 0.0 or p <= 0.0:
        return None

    q = L / p

    h1 = p / math.sqrt(1.0 + p * p)
    h2 = q / math.sqrt(1.0 + q * q)

    c1 = 1.0 / math.sqrt(D * (1.0 + p * p))
    c2 = 1.0 / math.sqrt(D * (1.0 + q * q))

    value = (
        c1 * c1
        + c2 * c2
        - 2.0 * c1 * c2 * math.cos(angle_same)
        + 0.25 * (h1 - h2) ** 2
        - 1.0
    )

    return value, h1, h2


def solve_heights(n, d, same_step, opposite_step):
    """Find positive height-pair solutions for a cross-step pair."""
    roots = []

    # A logarithmic scan is robust over the full 0 < h < 1 range.
    log_min = -13.815510557964274   # ln(1e-6)
    log_max = 13.815510557964274    # ln(1e6)
    samples = 220

    previous_p = None
    previous_value = None

    for index in range(samples + 1):
        exponent = log_min + (log_max - log_min) * index / samples
        p = math.exp(exponent)

        result = cross_equation_value(
            p, n, d, same_step, opposite_step
        )

        if result is None:
            continue

        value = result[0]

        if previous_value is not None:
            if value == 0.0 or previous_value * value < 0.0:
                lo = previous_p
                hi = p
                flo = previous_value

                # Geometric bisection is appropriate because p is scanned
                # logarithmically over many orders of magnitude.
                for _ in range(80):
                    mid = math.sqrt(lo * hi)
                    mid_result = cross_equation_value(
                        mid, n, d, same_step, opposite_step
                    )

                    if mid_result is None:
                        break

                    fm = mid_result[0]

                    if abs(fm) < EPSILON:
                        lo = hi = mid
                        break

                    if flo * fm <= 0.0:
                        hi = mid
                    else:
                        lo = mid
                        flo = fm

                p_root = math.sqrt(lo * hi)
                root_result = cross_equation_value(
                    p_root, n, d, same_step, opposite_step
                )

                if root_result is not None:
                    _, h1, h2 = root_result

                    if (
                        0.0 < h1 < 1.0
                        and 0.0 < h2 < 1.0
                        and not any(
                            abs(h1 - a) < EPSILON
                            and abs(h2 - b) < EPSILON
                            for a, b in roots
                        )
                    ):
                        roots.append((h1, h2))

        previous_p = p
        previous_value = value

    return roots


def distance_spectrum(vertices):
    """Return the sorted multiset of all pairwise vertex distances."""
    values = []

    for i in range(len(vertices)):
        for j in range(i):
            values.append(
                math.sqrt(distance2(vertices[i], vertices[j]))
            )

    values.sort()
    return values


def spectra_match(first, second, tol=CONGRUENCE_TOL):
    """
    Compare two distance spectra with an internal numerical tolerance.

    This is deliberately separate from the user-selectable geometric
    epsilon.  It is only used to recognize congruent realizations reached
    through different numerical paths.
    """
    if len(first) != len(second):
        return False

    return all(
        abs(a - b) <= tol
        for a, b in zip(first, second)
    )


def discover_isomers(n, d):
    """
    Discover valid scrunchie isomers for n/d.

    Each valid model has one same-sign cross-orbit angular separation and
    one opposite-sign separation, measured in units of pi/n.  We enumerate
    those discrete possibilities, solve the two orbit heights, construct the
    unit-distance graph, and keep only connected genus-1 biform triangulations
    with V/E/F = 4n/12n/8n.

    Congruent solutions generated through different phase/sign descriptions
    are merged.
    """
    found = []

    for same_step in range(1, n + 1):
        for opposite_step in range(0, same_step):
            height_pairs = solve_heights(
                n, d, same_step, opposite_step
            )

            for h1, h2 in height_pairs:
                phase_steps = (0, 1)

                if d & 1:
                    sign_flips = (0, 1)
                else:
                    sign_flips = (0,)

                for phase_step in phase_steps:
                    for sign_flip in sign_flips:
                        vertices = make_vertices(
                            n,
                            d,
                            h1,
                            h2,
                            phase_step=phase_step,
                            sign_flip=sign_flip,
                        )

                        validation = model_is_valid(vertices, n)

                        if validation is None:
                            continue

                        edges, faces, adjacency, parts = validation
                        spectrum = distance_spectrum(vertices)

                        candidate = {
                            "vertices": vertices,
                            "edges": edges,
                            "faces": faces,
                            "adjacency": adjacency,
                            "parts": parts,
                            "h1": h1,
                            "h2": h2,
                            "c1": orbit_radius(h1, n, d),
                            "c2": orbit_radius(h2, n, d),
                            "same_step": same_step,
                            "opposite_step": opposite_step,
                            "phase_step": phase_step,
                            "sign_flip": sign_flip,
                        }

                        # Merge numerically congruent realizations.
                        #
                        # Candidate generation remains completely independent
                        # of Luis's n/d/j parametrization. Congruence is tested
                        # only from the generated vertex geometry.
                        duplicate_index = None

                        for index, item in enumerate(found):
                            if spectra_match(spectrum, item["spectrum"]):
                                duplicate_index = index
                                break

                        if duplicate_index is None:
                            found.append(
                                {
                                    "spectrum": spectrum,
                                    "model": candidate,
                                }
                            )
                        else:
                            old = found[duplicate_index]["model"]

                            old_key = (
                                -old["same_step"],
                                -old["opposite_step"],
                                old["phase_step"],
                                old["sign_flip"],
                            )
                            new_key = (
                                -candidate["same_step"],
                                -candidate["opposite_step"],
                                candidate["phase_step"],
                                candidate["sign_flip"],
                            )

                            if new_key < old_key:
                                found[duplicate_index]["model"] = candidate
                                found[duplicate_index]["spectrum"] = spectrum

    models = [item["model"] for item in found]

    # Prefer the ordering of Luis's submitted examples when that ordering
    # is known.  Any additional isomers follow in deterministic order.
    known_order = {
        (5, 2): [(4, 2)],
        (6, 2): [(3, 1)],
        (6, 3): [(5, 4)],
        (7, 2): [(3, 1)],
        (8, 2): [(3, 1)],
        (8, 3): [(2, 1)],
        (8, 4): [(7, 5)],
        (9, 2): [(3, 1)],
        (10, 2): [(3, 1)],
        (10, 4): [(9, 7), (9, 5)],
        (10, 5): [(9, 6), (8, 7)],
        (12, 2): [(3, 1)],
    }

    preferred = known_order.get((n, d), [])

    def model_sort_key(model):
        pair = (model["same_step"], model["opposite_step"])

        try:
            preferred_index = preferred.index(pair)
        except ValueError:
            preferred_index = len(preferred)

        return (
            preferred_index,
            -model["same_step"],
            -model["opposite_step"],
            min(model["h1"], model["h2"]),
            max(model["h1"], model["h2"]),
        )

    models.sort(key=model_sort_key)

    return models


def orient_faces(faces):
    """Orient neighboring triangular faces oppositely along shared edges."""
    edge_faces = {}

    for fi, face in enumerate(faces):
        a, b, c = face

        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            edge_faces.setdefault(key, []).append(fi)

    neighbors = [[] for _ in faces]

    for edge, owners in edge_faces.items():
        if len(owners) == 2:
            a, b = owners
            neighbors[a].append((b, edge))
            neighbors[b].append((a, edge))

    oriented = [None] * len(faces)

    def direction(face, u, v):
        a, b, c = face

        if (u, v) in ((a, b), (b, c), (c, a)):
            return 1

        if (v, u) in ((a, b), (b, c), (c, a)):
            return -1

        raise RuntimeError("edge is not in face")

    for start in range(len(faces)):
        if oriented[start] is not None:
            continue

        oriented[start] = faces[start]
        stack = [start]

        while stack:
            fi = stack.pop()
            face = oriented[fi]

            for fj, edge in neighbors[fi]:
                if oriented[fj] is not None:
                    continue

                u, v = edge
                other = faces[fj]

                if direction(face, u, v) == direction(other, u, v):
                    other = (other[0], other[2], other[1])

                oriented[fj] = other
                stack.append(fj)

    return oriented


def write_off(fp, vertices, faces, n, d, isomer):
    fp.write("OFF\n")
    fp.write(
        f"# scrunchie {n}/{d}, isomer {isomer}\n"
    )
    fp.write(f"{len(vertices)} {len(faces)} 0\n")

    for x, y, z in vertices:
        fp.write(f"{x:.15g} {y:.15g} {z:.15g}\n")

    for a, b, c in faces:
        fp.write(f"3 {a} {b} {c}\n")


def standard_filename(n, d, isomer):
    return f"{n}_{d:0{len(str(n))}d}-scrunchie-{isomer:03d}.off"


def output_model(
    vertices,
    faces,
    n,
    d,
    isomer,
    output=None,
    save=False,
):
    if save:
        destination = Path.cwd() / standard_filename(n, d, isomer)
    elif output:
        destination = Path(output)
    else:
        destination = None

    if destination is None:
        write_off(sys.stdout, vertices, faces, n, d, isomer)
        return

    try:
        with destination.open("w", encoding="utf-8", newline="\n") as fp:
            write_off(fp, vertices, faces, n, d, isomer)
    except OSError as exc:
        sys.exit(f"scrunchie: cannot write {destination}: {exc}")


def list_isomers(n, d, models):
    """List available isomers for one n/d value."""
    count = len(models)

    print(
        f"{n}/{d}: {count} isomer"
        f"{'' if count == 1 else 's'}"
    )
    print(
        "  Steps a/b are angular separations between the two vertex orbits,"
    )
    print(
        "  measured in units of pi/n: a joins equal-height signs; "
        "b joins opposite-height signs."
    )

    step_width = max(
        len(f"{model['same_step']}/{model['opposite_step']}")
        for model in models
    )
    part_width = max(
        len(str(model["parts"]))
        for model in models
    )
    h1_width = max(
        len(f"{model['h1']:.12g}")
        for model in models
    )
    h2_width = max(
        len(f"{model['h2']:.12g}")
        for model in models
    )

    for index, model in enumerate(models, 1):
        steps = f"{model['same_step']}/{model['opposite_step']}"
        parts = str(model["parts"])
        h1 = f"{model['h1']:.12g}"
        h2 = f"{model['h2']:.12g}"

        print(
            f"{index:3d}  "
            f"steps {steps:<{step_width}}  "
            f"parts={parts:<{part_width}}  "
            f"h1={h1:<{h1_width}}  "
            f"h2={h2:<{h2_width}}"
        )

def verbose_report(n, d, isomer, models, model):
    fp = sys.stderr

    print(f"scrunchie {n}/{d}", file=fp)
    print(f"  gcd(n,d) = {math.gcd(n, d)}", file=fp)
    print(f"  isomers found = {len(models)}", file=fp)
    print(f"  selected isomer = {isomer}", file=fp)
    print(f"  epsilon = {EPSILON:.12g}", file=fp)
    print(
        "  cross steps (same/opposite) = "
        f"{model['same_step']}/{model['opposite_step']} "
        "units of pi/n",
        file=fp,
    )
    print(f"  h1 = {model['h1']:.15g}", file=fp)
    print(f"  h2 = {model['h2']:.15g}", file=fp)
    print(f"  c1 = {model['c1']:.15g}", file=fp)
    print(f"  c2 = {model['c2']:.15g}", file=fp)
    print(
        f"  phase step = {model['phase_step']}",
        file=fp,
    )

    if d & 1:
        print(
            f"  second-orbit sign flip = {model['sign_flip']}",
            file=fp,
        )

    print(
        f"  V/E/F = "
        f"{len(model['vertices'])}/"
        f"{len(model['edges'])}/"
        f"{len(model['faces'])}",
        file=fp,
    )
    print(f"  parts = {model['parts']}", file=fp)
    print("  edge length = 1", file=fp)
    print("  status = valid biform toroid", file=fp)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate LuisHPhi scrunchie Coptic biform deltahedra as OFF."
        )
    )

    parser.add_argument(
        "parameter",
        metavar=POLYGON_NOTATION_METAVAR,
        help=POLYGON_NOTATION_HELP,
    )

    parser.add_argument(
        "-i",
        "--isomer",
        type=int,
        default=1,
        metavar="N",
        help="select isomer N (default: 1)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="write geometry analysis to stderr",
    )

    parser.add_argument(
        "-L",
        "--list",
        action="store_true",
        help="list available isomers for the specified n/d and exit",
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
            "write OFF output using the standard scrunchie filename "
            "in the current directory"
        ),
    )

    add_version_argument(parser)

    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit must be nonnegative")

    global EPSILON
    EPSILON = 10.0 ** (-args.limit)

    if args.isomer < 1:
        parser.error("--isomer must be at least 1")

    try:
        n, d = parse_parameter(args.parameter)
    except (ValueError, TypeError) as exc:
        parser.error(f"invalid n/d '{args.parameter}': {exc}")

    models = discover_isomers(n, d)

    if not models:
        print(
            f"scrunchie: no valid isomers found for {n}/{d}",
            file=sys.stderr,
        )
        return 1

    if args.list:
        list_isomers(n, d, models)
        return 0

    if args.isomer > len(models):
        print(
            f"scrunchie: {n}/{d} has {len(models)} isomer"
            f"{'' if len(models) == 1 else 's'}; "
            f"cannot select isomer {args.isomer}",
            file=sys.stderr,
        )
        return 1

    model = models[args.isomer - 1]

    if args.verbose:
        verbose_report(
            n,
            d,
            args.isomer,
            models,
            model,
        )

    faces = orient_faces(model["faces"])

    output_model(
        model["vertices"],
        faces,
        n,
        d,
        args.isomer,
        output=args.output,
        save=args.save,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
