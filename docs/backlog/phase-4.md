# Phase 4: Semantic Context Shaping — The Trimmer

> **Goal**: Replace `output-trimmer` and `context-diet`. Build format-aware output truncators that preserve structural integrity (BR-02), and a dynamic budget calculator that automatically sizes output to fit the remaining LLM context window.

**Status**: Not Started
**Progress**: 0/3 tasks complete

**Business Rules enforced here**: BR-02 (No Blind Truncation)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P4-T00 | Resolve `ParsedPayload` Type Alias | Not Started | P2 + P3 Complete |
| P4-T01 | Implement Format-Aware Output Truncators | Not Started | P4-T00 |
| P4-T02 | Build Dynamic Budget Calculator | Not Started | P4-T01 |

---

## P4-T00: Resolve `ParsedPayload` Type Alias

**Description**: `context.py` contains `ParsedPayload: TypeAlias = Any` with a `TODO(P2-T01)` comment that was never closed when Phase 2 shipped. `parsed_ast` is typed `Any`, which strips type inference from every consumer — including the Phase 4 Trimmer, which needs to dispatch on the actual type. This task defines a concrete union type before any Trimmer code is written.

**Status**: Not Started

### User Story

As a downstream middleware author, I need `AgentContext.parsed_ast` to have a precise type so that mypy can verify I am handling all possible parse outcomes (dict, list, Element, str, None) and the Trimmer can dispatch correctly without runtime isinstance chains on an untyped `Any`.

### Acceptance Criteria

- [ ] `ParsedPayload` union type defined, replacing `Any`: covers `dict[str, Any]`, `list[Any]`, `xml.etree.ElementTree.Element`, `str`, and `None`
- [ ] `AgentContext.parsed_ast` typed as `ParsedPayload`
- [ ] `TODO(P2-T01)` comment removed from `context.py`
- [ ] `mypy --strict` passes with the new type
- [ ] All existing tests continue to pass (no new tests required — this is a type-level fix)

### Implementation Steps

1. Import `xml.etree.ElementTree` (stdlib) under `TYPE_CHECKING` in `context.py`
2. Define `ParsedPayload: TypeAlias = dict[str, Any] | list[Any] | ET.Element | str | None`
3. Update `AgentContext.parsed_ast` field type annotation
4. Verify `mypy --strict` passes; fix any downstream type errors surfaced

### Files to Modify

- Modify: `src/argent/pipeline/context.py`

### Commit Messages

```
fix: resolve ParsedPayload TypeAlias — replace Any with concrete union type

- ParsedPayload covers dict | list | ET.Element | str | None
- Closes TODO(P2-T01) from Phase 2
- mypy strict passes; no behaviour change
```

---

## P4-T01: Implement Format-Aware Output Truncators

**Description**: Implement a family of format-aware truncators — Python Traceback, Markdown Table, JSON Array, and JSON Dict — that compress oversized payloads while always preserving structural integrity (BR-02).

**Status**: Not Started

### User Story

As the egress stage, I need to shorten oversized tool output to a `max_chars` budget without destroying the structural information an LLM needs to interpret it, so that context windows are not silently corrupted.

### Acceptance Criteria

- [ ] `Trimmer` protocol defined in `src/argent/trimmer/base.py`: `def trim(self, content: str) -> str`
- [ ] `PythonTracebackTrimmer(max_chars: int)` — keeps final N characters (tail is most important frame)
- [ ] `MarkdownTableTrimmer(max_chars: int)` — always preserves header row; drops body rows from bottom
- [ ] `JsonArrayTrimmer(max_chars: int)` — drops elements from tail; appends tombstone `"... [N items truncated]"`
- [ ] `JsonDictTrimmer(max_chars: int)` — squashes low-priority keys; never returns empty dict
- [ ] All truncators: idempotent (return content unchanged if already within `max_chars`)
- [ ] All truncators: stdlib only, no external parser dependencies
- [ ] 90%+ test coverage

### Known Limitation — `DepthLimitValidator` and Tool Output

The `DepthLimitValidator` bracket-counting heuristic (Phase 2) over-estimates nesting depth for payloads that contain bracket characters inside string values (e.g., log lines, code snippets, template strings). Trimmed tool output passed back through ingress as a new payload may trigger false-positive depth rejections if `max_depth` is set aggressively. Operators should tune `max_depth` conservatively (≥ 20, the default) when tool output contains code or structured text. If false-positive rates prove unacceptable in practice, improve the heuristic in Phase 6.

### Implementation Steps

1. Define `Trimmer` protocol in `src/argent/trimmer/base.py`
2. Write failing tests for all four (RED)
3. Implement each class (GREEN)
4. Refactor

### Test Expectations

**Files**: `tests/unit/test_trimmer_traceback.py`, `tests/unit/test_trimmer_markdown.py`, `tests/unit/test_trimmer_json.py`

