# Phase 10: schema-anchor — The Guard's Second Validator

> **Goal**: Implement the fifth and final microproject — tool-schema drift detection.
> When a Python function's signature diverges from the JSON Schema registered with
> the LLM, the model sends tool calls that your code can't handle.  Schema-anchor
> catches this at startup, before any request is served.

**Status**: Not Started
**Progress**: 0/3 tasks complete

**Dependencies**: Phase 9 complete (Phase 10 is architecturally independent of P9
but depends on the public `SecurityValidator` protocol and `SecurityViolationError`
established in Phase 5)

**New Business Rule**: BR-06 — Schema Integrity: registered tool schemas must match
callable signatures at pipeline startup.

**New subpackage**: `src/argent/schema/`

---

## Task Summary

| ID | Task | Status | Dependencies |
|----|------|--------|--------------|
| P10-T01 | `SchemaInspector` — extract callable signatures | Not Started | Phase 5 complete |
| P10-T02 | `SchemaDriftDetector` — compare and classify drift | Not Started | P10-T01 complete |
| P10-T03 | `SchemaAnchorValidator` — pipeline integration + `check_schemas()` | Not Started | P10-T02 complete |

---

## P10-T01: `SchemaInspector` — Extract Callable Signatures

**Description**: Given any Python callable (function, bound method, `__call__`-based
object), extract its parameter names, required/optional status, and type annotations
into a normalized `ParameterSchema` structure that can be compared against a JSON
Schema `properties` dict.

Zero external dependencies (stdlib `inspect` only).

**Status**: Not Started

### User Story

As a library developer, I need a way to introspect any Python callable and produce
a normalized parameter description so I can compare it to the JSON Schema registered
with an LLM.

### `ParameterSchema` Dataclass

```python
@dataclass(frozen=True)
class ParameterSchema:
    name: str
    required: bool        # True when no default and not Optional-typed
    annotation: type | None   # raw annotation; None if unannotated
    has_default: bool     # True when a default value exists
```

### `SchemaInspector` Class

```python
class SchemaInspector:
    def inspect(self, fn: Callable[..., Any]) -> dict[str, ParameterSchema]:
        """Return one ParameterSchema per non-self named parameter."""
```

Behavior:
- Skips `self` and `cls` parameters
- Skips `*args` and `**kwargs` (positional/keyword catch-alls — not named params)
- `required=True` when `has_default=False` AND annotation is not `Optional[X]`
  or `X | None`
- `annotation=None` when the parameter has no type annotation

**Status**: Not Started

### Acceptance Criteria

- [ ] `SchemaInspector().inspect(fn)` returns a `dict[str, ParameterSchema]`
- [ ] Functions, bound methods, and `__call__`-bearing objects all work
- [ ] `self` and `cls` are excluded from the result
- [ ] `*args` and `**kwargs` are excluded
- [ ] `required=False` for params with defaults
- [ ] `required=False` for params annotated `Optional[X]` or `X | None`
- [ ] `required=True` for params with no default and non-Optional annotation
- [ ] `annotation=None` for unannotated params
- [ ] Empty dict for zero-parameter functions
- [ ] Zero external dependencies
- [ ] Located at `src/argent/schema/inspector.py`

### Commit Sequence

```
test: RED — failing tests for SchemaInspector (P10-T01)
feat: implement SchemaInspector; add schema/ subpackage (P10-T01)
```

---

## P10-T02: `SchemaDriftDetector` — Compare and Classify

**Description**: Compares the `dict[str, ParameterSchema]` produced by `SchemaInspector`
against the JSON Schema `properties` + `required` list registered with the LLM.
Produces a `DriftReport` classifying any mismatches by severity.

Zero external dependencies.

**Status**: Not Started

### Drift Severity Classification

