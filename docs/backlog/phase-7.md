# Phase 7: Maintenance & Observability

> **Goal**: Close the three open advisories from Phase 4/5 reviews that reduce operator visibility into runtime behaviour: trimmer truncation is silent (ADV-004), the security validator emits to stderr rather than Python logging (ADV-006), and the sqlglot version contract is unbounded with no test to detect silent breakage (ADV-007).

**Status**: Complete
**Progress**: 3/3 tasks complete

**Dependencies**: Phase 6 complete (all epics delivered)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P7-T01 | Trimmer Structured Logging | Complete | Phase 4 complete |
| P7-T02 | Security Validator Logging | Complete | Phase 5 complete |
| P7-T03 | sqlglot Version Contract Test | Complete | Phase 5 complete |

---

## P7-T01: Trimmer Structured Logging

**Description**: All four trimmer `trim()` methods return silently when they drop content. Operators cannot distinguish "output fit within budget" from "output was truncated" without inspecting the returned string. This task adds a single `logging.getLogger("argent.trimmer").info(...)` call at each truncation site so that standard Python log capture gives operators an observable count of truncation events without requiring caller-side inspection.

**Advisory reference**: ADV-004 (DevOps, P4 round 2)

**Status**: Complete

### User Story

As an operator running ARG-wrapped agents in production, I need a structured log signal when the trimmer drops content so that I can detect systemic context-window budget pressure without adding custom inspection code to every egress handler.

### Acceptance Criteria

- [ ] `JsonArrayTrimmer.trim()` emits `logging.getLogger("argent.trimmer").info(...)` when at least one item is dropped; log record includes `trimmer`, `chars_dropped`, and `max_chars`
- [ ] `JsonDictTrimmer.trim()` emits the same log record when at least one key is dropped
- [ ] `MarkdownTableTrimmer.trim()` emits the same log record when at least one body row is dropped
- [ ] `PythonTracebackTrimmer.trim()` emits the same log record when the traceback is cut
- [ ] Log message format: `"[argent.trimmer] %s: chars_dropped=%d max_chars=%d"` (trimmer class name, chars dropped, budget)
- [ ] No log emitted when content fits within budget (no truncation)
- [ ] No log emitted when content cannot be parsed by the trimmer (e.g. non-JSON passed to `JsonArrayTrimmer`)
- [ ] `mypy --strict` passes; no new dependencies (stdlib `logging` only)
- [ ] 90%+ coverage maintained

### Implementation Notes

- Logger name: `"argent.trimmer"` — consistent with the `"argent.security"` and `"argent.telemetry"` namespace convention
- `chars_dropped`: `len(original_content) - len(returned_content)` — computed after the trimmed result is known
- Level: `INFO` — truncation is not an error, but it is notable operational state
- The log call must fire on the successful-trim path, not on every call. The early-return paths (fits within budget, unparseable) must remain silent.

### Files to Modify

- `src/argent/trimmer/json_trimmer.py` — add logger + INFO call in both `trim()` methods
- `src/argent/trimmer/markdown.py` — add logger + INFO call in `trim()`
- `src/argent/trimmer/traceback.py` — add logger + INFO call in `trim()`
- `tests/unit/test_trimmer_json.py` — add `caplog` assertions for truncation logging
- `tests/unit/test_trimmer_markdown.py` — add `caplog` assertions
- `tests/unit/test_trimmer_traceback.py` — add `caplog` assertions

### Commit Messages

```
test: RED — add failing caplog assertions for trimmer truncation logging (P7-T01)
feat: add structured INFO logging to all trimmer trim() methods (P7-T01)
```

---

## P7-T02: Security Validator Logging

**Description**: `SqlAstValidator.validate()` currently uses `sys.stderr.write(...)` to report unexpected sqlglot errors, which bypasses the Python logging system and cannot be captured by standard handlers (e.g., structured JSON log shippers, PIIFilter, caplog in tests). Additionally, there is no log signal when the validator successfully blocks a destructive statement — the only observable event is the raised `SecurityViolationError`, which requires caller-side exception catching and re-logging to produce a count.

This task converts the stderr diagnostic to `logging.getLogger("argent.security").warning(...)` and adds an `info(...)` call immediately before raising `SecurityViolationError`.

**Advisory reference**: ADV-006 (DevOps + QA, P5)

**Status**: Complete

### User Story

As an operator running ARG-wrapped agents in production, I need security validator events to flow through the Python logging system so that both blocked statements and unexpected parse errors are visible in my log aggregation pipeline without requiring caller-side exception handling.

