# Phase 9: Composition & Ergonomics

> **Goal**: Connect the pieces that were built but never wired together.
> Add the missing `AgentContext.output` field that makes egress trimming a first-class
> pipeline stage.  Rewrite the example to model the correct threat.  Clean up the docs.

**Status**: Not Started
**Progress**: 0/3 tasks complete

**Dependencies**: Phase 8 complete (P9-T01 depends on the fixed `ContextBudgetCalculator`
from P8-T01; P9-T02 depends on `AgentContext.output` from P9-T01)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P9-T01 | `AgentContext.output` + `TrimmerMiddleware` | Not Started | P8 complete |
| P9-T02 | Rewrite `examples/basic_agent.py` — correct threat model | Not Started | P9-T01 complete |
| P9-T03 | README & installation story cleanup; ADR-0007 | Not Started | P9-T01/T02 complete |

---

## P9-T01: `AgentContext.output` + `TrimmerMiddleware`

**Description**: The current `AgentContext` carries `raw_payload` (ingress) and
`parsed_payload` (post-parse) but has no field for what the execution stage *produces*.
Tool results, LLM responses, and database query results are held outside the context
by the caller.  This prevents the pipeline from routing output through an egress
trimmer without the caller writing connector boilerplate every time.

Two deliverables ship together:

**1. `AgentContext.output: str | None = None`**
A new mutable field for the execution result.  Middlewares in the `execution` stage
write here.  Middlewares in the `egress` stage read and transform it.  Unlike
`raw_payload`, `output` is mutable — callers and middlewares may overwrite it at any
egress stage.

**2. `TrimmerMiddleware`** (`src/argent/trimmer/middleware.py`)
An async egress middleware that reads `context.output`, computes `max_chars` from the
active budget via `ContextBudgetCalculator`, applies any `Trimmer`, and writes the
result back.  No-op when `context.output is None`.

New Business Rule **BR-05**: Egress output integrity — egress middlewares that transform
output must operate on `context.output` and write the result back to `context.output`.

**Status**: Not Started

**ADR**: ADR-0007 — documents `output` field design, `TrimmerMiddleware` composition
pattern, and BR-05.

### User Story

As an agent developer, I need a single egress middleware that reads my tool result from
the pipeline context, trims it to fit the remaining token budget, and writes it back —
so I don't write the same five-line connection in every project.

### Acceptance Criteria

