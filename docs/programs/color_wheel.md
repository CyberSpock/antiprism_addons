# color_wheel

[Program index](README.md) · [Python source](../../color_wheel.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: color_wheel.py [-h] [-m {w,g,G}] [-c {rgb,hsv,hsl}] [--keep-temp]
                      [--version]
                      [map_name] num_cols

Make various color wheels.

positional arguments:
  map_name              map name or definition; if an .off file is given,
                        build a map from it
  num_cols              number of map colors; non-negative integer; zero uses
                        all colors of an OFF file

options:
  -h, --help            show this help message and exit
  -m, --model {w,g,G}   model type: w wheel, g grid, G globe (default: w)
  -c, --col-sys {rgb,hsv,hsl}
                        color system (default: rgb)
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
