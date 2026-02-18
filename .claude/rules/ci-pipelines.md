---
paths:
  - ".github/**"
---

# CI/CD Pipeline Reference

Read workflow files before making claims about what they do. Do not infer behavior from filenames.

## Verification After Pushing to Main

After any push to main, verify the pipeline completed and a release was created:

```bash
# Check latest workflow run status
gh run list --workflow=test.yml --limit 3

# Check if the release job ran (not skipped/cancelled)
gh run view <run-id> --json jobs --jq '.jobs[] | select(.name == "Tag and Release") | {status, conclusion}'

# Check latest releases match the work done
gh release list --limit 5

# Compare: latest release tag should reflect recent conventional commits
gh api repos/{owner}/{repo}/tags --jq '.[0:5] | .[].name'
```

If the release job was skipped or cancelled, investigate which prerequisite job failed. The release job requires ALL quality gate jobs to pass.

## Release Pipeline (push to main → PyPI)

```
push to main
  → .github/workflows/test.yml (all quality gates)
    → release job (line 239): tags via mathieudutour/github-tag-action@v6.2
      → creates GitHub release via ncipollo/release-action@v1
        → triggers .github/workflows/auto-publish.yml
          → uv build → uv publish (PyPI)
          → mcpb pack → upload MCPB bundle to release
```

**Do not manually create git tags or GitHub releases.** The pipeline handles both automatically from conventional commit prefixes (`feat:`, `fix:`, etc.). `default_bump: false` means no tag is created without a conventional prefix.

The release job uses `secrets.RELEASE_TOKEN` (not `GITHUB_TOKEN`) to create releases — this allows the release event to trigger `auto-publish.yml`.

## Quality Gates — `.github/workflows/test.yml`

All jobs run on push to main and pull requests to main.

| Job                 | What it checks                                                    | Lines   |
| ------------------- | ----------------------------------------------------------------- | ------- |
| `format`            | `ruff format --check`                                             | 21-40   |
| `lint`              | `ruff check --output-format=github`                               | 42-62   |
| `typecheck`         | `mypy packages/ --show-error-codes`                               | 64-84   |
| `basedpyright`      | `basedpyright packages/`                                          | 86-106  |
| `lint-extra`        | markdownlint, prettier, shellcheck, shfmt                         | 108-142 |
| `validate-manifest` | `mcpb validate manifest.json`                                     | 144-152 |
| `test`              | pytest + coverage, matrix: Python 3.11-3.14 × Linux/macOS/Windows | 154-189 |
| `coverage-summary`  | PR comment with coverage % (PR only)                              | 191-237 |
| `release`           | Tag + GitHub release (main push only, after all above pass)       | 239-275 |

## Publishing — `.github/workflows/auto-publish.yml`

Triggers: `release: published` event only.

1. Checkout at release tag (line 17-19)
2. `uv build` (line 33)
3. `uv publish` to PyPI (line 34)
4. `mcpb pack` to create MCPB bundle (lines 45-58)
5. Upload MCPB bundle to GitHub release (lines 64-67)

## Dependency Updates — `.github/workflows/yq-update.yml`

Triggers: weekly cron (Monday 9:00 UTC), manual dispatch.

1. Reads current `DEFAULT_YQ_VERSION` from `packages/mcp_json_yaml_toml/yq_wrapper.py` (line 24)
2. Checks latest yq release via GitHub API (lines 30-40)
3. Downloads checksums, validates SHA256 format (lines 54-100)
4. Updates version and checksums via `.github/scripts/update_yq_checksums.py` (lines 102-115)
5. Runs `pytest -x -q` against new version (lines 131-139)
6. Creates PR if tests pass (lines 141-175)
7. Reports failure if tests fail (lines 177-183)

## Known Issues

**Windows test hangs (as of 2026-02-17):** All 4 Windows matrix jobs (Python 3.11-3.14) hang indefinitely during the "Run tests with coverage" step — no pytest output is produced, and jobs run until the 6-hour GitHub Actions timeout. This blocks the `release` job on every push to main. Linux and macOS jobs pass. No automatic release has been created since v0.8.0 (2026-02-01).
