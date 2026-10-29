# embeddip

[Program index](README.md) · [Python source](../../embeddip.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: embeddip.py [-h] [-m {d,e,D,E}] [-D COLOR] [-C COLOR] [-E COLOR]
                   [-V COLOR] [-v] [--keep-temp] [--version]
                   [n[/d]]

Embed a dipyramid within a cube in four arrangements.

Geometry calculations by Adrian Rossiter (www.antiprism.com).
Model choices:
    d   dipyramid across cube faces (default)
    e   dipyramid across cube edges
    D   alternative face arrangement
    E   alternative edge arrangement

Writes combined colored OFF geometry to standard output.

positional arguments:
  n[/d]                 n or n/d; d is the step (default 1), not a
                        denominator. Values are not reduced. (default: 6)

options:
  -h, --help            show this help message and exit
  -m, --model {d,e,D,E}
                        embedding: faces (d), edges (e), alternative faces
                        (D), edges (E); default d
  -D, --dipyramid-color COLOR
                        dipyramid face color (default: red)
  -C, --cube-color COLOR
                        cube face color (default: yellow)
  -E, --edge-color COLOR
                        edge color (default: lightgray)
  -V, --vertex-color COLOR
                        vertex color (default: gold)
  -v, --verbose         print calculations and commands to stderr
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
