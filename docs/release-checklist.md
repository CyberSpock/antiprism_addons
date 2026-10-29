# Beta release checklist (0.9.0b1)

- [ ] Compare staged sources with the latest local authoritative source tree,
      including `scrunchie_math` and regression tests.
- [ ] Run `python tools/generate_help.py --check`.
- [ ] Run `python run_regression.py` on Cygwin and WSL/Ubuntu.
- [ ] Build the Python wheel and install in a clean venv on Cygwin, WSL/Ubuntu,
      and native Windows Python.
- [ ] Test all 17 installed command entry points with `--help` and `--version`.
      Run `python tools/check_install.py` with the installed interpreter.
- [ ] Run representative commands against a real installed Antiprism.
- [ ] Validate C++ `make BUILD_KIND=native` and `make BUILD_KIND=mingw` with
      a target-compatible Antiprism library (as appropriate).
- [ ] Review C++ licensing and preserve Dr. Zvi Har'El's acknowledgment.
- [ ] Confirm final repository branch name and whether it stays a fork.
- [ ] Replace the old public repository's tracked files in a single commit.
- [ ] Create a versioned GitHub beta release and attach the source/wheel.
- [ ] Decide whether and when to upload the beta to TestPyPI/PyPI.

The old `off_cong` utility is **not included** in this beta. Do not substitute
`off_coin` without separate testing; both remain deferred.
