# Antiprism Addons 0.9.0b1 beta

The first stand-alone Antiprism Addons beta release separates Roger Kaufman's
additional polyhedral utilities from Adrian Rossiter's Antiprism source tree.

- 17 Python command-line utilities, consistently versioned at 0.9.0b1.
- Generated GitHub Markdown reference pages derived from each command's help.
- Independent C++ source and GNU Makefile for `alt_color`, `off_sym`, `kaleido`.
- A Python wheel and source distribution; C++ utilities are not in the wheel.
- Antiprism itself remains a separate installation prerequisite.
- Historical script acknowledgments and `kaleido` attribution retained.

**Deferred:** `off_cong`/`off_coin`, the Pascal-era `snoflake`, and other
potential C++→Python ports. No new geometry features are introduced here.

For release validation and platform checks see
[`docs/release-checklist.md`](docs/release-checklist.md).
