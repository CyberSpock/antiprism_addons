# vr1tovr2

[Program index](README.md) · [Python source](../../vr1tovr2.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: vr1tovr2.py [-h] [-o OUTPUT] [--version] [input_file]

Convert VRML 1.0 to VRML 2.0 (VRML97). If the input is not VRML 1.0, it is
passed through unchanged. If input_file is omitted, input is read from
standard input. Output is written to standard output unless -o is used. This
converter focuses on geometry-oriented VRML 1.0 files and supports the node
families used by the Antiprism Addons sample corpus.

positional arguments:
  input_file           input file; default is stdin

options:
  -h, --help           show this help message and exit
  -o, --output OUTPUT  output file; default is stdout
  --version            show program's version number and exit
```