### Acceptance Criteria

- [ ] `sys.stderr.write(...)` in `SqlAstValidator.validate()` is replaced with `logging.getLogger("argent.security").warning(...)` (same information, same guarding condition)
- [ ] An `info(...)` call is emitted to `"argent.security"` immediately before raising `SecurityViolationError` — log record includes the policy name and the SQL keyword that was blocked
- [ ] `import sys` is removed from `sql_validator.py` (no longer needed)
- [ ] Existing test `test_handles_unexpected_sqlglot_error_with_stderr_diagnostic` is updated to use `caplog` instead of `capsys`
- [ ] New test asserts `INFO` log record emitted for blocked statements (at minimum `DROP`)
- [ ] `mypy --strict` passes; no new dependencies (stdlib `logging` only)
- [ ] 90%+ coverage maintained

### Implementation Notes

- Logger name: `"argent.security"` — already referenced in existing stderr messages; just change the mechanism
- WARNING level for unexpected sqlglot errors (same severity, now routable)
- INFO level for blocked statements (operational, not an error from the library's perspective — the exception signals the error to the caller)
- Log message for block: `"[argent.security] SqlAstValidator: blocked %s statement"` (the SQL keyword)
- Log message for unexpected error: unchanged text, but via `logger.warning(...)` instead of `sys.stderr.write(...)`

### Files to Modify

- `src/argent/security/sql_validator.py` — replace `sys.stderr.write` with `logger.warning`; add `logger.info` before raise
- `tests/unit/test_sql_validator.py` — update capsys test to caplog; add INFO assertion

### Commit Messages

```
test: RED — add failing caplog assertions for SqlAstValidator logging (P7-T02)
feat: replace sys.stderr with logging in SqlAstValidator (P7-T02)
```

---

## P7-T03: sqlglot Version Contract Test

**Description**: `_BLOCKED_STMT_TYPES` contains sqlglot AST class names (`Drop`, `Delete`, `TruncateTable`, `Alter`) verified against sqlglot 29.0.1. The dependency pin `sqlglot>=20.0.0` has no upper bound, so a future sqlglot major release that renames internal AST node classes would silently break the security policy without any test failure. This task adds an upper bound and a contract test that fails if any of the four class names disappear from `sqlglot.expressions`.

**Advisory reference**: ADV-007 (DevOps, P5)

**Status**: Complete

### User Story

As a maintainer of the ARG library, I need a CI-level contract test that fails immediately if a sqlglot upgrade renames the AST node classes used by `SqlAstValidator` so that security regressions caused by dependency upgrades are caught before deployment.

### Acceptance Criteria

- [ ] `sqlglot` upper bound added to `pyproject.toml`: `"sqlglot>=20.0.0,<30.0.0"` (both `[project.optional-dependencies].sql` and `[project.optional-dependencies].dev`)
- [ ] New test class `TestSqlglotVersionContract` in `tests/unit/test_sql_validator.py`
- [ ] Contract test iterates over `_BLOCKED_STMT_TYPES` and asserts each class name exists as an attribute on `sqlglot.expressions`
- [ ] Contract test iterates over `_STMT_TYPE_TO_KEYWORD` keys and asserts each maps to a class in `sqlglot.expressions`
- [ ] Test is skipped (not failed) when sqlglot is not installed (use `pytest.importorskip`)
- [ ] `mypy --strict` passes; no new dependencies

### Implementation Notes

- Upper bound `<30.0.0` is conservative: sqlglot uses minor-version bumps for AST changes; a major version bump is the highest-risk boundary
- The contract test is a canary: it will fail if `sqlglot.expressions.Drop` is renamed to `sqlglot.expressions.DropStatement` or similar
- Import `_BLOCKED_STMT_TYPES` and `_STMT_TYPE_TO_KEYWORD` directly from `argent.security.sql_validator` to test the actual runtime values, not a hardcoded list

### Files to Modify

- `pyproject.toml` — add upper bound to sqlglot in both `[sql]` and `[dev]` extras
- `tests/unit/test_sql_validator.py` — add `TestSqlglotVersionContract` class

### Commit Messages

```
test: RED — add failing sqlglot version contract test (P7-T03)
fix: add sqlglot upper bound <30.0.0 and version contract test (P7-T03)
```

---

## Phase 7 Completion Checklist

```bash
poetry run pytest tests/ -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/ examples/
poetry run ruff format --check src/ tests/ examples/
poetry run bandit -c pyproject.toml -r src/ examples/
poetry run pre-commit run --all-files
```
