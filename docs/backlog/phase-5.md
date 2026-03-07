# Phase 5: Pluggable Security Policies — The Guard

> **Goal**: Replace the flawed `CallGuard`. Build a semantic, AST-based security policy layer that evaluates tool inputs via structured parsing — never via naive substring matching. Complete the MVP with integration tests, a public API surface, and the end-to-end DoD scenario.

**Status**: Not Started
**Progress**: 0/4 tasks complete

**Business Rules enforced here**: BR-03 (Semantic Over Syntactic Security)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P5-T01 | Define `SecurityValidator` Protocol | Not Started | P4 Complete |
| P5-T02 | Implement SQL AST Validator | Not Started | P5-T01 |
| P5-T03 | Integration Test Suite (MVP DoD) | Not Started | P5-T02 |
| P5-T04 | Public API Surface | Not Started | P5-T03 |

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
async def test_pipeline_applies_validators_in_pre_execution():
    """Validators are called before the execution stage."""

async def test_security_violation_halts_pipeline():
    """A validator raising SecurityViolationError propagates from Pipeline.run()."""

async def test_empty_validators_list_is_noop():
    """Pipeline with no validators runs normally."""

def test_security_violation_error_has_policy_name_and_reason():
    """SecurityViolationError carries policy_name and reason fields."""
```

### Files to Create/Modify

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

**Description**: Implement the first concrete `SecurityValidator` — a SQL semantic validator that uses `sqlglot` to parse SQL payloads found in `AgentContext.parsed_ast` and blocks destructive DML operations (`DROP`, `DELETE`, `TRUNCATE`, `ALTER`). `sqlglot` is an optional extra — if not installed, the validator raises a clear error at construction time.

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
- [ ] `sqlglot` listed as optional extra in `pyproject.toml`: `[project.optional-dependencies] sql = ["sqlglot>=20.0.0"]`
- [ ] 90%+ test coverage (mock `sqlglot` in tests that test the import-error path)

### Implementation Steps

1. Write failing tests (RED) — mock `sqlglot` where needed
2. Implement `SqlAstValidator` (GREEN)
3. Add `sqlglot` optional extra to `pyproject.toml`
4. Refactor

### Test Expectations

**File**: `tests/unit/test_sql_validator.py`

```python
def test_sql_validator_passes_safe_select(): ...
def test_sql_validator_blocks_drop(): ...
def test_sql_validator_blocks_delete(): ...
def test_sql_validator_blocks_truncate(): ...
def test_sql_validator_skips_non_sql_context(): ...
def test_sql_validator_raises_on_missing_sqlglot(monkeypatch): ...
```

### Files to Create/Modify

- Create: `src/argent/security/sql_validator.py`
- Modify: `pyproject.toml` (add `sql` optional extra)
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

## P5-T03: Integration Test Suite (MVP DoD)

**Description**: Write the end-to-end integration tests that prove the assembled pipeline works as a complete system. This is the only place in the test suite where all five Epic components are wired together. These tests validate the MVP Definition of Done from REQUIREMENTS.md §6.

**Status**: Not Started

### Why This Matters

Unit tests verify components in isolation. They cannot catch integration gaps — places where components don't compose correctly, where exceptions from one layer aren't handled by another, or where the pipeline contract is subtly violated at a seam. Three phases of code have been built without a single test that wires them together. This task closes that gap.

### User Story

As a developer evaluating ARG, I need a runnable test that proves the assembled pipeline handles the worst-case adversarial scenarios — oversized payload, SQL injection, infinite loop tool — cleanly and without crashing the host process. This is the integration evidence that the framework is ready to use.

### Acceptance Criteria

- [ ] `tests/integration/test_pipeline_end_to_end.py` created
- [ ] Test 1: Oversized payload — `ByteSizeValidator(max_bytes=100)` rejects a 200-byte payload with `PayloadTooLargeError`; `execution_state` is `HALTED`
- [ ] Test 2: SQL injection — `SqlAstValidator` rejects `DROP TABLE users` with `SecurityViolationError`; pipeline propagates it cleanly
- [ ] Test 3: Infinite-loop tool — `ToolExecutor(timeout_seconds=0.1)` raises `ToolTimeoutError` for a `time.sleep(5)` tool; budget not charged
- [ ] Test 4: Budget exhaustion — `RequestBudget(max_calls=1)` exhausted after first tool call; second call raises `BudgetExhaustedError` before tool runs
- [ ] Test 5: Happy path — valid JSON payload passes all validators, is parsed and attached to `parsed_ast`, trimmer keeps output within budget, `execution_state` is `COMPLETE`
- [ ] Each test builds a `Pipeline` from components; no mocks of ARG internals
- [ ] All integration tests pass in CI

### Implementation Steps

1. Write all five integration tests (they are the RED phase — they should fail until all prior phases are complete)
2. Run against the full assembled stack (GREEN — if all unit-tested phases are done, these should pass)
3. Add to CI pipeline checklist

### Test Expectations

**File**: `tests/integration/test_pipeline_end_to_end.py`

```python
async def test_oversized_payload_halts_pipeline(): ...
async def test_sql_injection_raises_security_violation(): ...
async def test_infinite_loop_tool_raises_timeout(): ...
async def test_budget_exhaustion_blocks_second_call(): ...
async def test_happy_path_full_pipeline_completes(): ...
```

### Files to Create

- Create: `tests/integration/test_pipeline_end_to_end.py`

### Commit Messages

```
test: add end-to-end integration tests for MVP DoD scenarios (P5-T03)
```

---

## P5-T04: Public API Surface

**Description**: `argent/__init__.py` currently exports only `__version__`. As a library, consumers must currently write `from argent.budget.budget import RequestBudget` — a brittle internal path that exposes package structure. This task establishes a stable public API by re-exporting core types from the top-level package.

**Status**: Not Started

### User Story

As a developer integrating ARG into my agent, I need `from argent import Pipeline, AgentContext, RequestBudget, ToolExecutor` to work so that I can depend on a stable public interface without coupling to internal module paths that may change between versions.

### Acceptance Criteria

- [ ] `argent/__init__.py` re-exports: `Pipeline`, `AgentContext`, `ExecutionState`
- [ ] `argent/__init__.py` re-exports: `RequestBudget`, `ToolExecutor`
- [ ] `argent/__init__.py` re-exports exception types: `BudgetExhaustedError`, `ToolTimeoutError`, `ToolRecursionError`, `PayloadTooLargeError`, `NestingDepthError`
- [ ] `argent/__init__.py` re-exports: `ByteSizeValidator`, `DepthLimitValidator`, `SinglePassParser`
- [ ] `argent/__init__.py` re-exports trimmer types: `Trimmer` (protocol), all four concrete trimmer classes, `ContextBudgetCalculator`
- [ ] `argent/__init__.py` re-exports security types: `SecurityValidator` (protocol), `SecurityViolationError`, `SqlAstValidator`
- [ ] `__all__` defined explicitly to control `from argent import *` surface
- [ ] Integration tests updated to import from `argent` directly (not from internal paths)
- [ ] `mypy --strict` passes

### Implementation Steps

1. Write a test that imports all public types from `argent` directly (RED)
2. Add re-exports and `__all__` to `argent/__init__.py` (GREEN)
3. Update integration test imports to use public paths

### Test Expectations

**File**: `tests/unit/test_public_api.py`

```python
def test_core_types_importable_from_argent():
    """Pipeline, AgentContext, ExecutionState importable from argent."""

