# Phase 5: Pluggable Security Policies — The Guard

> **Goal**: Replace the flawed `CallGuard`. Build a semantic, AST-based security policy layer that evaluates tool inputs via structured parsing — never via naive substring matching.

**Status**: Not Started
**Progress**: 0/2 tasks complete

**Business Rules enforced here**: BR-03 (Semantic Over Syntactic Security)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P5-T01 | Define `SecurityValidator` Protocol | Not Started | P4 Complete |
| P5-T02 | Implement SQL AST Validator | Not Started | P5-T01 |

---

## P5-T01: Define `SecurityValidator` Protocol

**Description**: Define the `SecurityValidator` protocol — the extension point for all pluggable security policies in ARG. Wire it into the `Pipeline` pre-execution stage so any registered validators are applied before tools run.

**Status**: Not Started

### User Story

As an operator, I need a clean, typed interface that I can implement to add project-specific security policies so that the framework is extensible without forking core pipeline code.

### Acceptance Criteria

- [ ] `SecurityValidator` `Protocol` defined in `src/argent/security/base.py`
- [ ] Protocol method: `def validate(self, context: AgentContext) -> None`
- [ ] On violation: validate raises `SecurityViolationError` with a human-readable reason
- [ ] `SecurityViolationError` defined in `src/argent/security/exceptions.py`
- [ ] `SecurityViolationError` carries: `policy_name: str`, `reason: str`
- [ ] `Pipeline` accepts `security_validators: list[SecurityValidator]` and applies them in pre-execution stage
- [ ] An empty `security_validators` list is a valid (no-op) configuration
- [ ] Zero external dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests for protocol wiring (RED)
2. Define `SecurityValidator` protocol and `SecurityViolationError` (GREEN)
3. Wire validators into `Pipeline` pre-execution stage
4. Refactor

### Test Expectations

**File**: `tests/unit/test_security_base.py`

```python
def test_pipeline_applies_validators_in_pre_execution():
    """Validators are called before the execution stage."""

def test_security_violation_halts_pipeline():
    """A validator raising SecurityViolationError propagates from Pipeline.run()."""

def test_empty_validators_list_is_noop():
    """Pipeline with no validators runs normally."""

def test_security_violation_error_has_policy_name_and_reason():
    """SecurityViolationError carries policy_name and reason fields."""
```

### Files to Create/Modify

- Create: `src/argent/security/__init__.py`
- Create: `src/argent/security/base.py`
- Create: `src/argent/security/exceptions.py`
- Modify: `src/argent/pipeline/pipeline.py` (add `security_validators` parameter)
- Create: `tests/unit/test_security_base.py`

### Commit Messages

```
test: add failing tests for SecurityValidator protocol
```
```
feat: define SecurityValidator protocol and wire into pipeline

- SecurityValidator Protocol with validate(context) -> None
- SecurityViolationError with policy_name and reason fields
- Pipeline accepts security_validators list; applied in pre_execution stage
- BR-03: semantic-only evaluation; no substring matching in core
```

---

## P5-T02: Implement SQL AST Validator

**Description**: Implement the first concrete `SecurityValidator` — a SQL semantic validator that uses `sqlglot` to parse SQL payloads found in `AgentContext.parsed_ast` and blocks destructive DML operations (`DROP`, `DELETE`, `TRUNCATE`, `ALTER`). `sqlglot` is an optional extra — if not installed, the validator raises `ImportError` with a clear message at construction time.

**Status**: Not Started

### User Story

As an operator running ARG-wrapped agents with database tool access, I need SQL inputs validated semantically via AST parsing so that no agent can execute destructive queries via prompt injection or confusion — even if the query is obfuscated with comments or unusual whitespace.

### Acceptance Criteria

- [ ] `SqlAstValidator` defined in `src/argent/security/sql_validator.py`
- [ ] `SqlAstValidator` implements `SecurityValidator` protocol
- [ ] Uses `sqlglot.parse` to build an AST from the SQL payload
- [ ] Raises `SecurityViolationError` if AST contains: `DROP`, `DELETE`, `TRUNCATE`, or `ALTER` statements
- [ ] Raises `SecurityViolationError` (not `ImportError`) with a clear advisory message if `sqlglot` is not installed
- [ ] Skips validation without error if `context.parsed_ast` is not a SQL string (non-SQL contexts)
- [ ] `SqlAstValidator` is listed as an optional extra in `pyproject.toml`: `[project.optional-dependencies] sql = ["sqlglot>=20.0.0"]`
- [ ] 90%+ test coverage (mock `sqlglot` in tests that test the import-error path)

### Implementation Steps

1. Write failing tests (RED) — mock `sqlglot` where needed
2. Implement `SqlAstValidator` (GREEN)
3. Add `sqlglot` optional extra to `pyproject.toml`
4. Refactor

### Test Expectations

**File**: `tests/unit/test_sql_validator.py`

```python
def test_sql_validator_passes_safe_select():
    """A SELECT query passes without raising."""

def test_sql_validator_blocks_drop():
    """A DROP TABLE query raises SecurityViolationError."""

def test_sql_validator_blocks_delete():
    """A DELETE query raises SecurityViolationError."""

def test_sql_validator_blocks_truncate():
    """A TRUNCATE query raises SecurityViolationError."""

def test_sql_validator_skips_non_sql_context():
    """A context with a dict parsed_ast is skipped without error."""

def test_sql_validator_raises_on_missing_sqlglot(monkeypatch):
    """SecurityViolationError raised with advisory message if sqlglot missing."""
```

### Files to Create/Modify

- Create: `src/argent/security/sql_validator.py`
- Modify: `pyproject.toml` (add `[project.optional-dependencies] sql = ["sqlglot>=20.0.0"]`)
- Create: `tests/unit/test_sql_validator.py`

### Commit Messages

```
test: add failing tests for SQL AST validator
```
```
feat: implement SQL AST validator with sqlglot (optional extra)

- SqlAstValidator uses sqlglot to parse SQL and block destructive DML
- Blocks DROP, DELETE, TRUNCATE, ALTER (BR-03: semantic, not substring)
- sqlglot is optional extra; clear error if not installed
- Skips gracefully for non-SQL payloads
```

---

## Phase 5 Completion Checklist

This phase completes the MVP. Before declaring the MVP done, run the full integration check:

```bash
poetry run pytest tests/ -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run bandit -c pyproject.toml -r src/
poetry run vulture src/
poetry run pre-commit run --all-files
```

### MVP Definition of Done Verification

The MVP is complete when the following scenario passes end-to-end:

1. Construct a `Pipeline` with:
   - Ingress: `ByteSizeValidator(max_bytes=52_428_800)`, `SinglePassParser()`
   - Pre-execution: `SqlAstValidator()`
   - Execution: agent tool loop via `ToolExecutor(timeout_seconds=5.0)`
   - Egress: `ContextBudgetCalculator` + `JsonDictTrimmer`
2. Feed a 50MB malformed JSON payload → `PayloadTooLargeError` raised cleanly
3. Feed a `DROP TABLE users` SQL payload → `SecurityViolationError` raised cleanly
4. Feed an infinite-loop tool → `ToolTimeoutError` raised cleanly after 5s
5. **No memory leak, no unhandled host exception, no process crash.**
