# kaufman

[Program index](README.md) · [Python source](../../kaufman.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: kaufman.py [-h] [-c] [-E COLOR] [-V COLOR] [-v] [--keep-temp]
                  [--version]
                  [model] n

Make Kaufman polyhedra by repeatedly joining a model and its dual. The
original method takes the convex hull of the canonical base-and-dual model for
each iteration. The -c method uses Conway's j^n operation instead. Both
methods finish with side-based face coloring and canonicalization.

positional arguments:
  model                 OFF file or Antiprism built-in model (default: stdin)
  n                     number of join iterations (non-negative integer)

options:
  -h, --help            show this help message and exit
  -c, --conway          use Conway's j^n operation instead of the hull method
  -E, --edge-color COLOR
                        edge color (default: lightgray)
  -V, --vertex-color COLOR
                        vertex color (default: gold)
  -v, --verbose         show commands and canonicalization diagnostics on
                        stderr
  --keep-temp           preserve intermediate OFF files and report their
                        directory
  --version             show program's version number and exit
```
