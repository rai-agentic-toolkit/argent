# ADR-0005 — Optional SQL Dependency (sqlglot) and Security Validator Wiring

**Status:** Accepted
**Date:** 2026-03-07
**Deciders:** Argent core team
**Epic:** P5 — Pluggable Security Policies (The Guard)

---

## Context

`SqlAstValidator` (Epic 5) must parse SQL payloads via an AST to detect
destructive DML operations (BR-03: Semantic Over Syntactic Security).  The
only Python SQL AST parser with the required depth and dialect coverage is
`sqlglot`.

However, not all Argent deployments process SQL payloads.  A chat-completion
middleware, a tool-result sanitizer, or a JSON ingress pipeline has no SQL to
validate — requiring `sqlglot` unconditionally would impose a non-trivial
dependency on deployments that derive no benefit from it.

This differs from the `defusedxml` decision (ADR-0003): XML XXE protection is
needed by every deployment that parses XML payloads, and the stdlib fallback
is actively dangerous.  There is no dangerous "stdlib fallback" for SQL parsing
— absent `sqlglot`, the validator simply cannot be instantiated, which is a
safe and explicit failure mode.

---

## Decision 1 — sqlglot as an optional extra

**Make `sqlglot>=20.0.0` an opt-in dependency declared in
`[project.optional-dependencies].sql`**, not in `[project.dependencies]`.

Production consumers that need SQL validation install `argent[sql]`.
Deployments without SQL payloads install plain `argent` and never pay the
`sqlglot` import cost.

`sqlglot` is also declared in `[project.optional-dependencies].dev` so that
CI installs it via `pip install -e ".[dev]"` and the `SqlAstValidator` tests
run against the real library on every push.

---

## Decision 2 — Fail-fast at construction, not at validation time

**`SqlAstValidator.__init__` raises `ImportError` immediately** when `sqlglot`
is not installed, rather than returning a degraded validator that silently
passes all SQL payloads at `validate()` time.

This is the principle of *explicit over implicit*: a developer who adds
`SqlAstValidator` to a `Pipeline` without installing the `sql` extra receives
an `ImportError` at startup (or test time), not a silent no-op in production.

The exception type is `ImportError` — the stdlib convention for a missing
optional dependency — not `SecurityViolationError`, which is reserved for
runtime payload-rejection signals.

---

## Decision 3 — Lazy import inside validate()

**`import sqlglot` is repeated inside `SqlAstValidator.validate()`** in
addition to the construction-time probe in `__init__`.  This is intentional:
Python's import system caches the module after the first import, so the
repeated statement is effectively free.  The pattern ensures that:

1. Mypy, linters, and static analysis tools do not require `sqlglot` stubs
   at type-checking time (the import is at function scope, behind
   `# noqa: PLC0415`).
2. The `[[tool.mypy.overrides]]` entry with `ignore_missing_imports = true`
   for `sqlglot` and `sqlglot.*` allows `mypy --strict` to pass on systems
   where `sqlglot` is absent (e.g., CI matrix legs without the `sql` extra).

---

## Decision 4 — SecurityValidator wiring in pre_execution stage

**`Pipeline.security_validators` are called at the start of the
`pre_execution` stage**, before any `pre_execution` middlewares.

Rationale:
- Ingress (stage 1) handles payload hygiene: byte limits, depth limits, and
  format parsing.  By `pre_execution`, `context.parsed_ast` is populated and
  ready for semantic inspection.
- Executing validators before `pre_execution` middlewares ensures that budget
  counters and downstream logic never see a payload that should have been
  rejected.
- A dedicated `security` stage was considered but rejected: it would add a
  fifth stage name to `_STAGE_NAMES` and complicate the telemetry contract
  for a concern that maps naturally to "before execution, after ingress."

Future validator authors must account for this stage ordering: validators
receive a context that has passed ingress checks but has not yet been modified
by any pre_execution or execution middleware.

---

## Alternatives Considered

### A — Hard runtime dependency (like defusedxml)

Rejected.  Unlike XML XXE, there is no catastrophic security failure mode when
`sqlglot` is absent — the validator simply cannot be constructed, which is an
explicit error.  Forcing all deployments to install `sqlglot` punishes
consumers that process no SQL.

### B — Silent degradation (return without blocking when sqlglot absent)

Rejected.  A validator that silently passes all payloads when its dependency
is missing is a security anti-pattern: it fails open.  The fail-fast
`ImportError` at construction time is the correct sentinel.

### C — Separate security stage (stage 5 of the pipeline)

Rejected.  Adding a fifth named stage complicates the `_STAGE_NAMES` tuple,
the telemetry contract, and the Pipeline dataclass surface for a concern that
belongs naturally at the boundary between ingress and pre_execution.

---

## Consequences

- `argent[sql]` is the install path for deployments that use `SqlAstValidator`.
- `pyproject.toml` carries a `[[tool.mypy.overrides]]` entry for `sqlglot`
  and `sqlglot.*` with `ignore_missing_imports = true`.  This entry must be
  retained as long as `sqlglot` is an optional extra.
- The `_BLOCKED_STMT_TYPES` frozenset and `_STMT_TYPE_TO_KEYWORD` dict use
  sqlglot AST class names verified against `sqlglot >= 20.0.0`.  A future
  major version of `sqlglot` that renames internal AST node classes would
  silently break the block list — this is tracked as technical debt for P6.
- **Standing guideline for future optional extras**: Any future Epic that
  introduces an optional external dependency must: (a) declare it in
  `[project.optional-dependencies]` with a named extra, (b) add it to the
  `dev` extras for CI coverage, (c) fail-fast at construction with
  `ImportError` (not a silent no-op), (d) add a `[[tool.mypy.overrides]]`
  entry if the package ships no stubs, and (e) document the decision in a
  new ADR following this template.
