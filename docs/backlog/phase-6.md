# Phase 6: Post-MVP Polish

> **Goal**: Harden the delivered MVP with a working end-to-end example, configurable thread pool isolation for concurrent agent deployments, and an improved depth heuristic that eliminates false positives from tool output containing brackets in string values.

**Status**: Complete
**Progress**: 0/3 tasks complete

**Dependencies**: Phase 5 complete (MVP delivered)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P6-T01 | Working End-to-End Example | Complete | P5 Complete |
| P6-T02 | Thread Pool Isolation for `ToolExecutor` | Complete | P5 Complete |
| P6-T03 | `DepthLimitValidator` Heuristic Improvement | Complete | P5 Complete |

---

## P6-T01: Working End-to-End Example

**Description**: Create `examples/basic_agent.py` — a self-contained script that wires ARG around a real Claude API call, demonstrating the full pipeline in action: payload ingress, budget enforcement, tool execution via `ToolExecutor`, and output trimming. This is the primary onboarding artifact for new developers evaluating the framework.

**Status**: Complete

### User Story

As a developer evaluating ARG for my project, I need a complete, runnable example that shows exactly how to wrap a real LLM agent with the framework so that I can judge whether it solves my problem and how much effort integration requires.

### Acceptance Criteria

- [ ] `examples/basic_agent.py` exists and is runnable with `poetry run python examples/basic_agent.py`
- [ ] Demonstrates: `Pipeline` construction with ingress validators, `SinglePassParser`, `ToolExecutor` with budget, and at least one `Trimmer` in egress
- [ ] Uses real Claude API (`claude-sonnet-4-6` or latest available) via the `anthropic` SDK
- [ ] `anthropic` SDK added to `pyproject.toml` as an optional extra: `[project.optional-dependencies] examples = ["anthropic>=0.25.0"]`
- [ ] Script handles `BudgetExhaustedError`, `ToolTimeoutError`, and `PayloadTooLargeError` explicitly with clean user-facing messages
- [ ] Requires `ANTHROPIC_API_KEY` environment variable; exits cleanly with instructions if not set
- [ ] Script is < 150 lines; annotated comments explain each pipeline stage
- [ ] No PII committed — uses a hard-coded fictional prompt, not real user data

### Files to Create/Modify

- Create: `examples/basic_agent.py`
- Modify: `pyproject.toml` (add `examples` optional extra)
- Modify: `.gitignore` (ensure `examples/*.log` and `examples/output/` are excluded)

### Commit Messages

```
feat: add basic_agent.py end-to-end example (P6-T01)

- Demonstrates full ARG pipeline: ingress → budget → tool execution → trimming
- Uses Claude API via anthropic SDK (optional extra)
- Handles BudgetExhaustedError, ToolTimeoutError, PayloadTooLargeError explicitly
```

---

## P6-T02: Thread Pool Isolation for `ToolExecutor`

**Description**: `ToolExecutor.execute()` currently calls `loop.run_in_executor(None, ...)`, which uses the process-wide default thread pool (`ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4))`). Under concurrent agent load — multiple agents each running long-lived tools simultaneously — this shared pool is a bottleneck and can be exhausted. This task exposes a `max_workers` parameter and optionally accepts a custom `Executor`.

**Status**: Complete

### Background

Python's default thread pool is shared across all `run_in_executor(None, ...)` calls in a process. If 20 agents each block a thread for 25 seconds (within the 30-second timeout), the pool can be exhausted, causing new tool calls to queue rather than execute. For single-agent deployments this is not an issue; for concurrent deployments it is a real production concern.

The previous synchronous implementation used a per-call `ThreadPoolExecutor(max_workers=1)` which gave better isolation at the cost of per-call pool creation overhead. The async refactor improved event-loop compliance but introduced this shared-pool tradeoff.

### User Story

As an operator running multiple concurrent ARG-wrapped agents in the same process, I need to configure the thread pool size for tool execution so that agents do not compete for a fixed thread budget that was sized for single-agent use.

### Acceptance Criteria

- [ ] `ToolExecutor` accepts optional `max_workers: int | None = None` constructor argument
- [ ] When `max_workers` is `None` (default), behaviour is unchanged: uses `run_in_executor(None, ...)` (process default pool)
- [ ] When `max_workers` is set, `ToolExecutor` creates and owns a dedicated `ThreadPoolExecutor(max_workers=max_workers)` for its lifetime
- [ ] Owned pool is shut down cleanly when the executor is garbage collected (`__del__` or context manager)
- [ ] Alternatively (and preferably), `ToolExecutor` accepts `executor: concurrent.futures.Executor | None = None` directly — callers who need fine-grained control pass their own pool; `ToolExecutor` does not own it in this case
- [ ] Existing behaviour with `executor=None` / `max_workers=None` is unchanged
- [ ] ADR-0004 amended to document the thread pool decision and the isolation tradeoff
- [ ] 90%+ test coverage for new paths

### Files to Modify

- Modify: `src/argent/budget/executor.py`
- Modify: `docs/adr/ADR-0004-budget-context-coupling.md` (add thread pool section)
- Modify: `tests/unit/test_executor.py` (add coverage for new params)

### Commit Messages

```
feat: add configurable thread pool isolation to ToolExecutor (P6-T02)

- Optional executor param: pass custom Executor or set max_workers
- Default behaviour (None) unchanged: uses process-wide default pool
- Documents shared-pool tradeoff in ADR-0004
```

---

## P6-T03: `DepthLimitValidator` Heuristic Improvement

**Description**: The current bracket-counting depth estimator (`DepthLimitValidator._estimate_depth`) counts `{` and `[` in raw bytes without regard for whether they appear inside quoted string values. A JSON payload like `{"message": "connect to {host}:{port}"}` scores depth 3, not 1. This over-estimation can reject valid tool output (code snippets, log lines, template strings) when `max_depth` is tuned tightly.

**Status**: Complete

### Background

The original design intentionally over-estimates depth ("err on the side of caution"). This is correct for *ingress* payloads from untrusted sources. However, validated tool output that is fed back into the pipeline as a new request can trigger false positives. A simple improvement — tracking whether the byte scan is inside a double-quoted string — eliminates the false-positive class without adding significant complexity.

### Acceptance Criteria

- [ ] `DepthLimitValidator._estimate_depth` updated to skip brackets inside double-quoted string literals
- [ ] Quote tracking handles escaped quotes (`\"`) correctly
- [ ] Performance: the scan remains O(n) single-pass over raw bytes
- [ ] Existing tests updated; new tests added for the string-bracket false-positive case:
  - `{"key": "value with {braces} and [brackets]"}` scores depth 1, not 3
  - Escaped quote `{"key": "say \"hello {world}\""}` scores depth 1
  - Legitimately nested `{"a": {"b": [1, 2]}}` scores depth 3 (unchanged)
- [ ] `mypy --strict` passes; no new dependencies

### Files to Modify

- Modify: `src/argent/ingress/validators.py`
- Modify: `tests/unit/test_validators.py`

### Commit Messages

```
fix: improve DepthLimitValidator bracket counting to skip string contents (P6-T03)

- Quote-aware scan eliminates false positives for payloads with brackets
  inside string values (log lines, code snippets, template strings)
- Handles escaped quotes; remains O(n) single-pass
```

---

## Phase 6 Completion Checklist

```bash
poetry run pytest tests/ -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/ examples/
poetry run bandit -c pyproject.toml -r src/ examples/
poetry run pre-commit run --all-files
# Smoke test the example (requires ANTHROPIC_API_KEY):
poetry run python examples/basic_agent.py
```
