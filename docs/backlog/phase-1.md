# Phase 1: Core Pipeline & AgentContext State Machine

> **Goal**: Build the foundational highway — the `AgentContext` data structure, the middleware pipeline, and the observability hooks — before any individual feature is added.

**Status**: Complete
**Progress**: 3/3 tasks complete

**NFRs enforced here**: Zero-Copy / Single-Pass Parsing, Zero-Dependency Core

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P1-T01 | Define `AgentContext` Object | Complete | P0 Complete |
| P1-T02 | Implement Base Middleware Pipeline | Complete | P1-T01 |
| P1-T03 | Build Telemetry/Observability Hooks | Complete | P1-T02 |

---

## P1-T01: Define `AgentContext` Object

**Description**: Define the central `AgentContext` dataclass that flows through every stage of the ARG middleware pipeline. It is the single source of truth for all pipeline state: raw payload, parsed AST, token counts, call counts, and execution state.

**Status**: Not Started

### User Story

As the middleware pipeline, I need a single, typed container to carry all agent state through every stage so that downstream middlewares never need to re-parse or re-compute already-available data.

### Acceptance Criteria

- [ ] `AgentContext` is defined in `src/argent/pipeline/context.py`
- [ ] Fields include: `raw_payload: bytes`, `parsed_ast: Any | None`, `token_count: int`, `call_count: int`, `execution_state: ExecutionState` (an `Enum`)
- [ ] `ExecutionState` enum has at minimum: `PENDING`, `RUNNING`, `HALTED`, `COMPLETE`
- [ ] `AgentContext` is a frozen or partially-frozen dataclass (parsed_ast is mutable, others are immutable after creation)
- [ ] Full type annotations throughout; `mypy --strict` passes
- [ ] 90%+ test coverage
- [ ] Zero external dependencies (stdlib only)

### Implementation Steps

1. Write failing tests (RED):
   - Test that `AgentContext` can be instantiated with required fields
   - Test that `execution_state` transitions are valid
   - Test that `raw_payload` is stored as `bytes`
   - Test that `parsed_ast` defaults to `None`
2. Implement `src/argent/pipeline/context.py` (GREEN)
3. Refactor if needed

### Test Expectations

**File**: `tests/unit/test_context.py`

```python
def test_agent_context_instantiation():
    """AgentContext is created with correct defaults."""

def test_execution_state_enum_values():
    """ExecutionState has PENDING, RUNNING, HALTED, COMPLETE."""

def test_raw_payload_stored_as_bytes():
    """raw_payload field is bytes, not str."""

def test_parsed_ast_defaults_to_none():
    """parsed_ast is None until parser middleware runs."""

def test_token_count_defaults_to_zero():
    """token_count starts at 0."""
```

### Files to Create/Modify

- Create: `src/argent/pipeline/context.py`
- Create: `tests/unit/test_context.py`

### Commit Messages

```
test: add failing tests for AgentContext
```
```
feat: implement AgentContext state machine object

- Define AgentContext dataclass with raw_payload, parsed_ast,
  token_count, call_count, and execution_state
- Implement ExecutionState enum (PENDING, RUNNING, HALTED, COMPLETE)
- Full mypy strict compliance, zero external dependencies
```

---

## P1-T02: Implement Base Middleware Pipeline

**Description**: Implement the four-stage middleware pipeline (Ingress → Pre-Execution → Execution → Egress) that routes an `AgentContext` through a configurable chain of middleware handlers. Each stage is an ordered list of callables that mutate the `AgentContext` in place.

**Status**: Not Started

### User Story

As a developer integrating ARG, I need a composable middleware pipeline so that I can plug in ingress validators, budget enforcers, and output trimmers in any order without modifying the core pipeline logic.

### Acceptance Criteria

- [ ] `Pipeline` class defined in `src/argent/pipeline/pipeline.py`
- [ ] `Pipeline` accepts four typed lists of middleware callables: `ingress`, `pre_execution`, `execution`, `egress`
- [ ] `Pipeline.run(context: AgentContext) -> AgentContext` executes all stages in order
- [ ] Each middleware is typed as `Callable[[AgentContext], None]`
- [ ] If any middleware raises, the exception propagates — no silent swallowing (BR-Graceful Degradation does NOT mean ignoring errors in the pipeline)
- [ ] `Pipeline` can be constructed with empty stage lists (no-op pipeline)
- [ ] Zero external dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED)
2. Implement `Pipeline` class (GREEN)
3. Refactor

