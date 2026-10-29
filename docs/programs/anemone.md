# anemone

[Program index](README.md) · [Python source](../../anemone.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: anemone.py [-h] [-v] [-l LIM] [--allow-degenerate] [-o FILE | -s]
                  [--version]
                  n[/d]

Generate Coptic biform deltahedra as OFF on stdout.

positional arguments:
  n[/d]               n or n/d; d is the step (default 1), not a denominator.
                      Values are not reduced.

options:
  -h, --help          show this help message and exit
  -v, --verbose       write geometry analysis to stderr
  -l, --limit LIM     epsilon as 10**-LIM (default: 12)
  --allow-degenerate  emit OFF even if coincident vertices or unexpected
                      counts occur
  -o, --output FILE   write OFF output to FILE instead of stdout
  -s, --save          write OFF output as n_d-anemone.off in the current
                      directory
  --version           show program's version number and exit
```
