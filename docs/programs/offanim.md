# offanim

[Program index](README.md) · [Python source](../../offanim.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: offanim.py [-h] [-o FILE] [--no-compress] [-T TITLE] [-t N[,ELMS]]
                  [-d SECS] [--hold SPEC] [--ping-pong] [--compact] [-v SIZE]
                  [-e SIZE] [-B COLOR] [-x ELMS] [-V COLOR] [-E COLOR]
                  [-F COLOR] [-p COMMAND] [--verbose] [--version]
                  OFF [OFF ...]

Create static or animated X3D Classic from OFF models.

Reads OFF files in natural order, optionally pre-processes them with an OFF
command/pipeline, and applies Antiprism off_color for V/E/F color overrides.
Face boundaries supply implicit edges; explicit OFF edges take precedence.
The X3D renderer does not materialize implicit edges with off_util -e.

By default, vertices and edges are genuine shared spheres and cylinders;
--compact uses screen-sized points and lines instead. Output is compressed
.x3dvz by default. Use --no-compress for readable .x3dv output.

Timing: -d SECS controls ordinary frame duration. --hold "5=3,12=2,18-20=1"
sets absolute durations for one-based positions in the sorted model list.
Ping-pong playback applies the same hold to each visit to a frame.

positional arguments:
  OFF                   OFF files or quoted glob patterns

options:
  -h, --help            show this help message and exit
  -o, --output FILE     output file (default: anim.x3dvz)
  --no-compress         write readable .x3dv rather than gzip .x3dvz
  -T TITLE              X3D scene title
  -t N[,ELMS]           opacity 0-255; v,e,f,a (default f)
  -d, --frame-time SECS
                        seconds per frame (default: 0.2)
  --hold SPEC           frame durations, e.g. "5=3,12=2,18-20=1"
  --ping-pong           animate forwards then backwards
  --compact             draw flat points/lines instead of 3D geometry
  -v SIZE               vertex radius (default 0.02), or --compact point size
                        (default 3)
  -e SIZE               edge radius or compact line width (default: -v / 1.5)
  -B COLOR              background color; any valid Antiprism color
  -x ELMS               hide elements (v, e, f)
  -V COLOR              vertex coloring passed to off_color -v
  -E COLOR              edge coloring passed to off_color -e
  -F COLOR              face coloring passed to off_color -f
  -p, --pre-process COMMAND
                        quoted command/pipeline before processing
  --verbose             print subprocess commands and model progress
  --version             show program's version number and exit

OFF default colors: vertex orange, edge lavender, face pale blue.
Frames are numbered 1..N in naturally sorted input order.
--hold assigns absolute durations and repeats on ping-pong visits.
The default X3D output is gzip-compressed.
```
