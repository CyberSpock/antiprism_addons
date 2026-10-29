# x3dview

[Program index](README.md) · [Python source](../../x3dview.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: x3dview.py [-h] [-s] [--fullscreen] [-port PORT] [-timeout TIMEOUT]
                  [--keep-temp] [--version]
                  [x3d_file]

View a VRML/X3D file with the online X_ITE viewer.

The input may be a file or standard input. Gzip-compressed input is accepted
automatically. Python serves model data only from localhost; it does not
upload VRML/X3D geometry to the viewer website. The temporary server shuts
down as soon as the viewer has successfully fetched the file.

Examples:
    x3dview model.wrl
    cat model.wrl | x3dview
    gzip -c model.wrl | x3dview

positional arguments:
  x3d_file              VRML/X3D file; if omitted, read from standard input

options:
  -h, --help            show this help message and exit
  -s, --save-local-copy
                        save processed VRML/X3D in current directory; number
                        copies rather than overwrite
  --fullscreen          use interocitors.com full-window viewer
  -port, --port PORT    localhost port; 0 chooses an unused port (default: 0)
  -timeout, --timeout TIMEOUT
                        safety timeout waiting for viewer fetch (default: 60.0
                        seconds)
  --keep-temp           preserve temporary files and report their directory
  --version             show program's version number and exit
```