| Severity | Condition | Consequence |
|----------|-----------|-------------|
| `BREAKING` | Required param in code absent from schema; param in schema absent from code as a required field; param exists in both but Python annotation and JSON Schema type are incompatible | LLM will send malformed tool calls |
| `COMPATIBLE` | Optional param in code not in schema (LLM won't know to send it); schema has extra optional params code ignores | Degrades model accuracy, not correctness |
| `WARNING` | Param exists in both but code annotation is `None` (can't verify type match) | Cannot confirm alignment |
| `None` | No differences detected | Clean — schemas match |

### `DriftReport` Dataclass

```python
@dataclass(frozen=True)
class DriftReport:
    severity: Literal["BREAKING", "COMPATIBLE", "WARNING"] | None
    drifted_params: tuple[str, ...]   # names of mismatched parameters
    details: tuple[str, ...]          # human-readable explanation per param
```

### `SchemaDriftDetector` Class

```python
class SchemaDriftDetector:
    def detect(
        self,
        code_params: dict[str, ParameterSchema],
        json_schema: dict[str, Any],   # the "parameters" dict from the LLM tool definition
    ) -> DriftReport:
        ...
```

`json_schema` is the `parameters` object from a tool definition — e.g.:
```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string"},
    "limit": {"type": "integer"}
  },
  "required": ["query"]
}
```

### Type Compatibility Rules (BREAKING detection)

A type mismatch is BREAKING when the Python annotation is unambiguously incompatible
with the JSON Schema type:

| Python annotation | JSON Schema type | Compatible? |
|-------------------|-----------------|-------------|
| `str` | `"string"` | Yes |
| `int` | `"integer"` or `"number"` | Yes |
| `float` | `"number"` | Yes |
| `bool` | `"boolean"` | Yes |
| `dict` | `"object"` | Yes |
| `list` | `"array"` | Yes |
| `str` | `"integer"` | **No — BREAKING** |
| `int` | `"string"` | **No — BREAKING** |
| Unannotated (`None`) | Any | WARNING (can't check) |
| `Any` | Any | Compatible (explicit opt-out) |

**Status**: Not Started

### Acceptance Criteria

- [ ] BREAKING detected for: required param in code missing from schema; required
  param in schema (listed in `required` array) missing from code; clear type mismatch
- [ ] COMPATIBLE detected for: optional param in code not in schema
- [ ] WARNING detected for: param in both but code annotation is `None`
- [ ] `severity=None` when code and schema match exactly
- [ ] BREAKING takes priority over COMPATIBLE in a single report (worst wins)
- [ ] COMPATIBLE takes priority over WARNING
- [ ] `drifted_params` contains the names of all affected params
- [ ] `details` contains one human-readable string per drifted param
- [ ] Located at `src/argent/schema/drift.py`
- [ ] Zero external dependencies

### Commit Sequence

```
test: RED — failing tests for SchemaDriftDetector (P10-T02)
feat: implement SchemaDriftDetector with severity classification (P10-T02)
```

---

## P10-T03: `SchemaAnchorValidator` — Pipeline Integration

**Description**: A `SecurityValidator` that accepts `(callable, json_schema)` pairs,
runs `SchemaInspector` + `SchemaDriftDetector` against each at **construction time**,
and raises `SecurityViolationError` on the first `validate()` call if any BREAKING
drift was detected.

Schema drift is a startup condition, not a per-request condition.  The validator
catches it once and refuses to serve any request until schemas are corrected.

Also ships a standalone `check_schemas()` function for CI scripts and startup checks
that don't use the full pipeline.

**Status**: Not Started

**ADR**: ADR-0008 — documents schema-anchor design, startup-vs-runtime validation
decision, and BR-06.

### User Story

As an agent developer deploying to production, I need my pipeline to refuse to serve
requests if any registered tool schema has drifted from its callable signature, so I
catch this class of bug before it reaches users.

### `SchemaAnchorValidator`

```python
@dataclass
class SchemaAnchorValidator:
    """SecurityValidator that blocks execution when tool schemas have drifted.

    Accepts a list of (callable, json_schema) pairs.  At construction, inspects
    each callable and compares it to its schema.  If any BREAKING drift is
    detected, validate() raises SecurityViolationError on every subsequent call.

    COMPATIBLE and WARNING drift are logged but do not block execution.

    Args:
        tools: List of (callable, json_schema_dict) pairs to validate.
               json_schema_dict is the "parameters" object from the tool definition.
    """
    tools: list[tuple[Callable[..., Any], dict[str, Any]]]
    _breaking_reports: list[tuple[str, DriftReport]] = field(
        default_factory=list, init=False, repr=False
    )
    # populated at __post_init__
```

`validate(context)` behavior:
- If any BREAKING reports: raise `SecurityViolationError(policy_name="SchemaAnchorValidator", reason=...)`
  where reason lists each drifted callable name and its drifted params
- If COMPATIBLE or WARNING reports only: log to `argent.security` at WARNING level, return
- If no reports: return (no-op)

### `check_schemas()` Standalone Function

```python
def check_schemas(
    tools: list[tuple[Callable[..., Any], dict[str, Any]]],
) -> list[tuple[str, DriftReport]]:
    """Return drift reports for all tools without constructing a pipeline validator.

    Useful for CI scripts, startup checks, and development tooling.
    Returns a list of (callable_name, DriftReport) for tools with any drift.
    Returns an empty list when all schemas match.
    """
```

### Exports

Add to `src/argent/__init__.py`:
- `SchemaAnchorValidator`
- `check_schemas`
- `DriftReport`
- `ParameterSchema` (useful for callers inspecting results)

### Acceptance Criteria

- [ ] `SchemaAnchorValidator` satisfies the `SecurityValidator` protocol (has `validate(context)`)
- [ ] Construction with matching schemas: `validate()` is a no-op
- [ ] Construction with BREAKING drift: `validate()` raises `SecurityViolationError`
  with `policy_name="SchemaAnchorValidator"` and reason naming the drifted params
- [ ] Construction with COMPATIBLE drift only: `validate()` returns normally;
  WARNING logged to `argent.security`
- [ ] Multiple tools: BREAKING in any one tool causes `validate()` to raise
- [ ] `check_schemas([...])` returns `list[tuple[str, DriftReport]]` for drifted tools;
  returns `[]` when all match
- [ ] `DriftReport`, `ParameterSchema`, `SchemaAnchorValidator`, `check_schemas`
  all exported from `argent.__init__`
- [ ] ADR-0008 created
- [ ] BR-06 added to BACKLOG.md business rules table
- [ ] Integration test: pipeline with `SchemaAnchorValidator` blocks a request when
  a required schema param is missing from the callable
- [ ] Zero runtime dependencies beyond stdlib (works without sqlglot installed)

### Commit Sequence

```
test: RED — failing tests for SchemaAnchorValidator and check_schemas (P10-T03)
feat: implement SchemaAnchorValidator, check_schemas; export schema API; ADR-0008 (P10-T03)
```
