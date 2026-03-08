# Phase 8: API Integrity

> **Goal**: Correct the broken, misleading, and untestable parts of the existing API before they calcify.
> All four tasks are correctness fixes, not new features.  Phase 8 culminates in a **v0.2.0** version bump.

**Status**: In Progress
**Progress**: 0/4 tasks complete

**Dependencies**: Phase 7 complete

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P8-T01 | Fix `ContextBudgetCalculator` — dead parameter + broken README example | Not Started | Phase 4 complete |
| P8-T02 | Rename `AgentContext.parsed_ast` → `parsed_payload` | Not Started | P8-T01 complete |
| P8-T03 | Make `SqlAstValidator` configurable via `blocked_types` | Not Started | Phase 5 complete |
| P8-T04 | Test suite hygiene — remove coverage theater, fix private field access | Not Started | Phase 3 complete |

*Recommended order: T01, T04, T03, T02 (rename last — touches the most files).*

---

## P8-T01: Fix `ContextBudgetCalculator`

**Description**: `ContextBudgetCalculator.__init__` accepts a required `context_window_tokens` argument
that is stored in `self._context_window_tokens` and never read by any method.  The README
Usage section calls `ContextBudgetCalculator(reserved_tokens=500)` which is a `TypeError`
at runtime — `reserved_tokens` does not exist as a parameter.

**Root cause**: The Phase 4 design reserved `context_window_tokens` for a future tiktoken
integration (TODO-P6-T02) that was never implemented.  Phase 6 closed without the integration
and the dead parameter remained.

**Fix**: Replace `context_window_tokens: int` with `reserved_tokens: int = 0`.
`reserved_tokens` is the number of tokens to hold back from `budget.remaining_tokens`
before computing the character budget — e.g. reserve 500 tokens for the model's own
completion so the trimmer doesn't use the entire headroom.

New formula: `raw = int(max(0, budget.remaining_tokens - reserved_tokens) * chars_per_token)`

`reserved_tokens=0` (default) reproduces the current behavior exactly for callers not
passing a first argument.

**Status**: Not Started

**ADR**: ADR-0006 (documents v0.2.0 breaking changes including this rename)

### User Story

As a library caller computing the egress char budget, I need `ContextBudgetCalculator`
to accept a `reserved_tokens` argument so I can hold back headroom for the model's own
response before allocating to the trimmer.

### Acceptance Criteria

- [ ] `ContextBudgetCalculator(reserved_tokens=0)` produces the same output as the
  current `ContextBudgetCalculator(context_window_tokens=N)` for any `N`
- [ ] `ContextBudgetCalculator(reserved_tokens=500).compute(budget)` returns
  `int(max(0, budget.remaining_tokens - 500) * chars_per_token)` floored at 256
- [ ] When `reserved_tokens >= budget.remaining_tokens`, result is 256 (the floor)
- [ ] `context_window_tokens` parameter removed — passing it raises `TypeError`
- [ ] README example `ContextBudgetCalculator(reserved_tokens=500)` no longer raises
- [ ] New tests cover: zero reserved tokens, partial reservation, full reservation
  (floor), and custom `chars_per_token` combined with reserved tokens
- [ ] Existing `test_calculator.py` updated — no `context_window_tokens` references remain

### Implementation Notes

- Change is in `src/argent/trimmer/calculator.py` only
- Update `README.md` Usage section (ContextBudgetCalculator snippet)
- Update the `TODO(P6-T02): tiktoken integration` comment — drop it (the decision
  not to integrate tiktoken should be acknowledged, not left as a stale TODO)
- No ADR needed beyond the v0.2.0 ADR-0006 that P8-T02 will create

### Commit Sequence

```
test: RED — failing tests for ContextBudgetCalculator reserved_tokens (P8-T01)
feat: fix ContextBudgetCalculator — reserved_tokens replaces context_window_tokens (P8-T01)
```

---

