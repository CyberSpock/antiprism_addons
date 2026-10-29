# stepview

[Program index](README.md) · [Python source](../../stepview.py)

*This reference is generated from the current program's `--help`; do not edit it by hand.*

```text
usage: stepview.py [-h] [-V {antiview,offview}] [-s SUBCOMMAND]
                   [-a VIEWER_ARGS] [-A ANTIVIEW_ARGS] [-v] [--version]

Step through model files in the current directory.

OFF and OBJ files are viewed with antiview or offview. VRML/X3D files
(.wrl and .x3d) are always viewed with x3dview.

For browser-based viewers, press Space or Enter for the next model, or
Escape to exit. With antiview, close the viewer window to advance.

An optional subcommand may be inserted between the model input and viewer.
Extra viewer arguments may also be supplied. These strings are passed as
requested; their validity is the user's responsibility.

options:
  -h, --help            show this help message and exit
  -V, --viewer {antiview,offview}
                        viewer for OFF/OBJ files; WRL/X3D always use x3dview
                        (default: antiview)
  -s, --subcommand SUBCOMMAND
                        quoted command inserted between model input and viewer
  -a, --viewer-args VIEWER_ARGS
                        quoted arguments appended to whichever viewer is used
  -A, --antiview-args ANTIVIEW_ARGS
                        arguments appended only to antiview (default:
                        -geometry 1024x768+100+100 -B black -v 0.04)
  -v, --verbose         show commands being run
  --version             show program's version number and exit
```
