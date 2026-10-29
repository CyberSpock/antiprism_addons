# offview

[Program index](README.md) · [Python source](../../offview.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: offview.py [-h] [-v SIZE] [-e SIZE] [-x ELMS] [-l] [-V COLOR]
                  [-E COLOR] [-F COLOR] [-t N[,ELMS]] [-B COLOR] [-rot SPEED]
                  [-rotax X,Y,Z] [-p COMMAND] [-s] [--fullscreen] [-port PORT]
                  [-timeout SEC] [--keep-temp] [--version]
                  [OFF]

Prepare an OFF model with Antiprism and view it in Wagyx's web viewer. Reads
an OFF file or stdin; all geometry and color transformations happen locally,
before the temporary OFF file is served to the browser. The Python program
serves model data only from localhost; it does not upload OFF geometry to the
viewer website.

positional arguments:
  OFF                   OFF file (default: standard input)

options:
  -h, --help            show this help message and exit
  -v SIZE               vertex radius (default: 0.03)
  -e SIZE               edge radius (default: -v / 1.5)
  -x ELMS               hide elements (v, e, f)
  -l                    shortcut for -V black -E black
  -V COLOR              vertex coloring passed to off_color -v
  -E COLOR              edge coloring passed to off_color -e
  -F COLOR              face coloring passed to off_color -f
  -t N[,ELMS]           opacity 0-255; v,e,f,a (default f)
  -B COLOR              background color; any valid Antiprism color
  -rot SPEED            initial spin speed (can be positive or negative)
  -rotax X,Y,Z          rotation axis
  -p, --pre-process COMMAND
                        quoted command/pipeline before processing
  -s, --save-local-copy
                        save processed OFF in current directory; number copies
                        rather than overwrite
  --fullscreen          use interocitors.com full-window viewer
  -port PORT            localhost port (default: auto)
  -timeout SEC          maximum wait for browser fetch (default: 60)
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
