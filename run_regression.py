#!/usr/bin/env python3
"""Run the complete Antiprism Addons regression suite from this directory."""

from pathlib import Path
import os
import sys
import unittest


def main():
    root = Path(__file__).resolve().parent
    os.chdir(root)
    sys.path.insert(0, str(root))
    tests = unittest.defaultTestLoader.discover(
        start_dir=str(root / "tests"), pattern="test_*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
