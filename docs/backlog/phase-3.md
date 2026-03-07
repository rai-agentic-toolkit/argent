# Phase 3: Budgeting & Execution Isolation — The Leash

> **Goal**: Replace `tool-leash`. Build stateful execution budget enforcement and a safe tool invocation wrapper that physically prevents infinite loops, runaway token usage, and unhandled native tool exceptions.

**Status**: Complete
**Progress**: 3/3 tasks complete

**Business Rules enforced here**: BR-01 (Absolute Budget Enforcement)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P3-T01 | Implement Stateful Token & Call Counters | Complete | P1 Complete |
| P3-T02 | Build Tool Execution Wrapper | Complete | P3-T01 |
| P3-T03 | Wire `ExecutionState` Transitions in `Pipeline.run()` | Complete | P3-T01 |

---

## P3-T01: Implement Stateful Token & Call Counters

**Description**: Implement the `RequestBudget` class that maintains stateful counters for `call_count` and `token_count` within an agent's lifetime. It enforces configurable hard limits and raises a `BudgetExhaustedError` the instant any limit is crossed — with no possibility of bypass (BR-01).

**Status**: Complete

### Acceptance Criteria (as implemented)

- [x] `RequestBudget` defined in `src/argent/budget/budget.py`
- [x] Constructor: `RequestBudget(max_calls: int, max_tokens: int)`
- [x] `RequestBudget.record_call(tokens_used: int) -> None` increments both counters
- [x] `record_call` raises `BudgetExhaustedError` immediately if **either** limit is exceeded after the increment
- [x] `BudgetExhaustedError` carries context: which limit was hit, current count, configured max
- [x] `RequestBudget.remaining_calls -> int` property returns remaining call budget
- [x] `RequestBudget.remaining_tokens -> int` property returns remaining token budget
- [x] `RequestBudget.check_precall(token_cost: int) -> None` — pre-execution guard that raises before the tool runs if either limit would be exceeded (added during P3 arch review)
- [x] `RequestBudget` accepts budget exhaustion callbacks: `RequestBudget.on_exhausted(fn: Callable[["RequestBudget"], None])`
- [x] Budget is NOT resetable — immutable once constructed (BR-01 is absolute)
- [x] ~~`AgentContext` carries a `budget: RequestBudget` field~~ — **REVERTED** by arch review (ADR-0004): budget is passed directly to `ToolExecutor`, not stored on context. `AgentContext` has no knowledge of `RequestBudget`.
- [x] Zero external dependencies
- [x] 90%+ test coverage (100% achieved)

### Architecture Note (ADR-0004)

The original spec said to add `budget: RequestBudget | None` to `AgentContext`. This was implemented in the GREEN phase but reverted during the architecture review. Reason: `pipeline/` is the lowest-level foundation (ADR-0001); adding a `budget/` import into `pipeline/context.py` created an upward dependency cycle. `ToolExecutor` now accepts `budget` as a direct constructor argument. See ADR-0004 for the full decision record.

---

## P3-T02: Build Tool Execution Wrapper

**Description**: Implement the `ToolExecutor` async wrapper that wraps native tool calls with timeout enforcement, recursion trap, and pre-call budget guard. It is the canonical way all tools are invoked in an ARG-wrapped agent.

**Status**: Complete

### Acceptance Criteria (as implemented)

- [x] `ToolExecutor` defined in `src/argent/budget/executor.py`
- [x] `ToolExecutor(budget: RequestBudget | None = None, timeout_seconds: float = 30.0)`
- [x] `async def execute(tool, /, *args, token_cost: int = 0, **kwargs) -> _T` — parameterised with `TypeVar _T`
- [x] Calls `budget.check_precall(token_cost)` before executing; raises `BudgetExhaustedError` if already (or would be) exhausted
- [x] Calls `budget.record_call(token_cost)` immediately after successful invocation
- [x] `execute()` is `async def`; tool runs in a thread via `asyncio.wait_for + loop.run_in_executor(None, ...)` — event loop is never blocked
- [x] Raises `ToolTimeoutError` if timeout exceeded (catches built-in `TimeoutError`, Python 3.11+)
- [x] Traps `RecursionError` and raises `ToolRecursionError` with clear message
- [x] All other native tool exceptions re-raised as-is (not swallowed)
- [x] Budget NOT charged if tool raises — `record_call` only called on success
- [x] `ToolTimeoutError` and `ToolRecursionError` in `src/argent/budget/exceptions.py`
- [x] Zero external dependencies (stdlib `asyncio` only)
- [x] 90%+ test coverage (100% achieved)

