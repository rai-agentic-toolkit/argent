# ADR-0004 — Budget/Context Coupling and Async Execution Strategy

**Status**: Accepted
**Date**: 2026-03-07
**Deciders**: Architecture reviewer, core team
**Phase**: P3-T01/T02 (The Leash — RequestBudget + ToolExecutor)

---

## Context

During the GREEN phase of P3-T01/T02 two design decisions were made without
explicit documentation:

1. **Coupling direction** — `RequestBudget` was added as a field on
   `AgentContext` (`pipeline/context.py`), making `pipeline/` depend on
   `budget/`.  Per ADR-0001, `pipeline/` is the lowest-level shared
   foundation that all other epics depend on.  Adding a `budget/` import into
   `pipeline/` creates an upward dependency cycle.

2. **Async correctness** — `ToolExecutor.execute()` was implemented as a
   synchronous method using `concurrent.futures.ThreadPoolExecutor` with a
   blocking `.result(timeout=...)` call.  All middleware in the pipeline is
   `async def` (ADR-0002); a synchronous executor would block the event loop
   during tool execution, defeating the purpose of the async contract.

---

## Decisions

### Decision 1 — Remove `budget` from `AgentContext` (Option A)

`RequestBudget` is **not** added to `AgentContext`.  Instead, `ToolExecutor`
accepts `budget: RequestBudget | None` as a direct constructor argument.

**Rationale**

- Preserves the dependency direction mandated by ADR-0001: `budget/` depends
  on `pipeline/` (for `AgentContext`), never the reverse.
- `ToolExecutor` is the only consumer of `RequestBudget` at invocation time;
  passing it directly is the simplest correct factoring.
- Callers that need a budget-aware executor compose the two objects at the
  call site — no ambient coupling through the context object.

**Rejected alternative (Option B)**

Keep `budget` on `AgentContext` but accept the inverted dependency.  Rejected
because: (a) it introduces a direct cycle violation of ADR-0001; (b) it makes
`AgentContext` aware of an Epic-3-specific concern; (c) the cycle would
propagate to any future epic that imports `AgentContext`.

### Decision 2 — `async def execute()` with `asyncio.wait_for` + `run_in_executor`

`ToolExecutor.execute()` is `async def`.  Tool invocation runs in a
thread-pool thread via `asyncio.get_running_loop().run_in_executor(None, ...)`.
Timeout is enforced by `asyncio.wait_for(timeout=...)`, which raises the
built-in `TimeoutError` (Python 3.11+, confirmed by `requires-python = ">=3.11"`).

**Rationale**

- Complies with ADR-0002: all pipeline-callable entry points must be
  `async def` so callers can `await` them inside `Pipeline.run()`.
- `run_in_executor(None, ...)` uses Python's default thread pool, keeping
  synchronous tools from blocking the event loop.
- `asyncio.wait_for` integrates cleanly with the event loop's cooperative
  scheduling; no manual `Future.cancel()` calls needed.
- `TimeoutError` (Python 3.11+ built-in) subsumes `asyncio.TimeoutError`
  and `concurrent.futures.TimeoutError` — a single `except TimeoutError`
  clause covers all cases.

**Abandoned thread behaviour**

When `wait_for` times out, the underlying thread continues running until the
tool returns or raises naturally — Python threads cannot be forcibly killed.
This is the same limitation as the original synchronous implementation.
Callers should pass well-behaved (finite) tools to avoid orphaned threads.

### Decision 3 — `check_precall(token_cost)` on `RequestBudget`

All pre-call budget arithmetic is encapsulated in
`RequestBudget.check_precall(token_cost)`.  `ToolExecutor` calls this method
rather than reading `remaining_calls` / `remaining_tokens` directly.

**Rationale**

- Removes arithmetic from the executor (Single Responsibility).
- Fixes the asymmetric pre-check bug (`remaining_tokens < 0` vs
  `remaining_calls <= 0`) at the source: `check_precall` raises when
  `token_cost > remaining_tokens` (consistent with `record_call`'s
  `> max_tokens` semantics).
- Provides a stable, testable entry point for pre-execution budget
  enforcement that any future executor variant can reuse.

---

## Consequences

- `AgentContext` has no knowledge of `RequestBudget`.  Code that previously
  set `ctx.budget = budget` must instead pass `budget` directly to
  `ToolExecutor(budget=budget)`.
- `ToolExecutor.execute()` must be `await`-ed; synchronous callers cannot use
  it without an event loop.  This is intentional and consistent with the
  pipeline's async-first design.
- `RequestBudget.check_precall()` is now part of the public API surface and
  is covered by unit tests.
