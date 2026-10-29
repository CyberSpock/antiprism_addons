# Development

## Run regression tests

```sh
python3 run_regression.py
```

Some tests use fake Antiprism executables; they supplement rather than
replace end-to-end tests with the real geometry programs.

## Regenerate the program reference

```sh
python3 tools/generate_help.py
```

This uses the **same Python interpreter** running the generator to obtain
`--help` from every Python addon, then writes Markdown reference pages.
No HTML editor, GTML, Perl, or web server is needed. The generated pages
are committed to Git so GitHub displays them directly.

To verify that references have been refreshed:

```sh
python3 tools/generate_help.py --check
```

If help changes, rerun the generator and commit the updated Markdown.
Keep hand-written examples and mathematical explanations *outside* the
generated pages, so rerunning this tool never overwrites them.

## Publishing

See [beta release checklist](release-checklist.md).

Before publication, test the installable package and all entry points on
Cygwin, WSL, and native Windows Python. Preserve non-reduced `n/d`
notation where it encodes compound polyhedra. CLI help and error output
should fit within 80 columns.

## Smoke-test a wheel installation

After installing the wheel into a clean environment, run:

```sh
python tools/check_install.py
```

This checks all installed command wrappers using `--help` and `--version`.
It does not require Antiprism executables or replace real geometry tests.
