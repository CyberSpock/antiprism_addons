# scrunchie_math

[Program index](README.md) · [Python source](../../scrunchie_math.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: scrunchie_math.py [-h] [-L] [-l LIM] [-v] [-o FILE | -s] [--version]
                         n[/d] [j]

Generate LuisHPhi scrunchies using his GeoGebra construction.

positional arguments:
  n[/d]              n or n/d; d is the step (default 1), not a denominator.
                     Values are not reduced.
  j                  Luis's GeoGebra j value

options:
  -h, --help         show this help message and exit
  -L, --list         list all j values allowed by Luis's validity conditions,
                     including negative values and j=0, then exit
  -l, --limit LIM    minimum distance for unique vertex locations as negative
                     exponent (default: 12 giving 1e-12)
  -v, --verbose      write construction and mesh analysis to stderr
  -o, --output FILE  write OFF output to FILE instead of stdout
  -s, --save         write OFF output using the standard Luis scrunchie
                     filename in the current directory
  --version          show program's version number and exit
```
