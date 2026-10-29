# Installation

## Python commands from the source tree

Requires Python 3.10 or newer and an active virtual environment where
appropriate. The package depends only on the Python standard library;
many utilities also invoke Antiprism command-line tools available on `PATH`.

```sh
python -m pip install .
scrunchie_math --help
anemone --version
```

When the package is published on PyPI, use
`python -m pip install antiprism-addons` instead.

To test a built wheel from a clean virtual environment:

```sh
python -m pip wheel . --no-deps -w dist
python -m pip install dist/antiprism_addons-0.9.0b1-py3-none-any.whl
```

The filenames and generated launchers will vary according to the platform;
use the active interpreter's `python -m pip`. Do **not** copy virtual
environments between Cygwin, WSL, Ubuntu, or native Windows installations.

## External Antiprism prerequisite

This distribution does not bundle `off_util`, `off_color`, `off_query`,
`conv_hull`, or the other Antiprism executables used by individual commands.
Install the corresponding Antiprism programs separately and add them to `PATH`.

## Optional Stella

Set `STELLA_EXE` to the actual Stella executable for your platform when using
`stella`. No hard-coded Stella path is assumed.

## Browser viewers

`offview` and `x3dview` serve model bytes locally over localhost and open
existing hosted HTML/JavaScript viewers. The retired *Webview distribution
page* is not required, but the browser viewer content and handshake remain
part of the current runtime behavior.

## Independent C++ utilities

These are provided as source under [`cpp/`](../cpp/README.md) and require
matching Antiprism C++ headers and a compiled compatible Antiprism library.
They are not installed through pip.
