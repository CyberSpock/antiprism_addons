# scrunchie

[Program index](README.md) · [Python source](../../scrunchie.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: scrunchie.py [-h] [-i N] [-v] [-L] [-l LIM] [-o FILE | -s] [--version]
                    n[/d]

Generate LuisHPhi scrunchie Coptic biform deltahedra as OFF.

positional arguments:
  n[/d]              n or n/d; d is the step (default 1), not a denominator.
                     Values are not reduced.

options:
  -h, --help         show this help message and exit
  -i, --isomer N     select isomer N (default: 1)
  -v, --verbose      write geometry analysis to stderr
  -L, --list         list available isomers for the specified n/d and exit
  -l, --limit LIM    minimum distance for unique vertex locations as negative
                     exponent (default: 12 giving 1e-12)
  -o, --output FILE  write OFF output to FILE instead of stdout
  -s, --save         write OFF output using the standard scrunchie filename in
                     the current directory
  --version          show program's version number and exit
```
