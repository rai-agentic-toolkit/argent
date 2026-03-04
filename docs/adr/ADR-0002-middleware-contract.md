# ADR-0002: Middleware Contract — Async Callable, Exception Propagation, Telemetry Guarantee

**Date**: 2026-03-04
**Status**: Accepted
**Deciders**: Architecture Review (P1-T01/T02/T03)

---

## Context

Phase 1 establishes the `Pipeline` class as the core execution primitive for ARG.  Every
subsequent Epic (Ingress/Epic 2, Budget/Epic 3, Trimmer/Epic 4, Security/Epic 5) will
contribute middleware callables to one or more pipeline stages.  The type and calling
convention of `Middleware` is therefore the single most consequential API decision in the
codebase — locking it as synchronous at the foundation layer would force a breaking
signature change the first time any Epic touches an I/O-bound operation.

---

## Decision

### 1. Middleware is an async callable

```python
from collections.abc import Awaitable, Callable
from argent.pipeline.context import AgentContext

Middleware = Callable[[AgentContext], Awaitable[None]]
```

All middleware implementations **must** be `async def` functions or async callables.
`Pipeline.run()` is itself `async def` and `await`s each middleware in sequence.

**Rationale**: Agent tool calls (Epic 3: Budget), schema fetch (Epic 5: Security), and
single-pass I/O parsing (Epic 2: Ingress) are all inherently I/O-bound.  Defining the
contract as async from the start avoids a breaking change when the first such middleware
arrives.  Synchronous middlewares that perform no I/O have zero overhead from being
declared `async def`.

### 2. Exceptions from middleware propagate unchanged

`Pipeline.run()` does **not** catch exceptions raised by middleware.  The exception
propagates to the caller unmodified.  This is an explicit design choice: ARG is a
deterministic wrapper, not a retry framework.

**Rationale**: Swallowing exceptions would mask bugs, make budget-enforcement violations
invisible, and violate the "no silent failures" rule in the CONSTITUTION (Priority 1).
Error recovery is the caller's responsibility.

### 3. Telemetry `stage_end` is guaranteed via `try/finally`

Even when middleware raises, the `Telemetry.emit_end()` call for the current stage is
guaranteed via a `try/finally` block in `Pipeline.run()`.  This ensures the telemetry
stream never produces a `stage_start` without a matching `stage_end`.

**Rationale**: Unpaired telemetry events would make it impossible for operators to
determine which stage caused a failure.  The `try/finally` guarantee costs nothing and
eliminates an entire class of observability blind spots.

### 4. Telemetry handlers are non-fatal

Individual telemetry handler errors are caught, a diagnostic is written to `stderr`, and
the next handler continues.  A broken handler never crashes the pipeline.

**Rationale**: Telemetry is a side-car concern.  A deployment configuration error (e.g.,
a misconfigured log shipper) must not bring down the agent being observed.

---

## Consequences

### Positive

- Epics 2–5 can write `async def` middlewares without API changes.
- No breaking change to `Pipeline.run()` when async I/O arrives.
- Telemetry stream is always structurally valid (no orphaned events).
- Observability failures are visible on `stderr` but non-fatal.

### Negative / Trade-offs

- All middleware authors must declare `async def` even for CPU-only operations.
- Tests that construct `Pipeline` must be `async def` test functions.
- The codebase requires `pytest-asyncio` (already a dev dependency).

### Neutral

- The synchronous `Telemetry._emit()` dispatcher is acceptable for `stderr` I/O since
  that call is synchronous and non-blocking at the OS level.  If a handler ever needs to
  be async (e.g., shipping to a remote collector), `Telemetry` will need a separate ADR.

---

## Alternatives Considered

### Synchronous `Middleware` with thread-executor fallback

Keep `Middleware = Callable[[AgentContext], None]` and wrap async operations in
`asyncio.run_in_executor()` inside individual middlewares.

**Rejected**: This pushes the async complexity down into every middleware implementation,
produces inconsistent calling conventions, and does not compose cleanly with `async with`
resource managers (e.g., HTTP session lifecycle).

### `Union[sync, async]` middleware with `inspect.iscoroutinefunction()` dispatch

Support both sync and async callables, dispatch dynamically based on
`inspect.iscoroutinefunction()`.

**Rejected**: Runtime type dispatch on callables is fragile, bypasses mypy's type system,
and creates an invisible fork in the execution model that is hard to test exhaustively.
