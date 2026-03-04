# Phase 4: Semantic Context Shaping — The Trimmer

> **Goal**: Replace `output-trimmer` and `context-diet`. Build format-aware output truncators that preserve structural integrity (BR-02), and a dynamic budget calculator that automatically sizes output to fit the remaining LLM context window.

**Status**: Not Started
**Progress**: 0/2 tasks complete

**Business Rules enforced here**: BR-02 (No Blind Truncation)

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P4-T01 | Implement Format-Aware Output Truncators | Not Started | P2 + P3 Complete |
| P4-T02 | Build Dynamic Budget Calculator | Not Started | P4-T01 |

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

- Create: `src/argent/trimmer/__init__.py`
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

**Description**: Implement `ContextBudgetCalculator` which reads `AgentContext.token_count` and the configured context window size to dynamically compute the `max_chars` budget for the trimmer egress step — replacing all hardcoded trimming thresholds.

**Status**: Not Started

### User Story

As the egress stage, I need the trimmer's `max_chars` budget to be computed dynamically from the actual remaining context window so that large unused contexts allow larger outputs and near-full contexts enforce tighter limits automatically.

### Acceptance Criteria

- [ ] `ContextBudgetCalculator` defined in `src/argent/trimmer/calculator.py`
- [ ] Constructor: `ContextBudgetCalculator(context_window_tokens: int, chars_per_token: float = 4.0)`
- [ ] `compute(context: AgentContext) -> int` returns `max_chars`
- [ ] Formula: `max_chars = (context_window_tokens - context.token_count) * chars_per_token`
- [ ] Minimum return value: `256` (never starve the trimmer)
- [ ] `tiktoken` is an optional extra — if installed, used for accurate counting instead of `chars_per_token`
- [ ] `Pipeline` egress stage wires `ContextBudgetCalculator` with selected `Trimmer`
- [ ] Zero hard dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED)
2. Implement `ContextBudgetCalculator` (GREEN)
3. Wire into `Pipeline` egress
4. Refactor

### Test Expectations

**File**: `tests/unit/test_calculator.py`

```python
def test_compute_returns_correct_budget(): ...
def test_compute_returns_minimum_256(): ...
def test_compute_reflects_token_count_from_context(): ...
def test_calculator_uses_tiktoken_when_available(): ...
def test_pipeline_egress_calls_trimmer_with_computed_budget(): ...
```

### Files to Create/Modify

- Create: `src/argent/trimmer/calculator.py`
- Modify: `src/argent/pipeline/pipeline.py` (wire calculator + trimmer into egress)
- Create: `tests/unit/test_calculator.py`

### Commit Messages

```
test: add failing tests for ContextBudgetCalculator
```
```
feat: implement dynamic context budget calculator for trimmer egress

- ContextBudgetCalculator computes max_chars from remaining context window
- Minimum budget of 256 chars; tiktoken opt-in for accurate tokenization
- Wire calculator + trimmer into Pipeline egress stage
```

---

## Phase 4 Completion Checklist

Before moving to Phase 5, verify:

```bash
poetry run pytest tests/unit/test_trimmer_traceback.py tests/unit/test_trimmer_markdown.py tests/unit/test_trimmer_json.py tests/unit/test_calculator.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```