def test_budget_types_importable_from_argent():
    """RequestBudget, ToolExecutor, BudgetExhaustedError importable from argent."""

def test_ingress_types_importable_from_argent():
    """Validators and SinglePassParser importable from argent."""

def test_trimmer_types_importable_from_argent():
    """Trimmer protocol and all concrete trimmers importable from argent."""
```

### Files to Create/Modify

- Modify: `src/argent/__init__.py`
- Create: `tests/unit/test_public_api.py`

### Commit Messages

```
test: add failing tests for public API imports from argent top-level
```
```
feat: establish public API surface in argent/__init__.py

- Re-export all core types from pipeline, budget, ingress, trimmer, security
- Define __all__ for stable public interface
- Consumers can now use: from argent import Pipeline, AgentContext, ...
```

---

## Phase 5 Completion Checklist

This phase completes the MVP. Before declaring done, run:

```bash
poetry run pytest tests/ -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run bandit -c pyproject.toml -r src/
poetry run vulture src/
poetry run pre-commit run --all-files
```

### MVP Definition of Done

The MVP is complete when `tests/integration/test_pipeline_end_to_end.py` passes in full — covering the oversized payload, SQL injection, infinite loop, budget exhaustion, and happy-path scenarios — and `from argent import Pipeline` works without touching internal module paths.