### Architecture Note (ADR-0004)

Original spec referenced `context.budget` and synchronous `concurrent.futures.ThreadPoolExecutor`. Both were changed during the architecture review: (1) `budget` is a direct constructor arg, not read from context; (2) `execute()` is `async def` to comply with ADR-0002's async middleware contract. See ADR-0004.

---

## P3-T03: Wire `ExecutionState` Transitions in `Pipeline.run()`

**Description**: `AgentContext.ExecutionState` has four values (`PENDING`, `RUNNING`, `HALTED`, `COMPLETE`) but `Pipeline.run()` currently never transitions state. Only `HALTED` is set, by individual validators. This task wires the two missing transitions: `RUNNING` before the first stage and `COMPLETE` after the last.

**Status**: Complete

### User Story

As an operator monitoring pipeline execution, I need `context.execution_state` to accurately reflect the current lifecycle so that telemetry handlers, dashboards, and post-run assertions can distinguish between a pipeline that is actively running, one that completed cleanly, and one that was halted by a validator or exception.

### Acceptance Criteria

- [x] `Pipeline.run()` sets `context.execution_state = ExecutionState.RUNNING` before iterating the first stage
- [x] `Pipeline.run()` sets `context.execution_state = ExecutionState.COMPLETE` after all stages finish without exception
- [x] `HALTED` continues to be set by individual middlewares (validators, security policies) — the pipeline does not set it
- [x] If a middleware raises an unhandled exception and the pipeline propagates it, `execution_state` is left as `RUNNING` (not explicitly set to `HALTED` by the pipeline — the raising middleware is responsible)
- [x] Existing telemetry try/finally guarantee is preserved unchanged
- [x] All existing pipeline tests continue to pass
- [x] New tests added for the RUNNING and COMPLETE transitions (TestExecutionStateTransitions — 5 tests)

### Implementation Steps

1. Write failing tests (RED):
   - Test that `execution_state` is `RUNNING` during middleware execution
   - Test that `execution_state` is `COMPLETE` after `run()` returns
   - Test that `execution_state` remains as set by middleware when middleware halts
2. Add two `context.execution_state = ...` assignments to `Pipeline.run()` (GREEN)
3. Refactor

### Test Expectations

**File**: `tests/unit/test_pipeline.py` (extend existing)

```python
async def test_execution_state_is_running_during_middleware():
    """context.execution_state is RUNNING while middleware is executing."""

async def test_execution_state_is_complete_after_run():
    """context.execution_state is COMPLETE after Pipeline.run() returns."""

async def test_execution_state_halted_preserved_from_middleware():
    """If a middleware sets HALTED and raises, HALTED is preserved."""
```

### Files to Modify

- Modify: `src/argent/pipeline/pipeline.py`
- Modify: `tests/unit/test_pipeline.py`

### Commit Messages

```
test: add failing tests for ExecutionState pipeline transitions
```
```
feat: wire RUNNING/COMPLETE ExecutionState transitions into Pipeline.run()

- Set RUNNING before first stage, COMPLETE after last stage
- HALTED remains the responsibility of individual middlewares
- Preserves existing telemetry try/finally guarantee
```

---

## Phase 3 Completion Checklist

```bash
poetry run pytest tests/unit/test_budget.py tests/unit/test_executor.py tests/unit/test_pipeline.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```

> Phase 4 (The Trimmer) requires both Phase 2 and Phase 3 core tasks (P3-T01, P3-T02) to be complete. P3-T03 can run in parallel with Phase 4 since it only touches `pipeline/`.
