#!/usr/bin/env python3
"""Generate Github-rendered Markdown from each Addons program's --help.

Python standard library only. Edit *programs*, not generated pages.
"""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "programs"
EXCLUDE = {"anti_common.py", "run_regression.py"}


def pages():
    programs = sorted(
        p for p in ROOT.glob("*.py")
        if p.name not in EXCLUDE and not p.name.startswith("_")
    )
    if not programs:
        raise RuntimeError("no Python programs found")
    yield OUTPUT / "README.md", (
        "# Python program reference\n\n"
        "Generated from the actual `--help` output of each program.\n"
        "See [development](../development.md) to rebuild.\n\n"
        + "\n".join(
            f"- [`{p.stem}`]({p.stem}.md)" for p in programs
        ) + "\n"
    )
    for source in programs:
        result = subprocess.run(
            [sys.executable, str(source), "--help"],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{source.name} --help failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        output = result.stdout.rstrip()
        if not output or "usage:" not in output.lower():
            raise RuntimeError(
                f"{source.name} --help returned no recognizable help"
            )
        if "```" in output:
            raise RuntimeError(
                f"{source.name} --help contains a Markdown fence; "
                "adjust the generator before publishing"
            )
        content = (
            f"# {source.stem}\n\n"
            f"[Program index](README.md) · "
            f"[Python source](../../{source.name})\n\n"
            "*This reference is generated from the current program's "
            "`--help`; do not edit it by hand.*\n\n"
            "```text\n" + output + "\n```\n"
        )
        yield OUTPUT / f"{source.stem}.md", content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="verify generated Markdown is up to date without writing",
    )
    args = parser.parse_args()
    expected = dict(pages())
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p, content in expected.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != content]
        extra = [str(p.relative_to(ROOT)) for p in OUTPUT.glob("*.md")
                 if p not in expected] if OUTPUT.exists() else []
        if stale or extra:
            for name in stale + extra:
                print(f"outdated: {name}", file=sys.stderr)
            return 1
        print(f"Up to date: {len(expected)-1} program pages")
        return 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
    for path in OUTPUT.glob("*.md"):
        if path not in expected:
            path.unlink()
    print(f"Generated {len(expected)-1} program pages and index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
