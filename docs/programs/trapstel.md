# trapstel

[Program index](README.md) · [Python source](../../trapstel.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: trapstel.py [-h] [-m PARTS] [-r] [-T COLOR] [-A COLOR] [-E COLOR]
                   [-V COLOR] [-v] [--keep-temp] [--version]
                   [n[/d]]

Generate a trapezohedron that is dual to and a stellation of an antiprism.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
When n/d = 2, the model is a compound of tetrahedra.
Output selected parts as colored OFF on stdout.

positional arguments:
  n[/d]                 n or n/d; d is the step (default 1), not a
                        denominator. Values are not reduced. (default: 6)

options:
  -h, --help            show this help message and exit
  -m, --model PARTS     trapezohedron (t), reciprocal antiprism (a), or both
                        (ta); default t
  -r, --rotate-antiprism
                        rotate the reciprocal antiprism into the
                        trapezohedron; include a in selected parts
  -T, --trapezohedron-color COLOR
                        trapezohedron face color (default: red)
  -A, --antiprism-color COLOR
                        antiprism face color (default: blue)
  -E, --edge-color COLOR
                        edge color (default: lightgray)
  -V, --vertex-color COLOR
                        vertex color (default: gold)
  -v, --verbose         print calculated height and commands to stderr
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
