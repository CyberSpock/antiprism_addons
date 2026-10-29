# pyr2trap

[Program index](README.md) · [Python source](../../pyr2trap.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: pyr2trap.py [-h] [-p HEIGHT] [-m PARTS] [-P COLOR] [-A COLOR]
                   [-E COLOR] [-V COLOR] [-v] [--keep-temp] [--version]
                   [n[/d]]

Make a trapezohedron from two pyramids and a central antiprism.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
Output the selected components as colored OFF on stdout.

positional arguments:
  n[/d]                 n or n/d; d is the step (default 1), not a
                        denominator. Values are not reduced. (default: 6)

options:
  -h, --help            show this help message and exit
  -p, --pyramid-height HEIGHT
                        pyramid height (default: 1)
  -m, --model PARTS     parts: pyramid (p), mirrored pyramid (m), antiprism
                        (a); combine letters, e.g. pma (default: pma)
  -P, --pyramid-color COLOR
                        pyramid face color (default: red)
  -A, --antiprism-color COLOR
                        antiprism face color (default: blue)
  -E, --edge-color COLOR
                        edge color (default: lightgray)
  -V, --vertex-color COLOR
                        vertex color (default: gold)
  -v, --verbose         print calculated heights and commands to stderr
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