## P8-T02: Rename `AgentContext.parsed_ast` → `parsed_payload`

**Description**: `AgentContext.parsed_ast` holds a value of type
`dict | list | ET.Element | str | None` — none of which are Abstract Syntax Trees.
The field name is misleading.  The `ParsedPayload` TypeAlias (already correct) names
the concept accurately; the field should match it.

This is the sweeping rename of Phase 8.  It touches every file that reads or writes
`context.parsed_ast` or `ctx.parsed_ast`.

**Version bump**: `__version__ = "0.1.0"` → `"0.2.0"` in `src/argent/__init__.py`.

**ADR-0006**: Capture the rationale for both breaking changes in this phase.

**Status**: Not Started

### Affected Files (complete list)

Source:
- `src/argent/pipeline/context.py` — field declaration
- `src/argent/ingress/parser.py` — sets `context.parsed_ast`
- `src/argent/security/sql_validator.py` — reads `context.parsed_ast`
- `src/argent/__init__.py` — version bump

Examples:
- `examples/basic_agent.py` — reads `ctx.parsed_ast`

Tests (all unit + integration):
- `tests/unit/test_context.py`
- `tests/unit/test_parser.py`
- `tests/unit/test_sql_validator.py`
- `tests/unit/test_ingress_validators.py` (if any references)
- `tests/integration/test_pipeline_end_to_end.py`

Docs:
- `README.md` — Usage examples
- `docs/backlog/phase-*.md` — any references to `parsed_ast`
- `docs/adr/ADR-0002-middleware-contract.md` — references the field name
- `docs/RETRO_LOG.md` — historical references (leave as-is — retrospective log
  is a historical record, not a specification)

### Acceptance Criteria

- [ ] `AgentContext.parsed_payload` field exists and behaves identically to the old
  `parsed_ast` field
- [ ] `AgentContext.parsed_ast` does not exist — no compatibility alias
- [ ] `ParsedPayload` TypeAlias unchanged (already the correct name)
- [ ] All 279 tests pass (with field name updated)
- [ ] `__version__ == "0.2.0"` in `src/argent/__init__.py`
- [ ] ADR-0006 created: documents both breaking changes (T01 + T02) and v0.2.0 bump
- [ ] README updated: all `parsed_ast` references → `parsed_payload`
- [ ] ADR-0002 updated: `parsed_ast` → `parsed_payload` in field description

### Implementation Notes

- Use a global search-and-replace across the entire repository, then verify manually
- The RETRO_LOG historical entries may reference `parsed_ast` — leave them (they are
  retrospective records of what the code was, not specifications of what it is)
- Strategy: do the rename atomically in a single commit after all tests pass

### Commit Sequence

```
test: RED — update all test references parsed_ast → parsed_payload (P8-T02)
feat: rename AgentContext.parsed_ast → parsed_payload; bump v0.2.0; ADR-0006 (P8-T02)
```

---

## P8-T03: Make `SqlAstValidator` Configurable

**Description**: `SqlAstValidator()` blocks exactly four statement types
(`Drop`, `Delete`, `TruncateTable`, `Alter`) with no configuration.
Callers who need to block `Create`, `Grant`, or stored-procedure calls must
write a new class from scratch.  A `blocked_types` constructor argument closes this gap
without breaking existing behavior.

**Status**: Not Started

### User Story

As a security engineer using ARG in a read-only analytics environment, I need to configure
`SqlAstValidator` to also block `CREATE TABLE` without forking the library.

### Acceptance Criteria

- [ ] `SqlAstValidator()` (no args) behavior is **identical** to today
- [ ] `SqlAstValidator(blocked_types=frozenset({"Drop", "Create"}))` blocks only
  DROP and CREATE; DELETE/TRUNCATE/ALTER pass through
- [ ] Construction raises `ValueError` (not `SecurityViolationError`) if any provided
  class name does not exist in `sqlglot.expressions` — fail-fast at startup, not at
  first validation call
