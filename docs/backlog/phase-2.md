# Phase 2: Ingress Hygiene — The Shield

> **Goal**: Replace `secure-ingest`. Build the first checkpoint in the pipeline — a fast, zero-allocation pre-parser layer that rejects dangerous payloads before they consume memory.

**Status**: Not Started
**Progress**: 0/2 tasks complete

**Business Rules enforced here**: BR-04 (Pre-Allocation Limits), NFR Zero-Copy/Single-Pass Parsing

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P2-T01 | Implement Byte-Size & Depth-Limit Validators | Not Started | P1 Complete |
| P2-T02 | Build Unified Single-Pass Parser | Not Started | P2-T01 |

---

## P2-T01: Implement Byte-Size & Depth-Limit Validators

**Description**: Implement two lightweight validators that run at the very beginning of the ingress stage — long before any JSON/YAML parser is invoked. The byte-size validator enforces a configurable max-payload size. The depth-limit validator enforces a maximum nesting depth on raw text before structural parsing. Both implement the `Callable[[AgentContext], None]` middleware protocol.

**Status**: Not Started

### User Story

As a pipeline operator, I need payload size and depth to be checked before the parser is called so that a maliciously crafted 50MB JSON payload cannot cause an OOM crash or CPU burn during structural parsing.

### Acceptance Criteria

- [ ] `ByteSizeValidator` defined in `src/argent/ingress/validators.py`
- [ ] `ByteSizeValidator` is configurable: `ByteSizeValidator(max_bytes: int = 1_048_576)` (default 1MB)
- [ ] On violation: sets `context.execution_state = ExecutionState.HALTED` and raises `PayloadTooLargeError`
- [ ] `DepthLimitValidator` defined in `src/argent/ingress/validators.py`
- [ ] `DepthLimitValidator` estimates nesting depth via character counting (no parsing) — fast heuristic
- [ ] `DepthLimitValidator` is configurable: `DepthLimitValidator(max_depth: int = 20)`
- [ ] On violation: sets `context.execution_state = ExecutionState.HALTED` and raises `NestingDepthError`
- [ ] Both validators implement `Callable[[AgentContext], None]` (plug directly into `Pipeline` ingress stage)
- [ ] `PayloadTooLargeError` and `NestingDepthError` are custom exceptions in `src/argent/ingress/exceptions.py`
- [ ] Zero external dependencies
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED):
   - Test normal payload passes both validators without mutation
   - Test oversized payload raises `PayloadTooLargeError`
   - Test deeply nested payload raises `NestingDepthError`
   - Test context state is HALTED on violation
2. Implement `src/argent/ingress/validators.py` and `src/argent/ingress/exceptions.py` (GREEN)
3. Refactor if needed

### Test Expectations

**File**: `tests/unit/test_ingress_validators.py`

```python
def test_byte_size_validator_passes_small_payload():
    """A payload within limit passes without error."""

def test_byte_size_validator_raises_on_oversized_payload():
    """A payload exceeding max_bytes raises PayloadTooLargeError."""

def test_byte_size_validator_halts_context():
    """Context execution_state is HALTED when PayloadTooLargeError is raised."""

def test_depth_limit_validator_passes_shallow_payload():
    """A payload within nesting depth passes without error."""

def test_depth_limit_validator_raises_on_deep_payload():
    """A 21-level deep JSON string raises NestingDepthError."""

def test_validators_are_configurable():
    """ByteSizeValidator(max_bytes=100) rejects a 101-byte payload."""
```

### Files to Create/Modify

- Create: `src/argent/ingress/__init__.py`
- Create: `src/argent/ingress/validators.py`
- Create: `src/argent/ingress/exceptions.py`
- Create: `tests/unit/test_ingress_validators.py`

### Commit Messages

```
test: add failing tests for byte-size and depth-limit validators
```
```
feat: implement ingress byte-size and depth-limit validators

- Define ByteSizeValidator (configurable max_bytes, default 1MB)
- Define DepthLimitValidator (fast heuristic, configurable max_depth)
- Custom exceptions: PayloadTooLargeError, NestingDepthError
- Validators set context state to HALTED on violation (BR-04)
- Zero external dependencies
```

---

## P2-T02: Build Unified Single-Pass Parser

**Description**: Implement a single-pass structural parser middleware that detects the content format (JSON, YAML, XML, or plaintext) and parses it exactly once, attaching the resulting Python object to `context.parsed_ast`. Downstream middlewares may read `parsed_ast` without re-parsing.

**Status**: Not Started

### User Story

As a pipeline, I need to parse a raw payload exactly once and make the result available to all downstream stages so that we never duplicate AST parsing work (NFR: Zero-Copy / Single-Pass Parsing).

### Acceptance Criteria

- [ ] `SinglePassParser` defined in `src/argent/ingress/parser.py`
- [ ] Detects format automatically: JSON → `json.loads`, YAML → `yaml.safe_load` (opt-in extra), XML → `xml.etree.ElementTree`, plaintext → `str`
- [ ] Attaches the parsed object to `context.parsed_ast`
- [ ] If `parsed_ast` is already set, **skips parsing** (idempotent — respects single-pass NFR)
- [ ] If parsing fails (malformed content), falls back to storing `raw_payload.decode("utf-8", errors="replace")` as `parsed_ast` and emits a telemetry warning event (NFR: Graceful Degradation — **never crash the host event loop**)
- [ ] YAML is only attempted if `pyyaml` is installed; if not, skips YAML detection cleanly
- [ ] Zero hard dependencies beyond stdlib; `pyyaml` is opt-in
- [ ] 90%+ test coverage

### Implementation Steps

1. Write failing tests (RED)
2. Implement `SinglePassParser` (GREEN)
3. Refactor; verify idempotency and graceful fallback paths

### Test Expectations

**File**: `tests/unit/test_ingress_parser.py`

```python
def test_parser_detects_and_parses_json():
    """Valid JSON payload produces a dict in context.parsed_ast."""

def test_parser_detects_and_parses_xml():
    """Valid XML payload produces an ElementTree object in context.parsed_ast."""

def test_parser_falls_back_to_plaintext():
    """Plaintext payload is stored as str in context.parsed_ast."""

def test_parser_gracefully_handles_malformed_json():
    """Malformed JSON does not raise; falls back to raw string."""

def test_parser_is_idempotent():
    """If parsed_ast is already set, parser does not re-parse."""

def test_parser_emits_telemetry_on_fallback():
    """A parsing failure emits a structured warning event via telemetry."""
```

### Files to Create/Modify

- Create: `src/argent/ingress/parser.py`
- Create: `tests/unit/test_ingress_parser.py`

### Commit Messages

```
test: add failing tests for unified single-pass parser
```
```
feat: implement unified single-pass parser middleware

- Auto-detect content format: JSON, YAML (opt-in), XML, plaintext
- Attach parsed object to context.parsed_ast exactly once (idempotent)
- Graceful fallback to raw string on malformed content; telemetry warning emitted
- pyyaml is optional — skipped cleanly if not installed
- Zero hard dependencies beyond stdlib
```

---

## Phase 2 Completion Checklist

Before moving to Phase 3, verify:

```bash
poetry run pytest tests/unit/test_ingress_validators.py tests/unit/test_ingress_parser.py -v
poetry run pytest --cov=src/argent --cov-fail-under=90
poetry run mypy src/
poetry run ruff check src/ tests/
poetry run pre-commit run --all-files
```

> Phase 3 (Budgeting & The Leash) may begin in parallel with Phase 2 once Phase 1 is complete.
