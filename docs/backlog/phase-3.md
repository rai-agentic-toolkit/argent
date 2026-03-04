# Phase 3: Budgeting & Execution Isolation — The Leash

> **Goal**: Replace `tool-leash`. Build stateful execution budget enforcement and a safe tool invocation wrapper that physically prevents infinite loops, runaway token usage, and unhandled native tool exceptions.

**Status**: Not Started
**Progress**: 0/2 tasks complete

**Business Rules enforced here**: BR-01 (Absolute Budget Enforcement)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P3-T01 | Implement Stateful Token & Call Counters | Not Started | P1 Complete |
| P3-T02 | Build Tool Execution Wrapper | Not Started | P3-T01 |

---

## P3-T01: Implement Stateful Token & Call Counters

**Description**: Implement the `RequestBudget` class that maintains stateful counters for `call_count` and `token_count` within an agent's lifetime. It enforces configurable hard limits and raises a `BudgetExhaustedError` the instant any limit is crossed — with no possibility of bypass (BR-01).

**Status**: Not Started

### User Story

As an operator, I need the framework to halt agent execution the instant it crosses a defined call or token budget so that a runaway agent cannot consume unbounded compute or API spend — no exceptions, no workarounds.

### Acceptance Criteria

- [ ] `RequestBudget` defined in `src/argent/budget/budget.py`
- [ ] Constructor: `RequestBudget(max_calls: int, max_tokens: int)`
- [ ] `RequestBudget.record_call(tokens_used: int) -> None` increments both counters
- [ ] `record_call` raises `BudgetExhaustedError` immediately if **either** limit is exceeded after the increment
- [ ] `BudgetExhaustedError` carries context: which limit was hit, current count, configured max
- [ ] `RequestBudget.remaining_calls -> int` property returns remaining call budget
- [ ] `RequestBudget.remaining_tokens -> int` property returns remaining token budget
- [ ] `RequestBudget` accepts budget exhaustion callbacks: `RequestBudget.on_exhausted(fn: Callable[["RequestBudget"], None])`
- [ ] Budget is NOT resetable — immutable once constructed (BR-01 is absolute)
- [ ] `AgentContext` carries a `budget: RequestBudget` field (modify `context.py`)
- [ ] Zero external dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED):
   - Test normal calls increment counters correctly
   - Test that exceeding `max_calls` raises `BudgetExhaustedError`
   - Test that exceeding `max_tokens` raises `BudgetExhaustedError`
   - Test that `remaining_calls` and `remaining_tokens` are accurate
   - Test that registered callbacks fire on exhaustion
2. Implement `RequestBudget` and `BudgetExhaustedError` (GREEN)
3. Update `AgentContext` to include `budget: RequestBudget`
4. Refactor

### Test Expectations

**File**: `tests/unit/test_budget.py`

```python
def test_record_call_increments_counters():
    """call_count and token_count increment correctly."""

def test_raises_on_max_calls_exceeded():
    """BudgetExhaustedError raised when call_count > max_calls."""

def test_raises_on_max_tokens_exceeded():
    """BudgetExhaustedError raised when token_count > max_tokens."""

def test_remaining_calls_accurate():
    """remaining_calls returns max_calls - call_count."""

def test_exhaustion_callback_fires():
    """Registered on_exhausted callback is called exactly once."""

def test_budget_not_resetable():
    """There is no reset() method — budget is immutable after construction."""
```

### Files to Create/Modify

- Create: `src/argent/budget/__init__.py`
- Create: `src/argent/budget/budget.py`
- Modify: `src/argent/pipeline/context.py` (add `budget: RequestBudget` field)
- Create: `tests/unit/test_budget.py`

### Commit Messages

```
test: add failing tests for RequestBudget
```
```
feat: implement stateful token and call budget enforcement

- Define RequestBudget with max_calls and max_tokens hard limits
- record_call() raises BudgetExhaustedError immediately on violation (BR-01)
- Exhaustion callbacks via on_exhausted()
- remaining_calls and remaining_tokens properties
- Add budget field to AgentContext
- Zero external dependencies
```

---

## P3-T02: Build Tool Execution Wrapper

**Description**: Implement the `ToolExecutor` middleware that wraps native tool calls with timeout enforcement, recursion trap, and exception capture. It consults the `RequestBudget` before each call and records the usage after. It is the canonical way all tools are invoked in an ARG-wrapped agent.

**Status**: Not Started

### User Story

As an agent consumer, I need all my tool calls routed through a safe execution wrapper so that timeouts, recursion bombs, and unexpected native exceptions are trapped cleanly — without crashing my host process.

### Acceptance Criteria

- [ ] `ToolExecutor` defined in `src/argent/budget/executor.py`
- [ ] `ToolExecutor.execute(tool: Callable[..., Any], *args, token_cost: int = 0, **kwargs) -> Any`
- [ ] Checks `context.budget` before executing; raises `BudgetExhaustedError` if already exhausted
- [ ] Calls `context.budget.record_call(token_cost)` immediately after successful invocation
- [ ] Enforces per-call timeout via `concurrent.futures.ThreadPoolExecutor` (stdlib only): `ToolExecutor(timeout_seconds: float = 30.0)`
- [ ] Raises `ToolTimeoutError` if timeout exceeded
- [ ] Traps `RecursionError` and raises `ToolRecursionError` with clear message
- [ ] All other native tool exceptions are re-raised as-is (not swallowed)
- [ ] `ToolTimeoutError` and `ToolRecursionError` in `src/argent/budget/exceptions.py`
- [ ] Zero external dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED):
   - Test normal tool invocation returns result and increments budget
   - Test timeout raises `ToolTimeoutError`
   - Test recursion raises `ToolRecursionError`
   - Test pre-exhausted budget blocks tool before invocation
   - Test that generic tool exceptions propagate unchanged
2. Implement `ToolExecutor` and exceptions (GREEN)
3. Refactor

### Test Expectations

**File**: `tests/unit/test_executor.py`

```python
def test_execute_returns_tool_result():
    """Normal tool invocation returns the correct result."""

def test_execute_records_budget():
    """budget.record_call is called with the correct token_cost."""

def test_execute_raises_on_timeout():
    """A tool that sleeps > timeout raises ToolTimeoutError."""

def test_execute_raises_on_recursion():
    """A recursive tool raises ToolRecursionError."""

def test_execute_blocked_on_exhausted_budget():
    """A pre-exhausted budget raises BudgetExhaustedError before tool is called."""

def test_tool_exception_propagates():
    """An exception raised by the tool is not wrapped or swallowed."""
```

### Files to Create/Modify

- Create: `src/argent/budget/executor.py`
- Create: `src/argent/budget/exceptions.py`
- Create: `tests/unit/test_executor.py`

### Commit Messages

```
test: add failing tests for ToolExecutor wrapper
```
```
feat: implement ToolExecutor with timeout and recursion protection

- Define ToolExecutor with configurable timeout via ThreadPoolExecutor
- ToolTimeoutError on timeout; ToolRecursionError on RecursionError
- Budget check before invocation; budget.record_call() after success
- Native tool exceptions propagate unchanged
- Zero external dependencies
```

---

## Phase 3 Completion Checklist

Before moving to Phase 4, verify:

```bash
poetry run pytest tests/unit/test_budget.py tests/unit/test_executor.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```

> Phase 4 (The Trimmer) requires both Phase 2 and Phase 3 to be complete before starting.
