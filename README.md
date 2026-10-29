![Antiprism Addons](assets/AA_logo.png)

# Antiprism Addons

Additional polyhedral geometry programs maintained by Roger Kaufman,
building on [Adrian Rossiter's Antiprism](https://www.antiprism.com/).

**Beta version: 0.9.0b1.**
This repository is separate from Antiprism itself. Some generators draw on
mathematical work by Luis (LuisHPhi), credited in program help.

## Installation

The Python package provides **17 commands** and uses the Python standard
library. External Antiprism executables are required for many operations,
and must already be on your `PATH`; **pip does not install Antiprism**.

Install from a local checkout for testing:

```sh
python -m pip install .
anemone --version
scrunchie_math --help
```

After the package is published on PyPI, users will be able to run:

```sh
python -m pip install antiprism-addons
```

This is a **future command**, not a claim that the PyPI release already exists.
On Windows/Cygwin/WSL, use the corresponding active Python virtual environment.

The optional `stella` utility needs `STELLA_EXE` configured. `offview` and
`x3dview` serve model data on localhost to the existing hosted browser
viewers; their browser HTML/JavaScript remains an external dependency.

## Program reference

See [all 17 generated help pages](docs/programs/README.md), derived from the
programs' actual `--help` output. Examples:

- [Anemone](docs/programs/anemone.md)
- [Scrunchie](docs/programs/scrunchie.md)
- [Scrunchie Math](docs/programs/scrunchie_math.md)
- [Offview](docs/programs/offview.md)
- [X3dview](docs/programs/x3dview.md)

## Independent C++ utilities

The same repository includes `alt_color`, `off_sym`, and `kaleido` under
[`cpp/`](cpp/README.md). Build them against an existing compiled, compatible
Antiprism library with GNU Make. These are **not included in the pip wheel**.
`off_cong` and the possible successor `off_coin` are deferred.

## Development and releases

- [Installation details](docs/installation.md)
- [Development and tests](docs/development.md)
- [Beta publication checklist](docs/release-checklist.md)

Regenerate help with `python tools/generate_help.py`; check it with
`python tools/generate_help.py --check`. Run regressions with
`python run_regression.py`.

## Licenses and attribution

Python scripts use the [BSD Zero Clause License](LICENSE). C++ files retain
their respective notices. In particular, the historical parts of `kaleido`
require acknowledgment of Dr. Zvi Har'El; see [`cpp/README.md`](cpp/README.md).
Antiprism itself is a separate project with its own licensing and distribution.
