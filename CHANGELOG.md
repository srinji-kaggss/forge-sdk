# Changelog

All notable changes to forge-sdk are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [0.5.2] - 2026-06-30

Trust-gate hardening. Found via hands-on dogfooding (a real concurrent
fan-out batch against lgwks issue #349), not code review — each fix has a
regression test exercising the actual failure.

### Fixed
- **False-success on malformed model output** (`agents/react.py`): a
  non-JSON / unparseable model response was silently classified as a
  successful `finish`, producing a "Status: SUCCESS" with zero tool calls
  executed. Parser now returns an explicit `__parse_failed__` sentinel,
  which triggers a bounded corrective retry (2 attempts) before the run
  honestly reports failure. (#28)
- **Read-only safety-net bypass** (`agents/react.py`): `_task_implies_edits()`
  treated a task's own scoping caveats (e.g. "do not modify X.py itself")
  as a blanket read-only signal, disabling the zero-edits-on-an-edit-task
  safety net. Added `_READ_ONLY_SCOPED_TAIL` to distinguish a genuine
  read-only marker from a scoped exclusion naming one other file. (#28)
- **Residual `shell=True` fallback** (`tools/adapters.py`):
  `LgwksToolAdapter` fell back to `shell=True` when `shlex.split` failed on
  unbalanced quotes, reopening a shell-injection path layer L3 was meant to
  close. Now returns a blocked `ToolResult` with a quoting-fix hint instead
  of ever shelling out. (#27)
- **Concurrent-run trace/audit path collision** (`cli/main.py`): `trace_dir`
  and `audit_db` were resolved against the process's real `os.getcwd()`
  instead of the run's `--cwd`, so N concurrent `forge run` invocations
  launched from one shared directory wrote all N runs' traces into one
  shared folder — forensic evidence from a 6-task concurrent batch nearly
  collided. Added `scope_path_to_cwd()`; both paths now resolve against
  `--cwd` when relative. (#29)

### Known open issue (not fixed, tracked)
- Partial-completion over-claim: an agent that completes 1 of 2 named
  edits and silently drops the second can still report full success — the
  existing zero-edits safety net doesn't fire because ≥1 edit did happen.
  See `blackbox2/PLAYBOOK-forge-fanout.md` §9 for the full writeup and the
  prototyped verify-gate mitigation.

## [0.5.1] - 2026-06-30

Defense-in-depth security hardening — 5-layer model (path containment,
network egress block, destructive-command block, prompt-injection
sanitization, sensitive-path allowlist). See GitHub release notes.

## [0.5.0] and earlier

See GitHub releases for v0.5.0 and earlier — this file starts at 0.5.2;
earlier history wasn't backfilled.