- [ ] `_STMT_TYPE_TO_KEYWORD` extended with at least: `Create → CREATE`,
  `Grant → GRANT`, `AlterTable → ALTER TABLE`, `Command → COMMAND`
  (keyword lookup for error messages; callers can reference these names)
- [ ] The P7-T03 canary tests remain green — they now test both the default
  and the custom `blocked_types` paths
- [ ] New tests cover: custom blocked_types, invalid class name raises ValueError,
  empty frozenset blocks nothing (passes all SQL through)

### Implementation Notes

- `blocked_types` parameter type: `frozenset[str] | None = None`
- When `None`: use `_BLOCKED_STMT_TYPES` module-level default (backward compatible)
- When provided: validate each name against `sqlglot.expressions` at `__init__` time
  (same check as the P7-T03 contract tests — use `importorskip` in tests)
- `_STMT_TYPE_TO_KEYWORD` is module-level and can be extended without breaking callers
  (they never needed to enumerate it; it is internal to error formatting)

### Commit Sequence

```
test: RED — failing tests for configurable SqlAstValidator blocked_types (P8-T03)
feat: add blocked_types to SqlAstValidator; extend _STMT_TYPE_TO_KEYWORD (P8-T03)
```

---

## P8-T04: Test Suite Hygiene

**Description**: Two categories of test quality debt accumulated during Phase 1 and Phase 3:

**Category A — Coverage theater** (`test_context.py`):
`TestExecutionState` contains four tests (`test_has_pending`, `test_has_running`,
`test_has_halted`, `test_has_complete`) that assert enum members are truthy.
Enum members are truthy by definition in Python; these tests cannot catch any
real regression.  Replace them with one test that exercises the actual state
machine contract from ADR-0002.

**Category B — Private field access** (`test_pipeline_end_to_end.py`):
Three integration tests access `budget._call_count` directly.  `RequestBudget`
exposes `remaining_calls` as a public property; the tests should use it.

**Status**: Not Started

### Acceptance Criteria

**Category A**:
- [ ] `test_has_pending`, `test_has_running`, `test_has_halted`, `test_has_complete`
  removed from `tests/unit/test_context.py`
- [ ] Replaced by `test_execution_state_lifecycle` (or similar) that asserts:
  - Fresh `AgentContext` starts at `PENDING`
  - After `pipeline.run()` the state is `COMPLETE` (happy path)
  - After a middleware raises, the state is `RUNNING` (not `COMPLETE`) unless the
    middleware explicitly sets `HALTED`
  - These are the three meaningful invariants from ADR-0002 § State Machine Contract
- [ ] `test_values_are_distinct` may stay (it is at least non-trivially asserting
  the enum has no duplicate values, which can't be trivially satisfied accidentally)

**Category B**:
- [ ] Zero occurrences of `budget._call_count` in any test file
- [ ] Replaced with equivalent expressions using the public API:
  - `budget._call_count == N` → `budget.max_calls - budget.remaining_calls == N`
  - `budget._call_count == calls_before` → `budget.remaining_calls == calls_before_remaining`
- [ ] All affected assertions remain logically equivalent

### Implementation Notes

- For Category A: the new lifecycle test can use an `async` test function with
  `@pytest.mark.asyncio` — it needs to call `pipeline.run()`.  A minimal pipeline
  with one stub middleware is sufficient.
- For Category B: capture `calls_before = budget.remaining_calls` before the
  operation, then assert `budget.remaining_calls == calls_before` after.
  This is cleaner than the current pattern.

### Commit Sequence

```
test: replace enum theater tests with state-machine lifecycle test (P8-T04)
test: replace budget._call_count private access with public API (P8-T04)
```

*Note: both commits in this task are test-only — no source changes.  The "RED" phase
is the removal of wrong tests; the "GREEN" phase is the addition of correct tests.
This is a legitimate test-rewrite task, not a standard RED/GREEN cycle.*
