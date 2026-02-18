---
created: 2026-02-17T23:50:00.000Z
title: Investigate Windows CI test hang blocking releases
area: ci
files:
  - .github/workflows/test.yml:154-189
---

## Problem

All 4 Windows matrix jobs (Python 3.11-3.14) hang during the "Run tests with coverage" step in `.github/workflows/test.yml`. No pytest output is produced. Jobs run until the 6-hour GitHub Actions timeout.

**Observed in:**

- Run 22073949778 (2026-02-16, PR #25 merge to main): all 4 Windows jobs timed out at 6 hours, `Tag and Release` job was skipped
- Run 22120104212 (2026-02-17, milestone commit): Windows jobs status not yet determined

Linux and macOS jobs pass on the same commits.

**Impact:**

- The `release` job in test.yml requires all jobs to pass (line 241-250). Windows hangs prevent it from running.
- `gh release list` shows latest release is v0.8.0 (2026-02-01). No releases exist after that date.
- The relationship between the Windows hang and the release gap has not been verified — other causes may exist.

## Investigation Notes

- Previous successful run: 21563677927 (2026-02-01, PR #22 merge) — all jobs passed including Windows
- The hang produces no log output from the test step — logs end at `Install dependencies`
- Run 22023158119 (2026-02-14) failed on all platforms with `pytest: error: argument -n/--numprocesses: expected one argument` — different issue (pytest-xdist config)

## Suggested Investigation

1. Compare `pyproject.toml` pytest config between v0.8.0 tag and current main
2. Check if a pytest plugin or fixture is hanging on Windows (e.g., subprocess spawning, yq binary download, file locking)
3. Try reproducing locally with `--timeout` flag or run a manual dispatch with debug logging
4. Check if `pytest-xdist` `-n` flag interacts with Windows differently