```python
def test_traceback_trimmer_keeps_tail(): ...
def test_traceback_trimmer_idempotent_on_short_content(): ...
def test_markdown_table_trimmer_preserves_header(): ...
def test_markdown_table_trimmer_drops_body_rows(): ...
def test_json_array_trimmer_appends_tombstone(): ...
def test_json_array_trimmer_valid_json_output(): ...
def test_json_dict_trimmer_retains_at_least_one_key(): ...
def test_json_dict_trimmer_valid_json_output(): ...
```

### Files to Create/Modify

- Create: `src/argent/trimmer/base.py`
- Create: `src/argent/trimmer/traceback.py`
- Create: `src/argent/trimmer/markdown.py`
- Create: `src/argent/trimmer/json_trimmer.py`
- Create: `tests/unit/test_trimmer_traceback.py`
- Create: `tests/unit/test_trimmer_markdown.py`
- Create: `tests/unit/test_trimmer_json.py`

### Commit Messages

```
test: add failing tests for format-aware output truncators
```
```
feat: implement format-aware output truncators

- PythonTracebackTrimmer: preserves tail (BR-02)
- MarkdownTableTrimmer: always preserves header row (BR-02)
- JsonArrayTrimmer: tombstone marker on truncation (BR-02)
- JsonDictTrimmer: heuristic key squashing, never empty
- Common Trimmer protocol; stdlib only
```

---

## P4-T02: Build Dynamic Budget Calculator

**Description**: Implement `ContextBudgetCalculator` which reads `RequestBudget.remaining_tokens` and the configured context window size to dynamically compute the `max_chars` allowance for the trimmer egress step.

**Status**: Not Started

### Architecture Note (Option A — chosen per P3 review)

The original spec had `compute(context: AgentContext) -> int` reading `context.token_count`. Since `budget` is no longer on `AgentContext` (ADR-0004), and `context.token_count` is an orphaned field that nothing updates, the calculator instead accepts `budget: RequestBudget` directly. This also removes the orphaned `token_count` and `call_count` fields from `AgentContext` — they were vestiges of the original "context carries everything" design.

The `AgentContext.token_count` and `AgentContext.call_count` fields are removed in this task.

### User Story

As the egress stage, I need the trimmer's `max_chars` budget to be computed dynamically from the actual remaining token budget so that large unused budgets allow larger outputs and near-exhausted budgets enforce tighter limits automatically.

### Acceptance Criteria

- [ ] `AgentContext.token_count` and `AgentContext.call_count` fields removed from `context.py` (orphaned vestiges; budget state lives in `RequestBudget`)
- [ ] All references to `context.token_count` / `context.call_count` updated or removed throughout codebase and tests
- [ ] `ContextBudgetCalculator` defined in `src/argent/trimmer/calculator.py`
- [ ] Constructor: `ContextBudgetCalculator(context_window_tokens: int, chars_per_token: float = 4.0)`
- [ ] `compute(budget: RequestBudget) -> int` returns `max_chars`
- [ ] Formula: `max_chars = int(budget.remaining_tokens * chars_per_token)`
- [ ] Minimum return value: `256` (never starve the trimmer)
- [ ] `tiktoken` is an optional extra — if installed, used for accurate token-to-char conversion instead of `chars_per_token` multiplier
- [ ] Zero hard dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Remove `token_count` and `call_count` from `AgentContext`; fix any fallout (mypy, tests)
2. Write failing tests for `ContextBudgetCalculator` (RED)
3. Implement `ContextBudgetCalculator` (GREEN)
4. Refactor

### Test Expectations

**File**: `tests/unit/test_calculator.py`

```python
def test_compute_returns_correct_budget(): ...
def test_compute_returns_minimum_256(): ...
def test_compute_reflects_remaining_tokens_from_budget(): ...
def test_calculator_uses_tiktoken_when_available(): ...
def test_compute_at_zero_remaining_tokens_returns_minimum(): ...
```

### Files to Create/Modify

- Modify: `src/argent/pipeline/context.py` (remove `token_count`, `call_count`)
- Modify: `tests/unit/test_context.py` (update assertions for removed fields)
- Create: `src/argent/trimmer/calculator.py`
- Create: `tests/unit/test_calculator.py`

### Commit Messages

```
test: add failing tests for ContextBudgetCalculator
```
```
feat: implement dynamic context budget calculator; remove orphaned context fields

- ContextBudgetCalculator.compute(budget) uses remaining_tokens * chars_per_token
- Minimum budget of 256 chars; tiktoken opt-in for accurate tokenization
- Remove AgentContext.token_count and call_count (orphaned since ADR-0004)
```

---

## Phase 4 Completion Checklist

Before moving to Phase 5, verify:

```bash
poetry run pytest tests/unit/test_trimmer_traceback.py tests/unit/test_trimmer_markdown.py \
  tests/unit/test_trimmer_json.py tests/unit/test_calculator.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```