**`AgentContext.output`**:
- [ ] Field exists with type `str | None`, default `None`
- [ ] Mutable — middlewares can set and overwrite it freely
- [ ] No immutability guard (unlike `raw_payload`)
- [ ] Exported via `argent.__init__` (implicitly — it's on `AgentContext`)
- [ ] `__repr__` reflects the field

**`TrimmerMiddleware`**:
- [ ] Located at `src/argent/trimmer/middleware.py`
- [ ] `@dataclass` with fields: `trimmer: Trimmer`, `budget: RequestBudget`,
  `calculator: ContextBudgetCalculator`
- [ ] `async def __call__(self, context: AgentContext) -> None`
- [ ] No-op when `context.output is None` (does not raise)
- [ ] Calls `self.calculator.compute(self.budget)` to get `max_chars`
- [ ] Calls `self.trimmer.trim(context.output)` with that budget
- [ ] Writes result back to `context.output`
- [ ] Exported from `argent.__init__` as `TrimmerMiddleware`
- [ ] Emits `argent.trimmer` INFO log when trimming occurs (delegated to the
  wrapped `Trimmer` — no additional log in `TrimmerMiddleware` itself)

**Integration**:
- [ ] Integration test demonstrates full cycle:
  - execution middleware sets `ctx.output = json.dumps(large_dict)`
  - `TrimmerMiddleware(trimmer=JsonDictTrimmer(...), budget=budget, calculator=calc)`
    in the `egress` stage trims it
  - `ctx.output` after pipeline completes is within the expected char budget

### Implementation Notes

- `TrimmerMiddleware` accepts any `Trimmer` (satisfies the Protocol) — callers choose
  the format-appropriate trimmer
- The `calculator.compute(budget)` result becomes the `max_chars` for the trimmer;
  the `Trimmer` itself is constructed externally (its `max_chars` is fixed at
  construction, but `TrimmerMiddleware` constructs a *new trimmer call* per request
  using the dynamically computed budget... wait — `Trimmer.trim()` accepts the content
  but the max_chars is set at `Trimmer.__init__`.  Resolution: `TrimmerMiddleware`
  does not hold a `Trimmer` instance directly; it holds a `Trimmer` *factory*:
  `trimmer_factory: Callable[[int], Trimmer]` — called with the computed `max_chars`
  on each request.  Alternatively, reconsider the `Trimmer` protocol to accept
  `max_chars` in `trim()`.
- **Preferred resolution**: `TrimmerMiddleware` holds `trimmer_factory: Callable[[int], Trimmer]`
  where callers pass e.g. `trimmer_factory=JsonDictTrimmer` (the class itself, since
  `JsonDictTrimmer(max_chars)` is the factory call).  This is clean and type-safe.
- ADR-0007 documents this design decision.

### Commit Sequence

```
test: RED — failing tests for AgentContext.output and TrimmerMiddleware (P9-T01)
feat: add AgentContext.output field; TrimmerMiddleware; BR-05; ADR-0007 (P9-T01)
```

---

## P9-T02: Rewrite `examples/basic_agent.py` — Correct Threat Model

**Description**: The current example calls Claude, then runs Claude's *response* through
`ByteSizeValidator` and `DepthLimitValidator` — treating the LLM's bounded API response
as adversarial input.  The validators are designed for untrusted user-submitted data, not
for responses from a known API.

The correct threat model for an agentic system:

1. **User submits a query** (untrusted) → ingress validation
2. **LLM decides to call a tool** with arguments (potentially malicious via prompt injection)
   → the tool arguments are the untrusted surface
3. **Tool executes** via `ToolExecutor` under budget control
4. **Tool result is stored** in `ctx.output`
5. **Egress**: `TrimmerMiddleware` trims `ctx.output` to fit the remaining token budget

The rewritten example demonstrates this model.  The pipeline is constructed **once at
module level**, not inside `run()` on every call.

**Status**: Not Started

### Acceptance Criteria

- [ ] `_build_pipeline()` or equivalent is called **once at module level**, not inside `run()`
- [ ] Ingress validates **user-supplied input** (e.g. a query or simulated tool call
  argument), not the LLM's response
- [ ] `ctx.output` is set by the execution stage middleware
- [ ] `TrimmerMiddleware` appears in the `egress` stage
- [ ] `SqlAstValidator` appears in `security_validators` — the example demonstrates
  SQL injection blocking on tool arguments
- [ ] Example still runs end-to-end with `ANTHROPIC_API_KEY` set
- [ ] Comments explain *why* each component is at its stage, not just *what* it does
- [ ] `basic_agent.py` passes ruff, mypy, and bandit in CI (already in scope from P6)

### Commit Sequence

```
feat: rewrite basic_agent.py with correct threat model and pipeline-level construction (P9-T02)
```

---

## P9-T03: README & Installation Story Cleanup

**Description**: Three concrete documentation gaps:

1. **Installation section contradicts CLAUDE.md** — README shows `pip install -e ".[dev]"`
   with no mention of Poetry; CLAUDE.md mandates `poetry run` for all commands.
2. **Usage examples are stale** — `ContextBudgetCalculator` snippet uses the old API;
   no example shows `TrimmerMiddleware` or `AgentContext.output`.
3. **Coverage figure is stale** — README title shows "99.41%" from Phase 6; post-P8/P9
   the number will change.

**Status**: Not Started

### Acceptance Criteria

- [ ] Installation section shows: `poetry install` (canonical), then `pip install -e "."` as
  an alternative with a note that quality gates require `poetry run`
- [ ] `ContextBudgetCalculator` snippet uses `reserved_tokens=` (not the old dead param)
- [ ] New "With output trimming" usage example shows `TrimmerMiddleware` in the egress stage
  using `ctx.output`
- [ ] "With security validation" example shows `SqlAstValidator(blocked_types=...)` to
  demonstrate the new configurability from P8-T03
- [ ] Coverage figure updated to match `poetry run pytest --cov` output after Phase 8/9
- [ ] ADR table updated with ADR-0006 and ADR-0007
- [ ] "What's Shipped" table updated with Phase 8/9 deliverables
- [ ] Business Rules table updated with BR-05
- [ ] `__version__ = "0.2.0"` reflected in README header (or removed if too brittle)

### Commit Sequence

```
docs: update README for v0.2.0 — installation, API changes, TrimmerMiddleware (P9-T03)
```
