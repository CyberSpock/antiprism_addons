# stella

[Program index](README.md) · [Python source](../../stella.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: stella.py [-h] [-v] [-s] [--version] [off_file]

Send an OFF model to Stella4D without changing the original.

Examples:
    stella model.off
    stella cube
    off_color -f S model.off | stella

positional arguments:
  off_file              OFF file, Antiprism built-in model, or standard input

options:
  -h, --help            show this help message and exit
  -v, --verbose         show commands and temporary filename
  -s, --save-local-copy
                        save original colored OFF in current directory; number
                        copies rather than overwrite
  --version             show program's version number and exit
```