### Test Expectations

**File**: `tests/unit/test_pipeline.py`

```python
def test_empty_pipeline_returns_context():
    """A pipeline with no middlewares returns the context unchanged."""

def test_ingress_middleware_executed_first():
    """Ingress middlewares run before pre_execution middlewares."""

def test_stage_order_is_ingress_pre_exec_exec_egress():
    """All four stages execute in strict order."""

def test_middleware_exception_propagates():
    """An exception raised inside a middleware is not swallowed."""

def test_middleware_can_mutate_context():
    """A middleware that mutates parsed_ast is reflected downstream."""
```

### Files to Create/Modify

- Create: `src/argent/pipeline/pipeline.py`
- Create: `tests/unit/test_pipeline.py`

### Commit Messages

```
test: add failing tests for base middleware pipeline
```
```
feat: implement four-stage middleware pipeline

- Define Pipeline class with ingress, pre_execution, execution, egress stages
- Each stage is an ordered list of Callable[[AgentContext], None]
- Exceptions propagate; no silent swallowing
- Zero external dependencies
```

---

## P1-T03: Build Telemetry/Observability Hooks

**Description**: Implement a lightweight, structured logging and event-emission layer that fires on every pipeline stage transition. Output must be structured JSON and OpenTelemetry-compatible (even if OTel SDK is not present — emit dict events that can be forwarded).

**Status**: Not Started

### User Story

As an operator of an ARG-wrapped agent, I need structured pipeline events emitted at every stage so that I can trace exactly what happened to a payload — which middleware ran, how long it took, and whether budget limits were approached.

### Acceptance Criteria

- [ ] `Telemetry` class defined in `src/argent/pipeline/telemetry.py`
- [ ] Emits a structured event dict at the start and end of each pipeline stage
- [ ] Events include: `stage`, `timestamp_ms`, `duration_ms`, `context_state` snapshot
- [ ] Default handler writes events as JSON lines to `stderr` (zero dependencies)
- [ ] Custom handler can be registered via `Telemetry.register_handler(fn: Callable[[dict], None])`
- [ ] `Pipeline` integrates `Telemetry` automatically (no opt-in required per middleware)
- [ ] Zero external dependencies; OTel SDK is an optional extra, not a requirement
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED)
2. Implement `Telemetry` class (GREEN)
3. Wire `Telemetry` into `Pipeline.run()` (wrap each stage call)
4. Refactor

### Test Expectations

**File**: `tests/unit/test_telemetry.py`

```python
def test_telemetry_emits_event_per_stage():
    """Four stage transitions produce four event pairs (start + end)."""

def test_event_contains_required_fields():
    """Each event dict has stage, timestamp_ms, duration_ms."""

def test_custom_handler_receives_events():
    """A registered custom handler is called for every event."""

def test_default_handler_writes_json():
    """Default handler output is valid JSON."""

def test_telemetry_does_not_crash_on_handler_error():
    """If a telemetry handler raises, the pipeline continues (telemetry is non-fatal)."""
```

### Files to Create/Modify

- Create: `src/argent/pipeline/telemetry.py`
- Modify: `src/argent/pipeline/pipeline.py` (wire telemetry into stage execution)
- Create: `tests/unit/test_telemetry.py`

### Commit Messages

```
test: add failing tests for telemetry/observability hooks
```
```
feat: implement telemetry hooks for pipeline stage transitions

- Define Telemetry class with start/end event emission per stage
- Default handler writes JSON lines to stderr (zero dependencies)
- Custom handlers registerable via Telemetry.register_handler()
- Wire Telemetry into Pipeline.run(); telemetry errors are non-fatal
```

---

## Phase 1 Completion Checklist

Before moving to Phase 2 / 3, verify:

```bash
poetry run pytest tests/unit/test_context.py tests/unit/test_pipeline.py tests/unit/test_telemetry.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```
