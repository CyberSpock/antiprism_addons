# rotyz

[Program index](README.md) · [Python source](../../rotyz.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: rotyz.py [-h] -y vN|eN|fN -z vN|eN|fN [-v] [--keep-temp] [--version]
                model

Orient OFF geometry using two selected elements. Align the first element's
centre with the positive Y axis; use the second to establish the forward
(positive Z) direction. The rotation uses Antiprism's twelve-number off_trans
-R operation.

positional arguments:
  model                 OFF file, Antiprism built-in model, or '-' for stdin

options:
  -h, --help            show this help message and exit
  -y, --y-axis vN|eN|fN
                        element whose centre is oriented along positive Y
  -z, --z-axis vN|eN|fN
                        second element establishing positive Z direction
  -v, --verbose         show the selected coordinates and commands on stderr
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
