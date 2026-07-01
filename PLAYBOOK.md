# Forge SDK — Verification & Release Playbook

Repeatable, observable verification floor for every forge-sdk change.

## Prerequisites

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,test,all]"
pip install pyright ruff build pytest pytest-asyncio datasets
```

## Quick Verify (3 commands)

```bash
ruff check src/ --ignore=E501 && ruff format --check src/     # Lint + format
PYTHONPATH=src python -m pytest tests/ -q --tb=short           # Tests (204+)
python -m build --outdir /tmp/dist                             # Package build
```

## Full CI (what GitHub Actions runs)

```bash
# 1. Lint
ruff check src/ --ignore=E501
ruff format --check src/

# 2. Security (Bandit)
pip install bandit && bandit -r src/ -ll -x src/forge_sdk/cli/permissions.py

# 3. Type check
pyright src/ --pythonversion 3.11

# 4. Tests — all supported Python versions
PYTHONPATH=src python -m pytest tests/ -q --tb=short

# 5. Build
python -m build --outdir /tmp/dist

# 6. Smoke (install from wheel)
pip install /tmp/dist/forge_sdk-*.whl && forge doctor
```

## Release Process

```bash
# 1. Verify clean working tree
git status --short  # must be empty

# 2. Run full CI locally
ruff check src/ --ignore=E501
ruff format --check src/
pyright src/ --pythonversion 3.11
PYTHONPATH=src python -m pytest tests/ -q --tb=short
python -m build --outdir /tmp/dist

# 3. Bump version in pyproject.toml + CHANGELOG.md

# 4. Commit, tag, push
git add -A
git commit -m "chore: release vX.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin main --tags

# 5. Create GitHub release
gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag

# 6. Verify release
gh release view vX.Y.Z
pip install forge-sdk==X.Y.Z && forge doctor

# 7. Close addressed issues
gh issue close <num> --reason completed
```

## Observability

Every `forge run` emits a typed event stream. Pipe it for machine consumption:

```bash
forge run --output-format stream-json "fix the bug" > trace.ndjson
# Each line is one typed event with correlation keys (trace_id, run_id, model, provider)
```

Check session state:

```bash
forge run --list-sessions
forge run --resume <session-id>
```

Doctor check:

```bash
forge doctor              # human-readable
forge doctor --json       # machine-readable
```

## Test Inventory

| File | What it covers | Count |
|---|---|---|
| `test_smoke.py` | Core ReAct loop, tool dispatch, model port | 45+ |
| `test_react_cwd.py` | CWD tracking, subdirectory runs | 3+ |
| `test_native_tool_calling.py` | Provider-native tool call parsing | 10+ |
| `test_none_content_response.py` | None content edge cases | 3+ |
| `test_parse_failure_retry.py` | Parse failure retry loop | 4+ |
| `test_parse_control_chars.py` | Control character recovery | 3+ |
| `test_phantom_edit_from_blocked_command.py` | Phantom edits from blocked commands | 3+ |
| `test_task_implies_edits.py` | Task-implied edit tracking | 5+ |
| `test_named_target_coverage.py` | Named target coverage | 4+ |
| `test_edit_intel.py` | Edit intelligence | 5+ |
| `test_filesystem.py` | Filesystem tools | 10+ |
| `test_security_containment.py` | Security containment | 6+ |
| `test_security_path_command.py` | Path command security | 3+ |
| `test_security_temp_dir.py` | Temp dir security | 2+ |
| `test_shell_compound_commands.py` | Shell compound commands | 5+ |
| `test_verification_pipeline.py` | Verification pipeline | 5+ |
| `test_verify_gate.py` | Verify gate | 10+ |
| `test_adapters.py` | Tool adapters | 6+ |
| `test_cli_trace_cwd.py` | CLI trace CWD | 3+ |
| **Total** | | **204** |

## Failure Taxonomy (L4)

| Exit code | failure_reason | When |
|---|---|---|
| 0 | `""` | Agent finished successfully |
| 1 | `"run_error"` | Uncaught exception during run |
| 2 | `"config_error"` | Bad config, missing API key |
| 3 | `"model_auth_error"` | Provider returned auth/rate-limit error |
| 4 | `"usage_limit_exceeded"` | Token or cost budget exhausted |
| 5 | `"max_steps_reached"` | Step budget exhausted without convergence |

## Layer Map

| Layer | CLI flag | Source | Spec § |
|---|---|---|---|
| L5b | `--resume`, `--checkpoint-dir`, `--list-sessions` | `cli/session.py` | L5b |
| L5a | `--permission-mode` | `cli/permissions.py` | L5a |
| L4 | _(always active)_ | `agents/react.py` | L4 |
| L3 | `--output-format` | `agents/events.py`, `cli/renderers.py` | L3 |
| L2 | `--verify-command`, `--max-tokens`, `--max-cost`, `--sandbox` | `cli/main.py` | L2 |
| L1 | `forge doctor` | `cli/doctor.py`, `cli/ansi.py` | L1 |
