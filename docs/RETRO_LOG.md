# Retrospective Log

Living ledger of review retrospective notes, appended after each completed task.

---

## Open Advisory Items

| ID | Advisory | Target Task | Source |
|----|----------|-------------|--------|
| *(no open items)* | | | |

---

## [2026-03-08] P8-T01/T04 — API Integrity (ContextBudgetCalculator + Test Hygiene)

### QA
PASS — 283 tests at 99.43% coverage. Edge cases covered: zero remaining tokens (floor fires), reserved_tokens > remaining_tokens (negative raw clamped to zero, floor fires), partially depleted budget, large token budgets, custom chars_per_token. The `test_context_window_tokens_no_longer_exists` test locks the v0.2.0 breaking change at the test layer. Advisory: construction tests assert private attrs (`_chars_per_token`, `_reserved_tokens`). Trade-off is acceptable for a pre-1.0 library; if internals change, compute() tests will still pass while construction tests break — reviewers should watch for this divergence. The `_call_count` → `remaining_calls` replacement in integration tests is semantically exact (`remaining_calls = max_calls - _call_count`).

### UI/UX
SKIP — pure library internals. No HTML, templates, form elements, interactive components, or routes modified. The `reserved_tokens` name is more actionable than the dead `context_window_tokens` for any future web UI form field or tooltip.

### DevOps
PASS — gitleaks clean (63 commits). bandit: 0 issues. No new logging or PII surface. `max(0, ...)` and floor guards prevent harmful output from pathological reserved_tokens values. Advisory: CI matrix (Python 3.11/3.12) lags local dev runtime (3.14.1) — pre-existing gap, unchanged by this diff.

### Architecture
FINDING (addressed) — `test_execution_state_lifecycle` is async in a class alongside synchronous tests. Reviewer flagged risk of silent non-execution without explicit `@pytest.mark.asyncio`. Confirmed: `asyncio_mode = "auto"` in pyproject.toml handles this correctly — targeted run shows `1 passed in 0.01s`. No code change required. Pattern established: mixed sync/async methods in a single test class are valid under `asyncio_mode = "auto"`; no per-method markers needed. Document this as the project standard so contributors do not add unnecessary decorators.

---

## [2026-03-08] P7-T01/T02/T03 — Maintenance & Observability

### QA
Phase 7 closes three advisory items (ADV-004, ADV-006, ADV-007) that required structured logging rather than new business logic. 279 tests at 99.43% coverage; all quality gates green. One FINDING fixed: `TestJsonDictTrimmerLogging` was missing a test for the single-key `break`-fallback path in `JsonDictTrimmer.trim()` (the for-loop breaks early when `len(remaining) <= 1`, then falls through to the post-loop return). `test_emits_info_log_on_single_key_fallback_path` added to exercise this path. Pattern established: when a function has multiple early-exit or loop-break paths, each path that should emit a log must have its own dedicated test — coverage alone cannot confirm the log fires on every path.

### UI/UX
SCOPE: DX/observability review (no UI surface area). Two DX FINDINGs fixed: (1) Inline `[argent.trimmer]` / `[argent.security]` prefixes in log format strings were redundant with `record.name` — removed from all five production log calls. (2) Security-block log was `_logger.info(...)` — a WARNING-filtered production deployment would silence it, making security events invisible in the operator's log stream. Changed to `_logger.warning(...)` and test assertion updated accordingly. Rule established: anything that raises `SecurityViolationError` must be preceded by at least a `logger.warning()` call, tested in the same test class as the exception assertion.

### DevOps
PASS — all security and operational checks green. gitleaks: clean (log messages contain only integer metrics and SQL keyword constants — no payload content). bandit: 0 issues. pip-audit: no new vulnerability surface. sqlglot upper bound `<30.0.0` added in both `[sql]` and `[dev]` extras with explanatory comment. P7-T03 canary tests act as install-time sentinels: if sqlglot renames `Drop`, `Delete`, `TruncateTable`, or `Alter` AST nodes in a future release, `test_blocked_stmt_type_class_names_exist_in_sqlglot_expressions` fails immediately — before any destructive SQL silently passes validation. Pattern to carry forward: any optional dependency whose internal class names are referenced by production code should have both an upper version bound and a canary test.

### Architecture
One FINDING fixed: inline logger-name prefix in format strings duplicates `record.name` — redundant and creates a maintenance burden if loggers are renamed. Removed from all production log calls. PASS on all other checklist items: dependency direction is clean (logging added within each Epic's own module), no cross-Epic imports introduced, ADR-0002/0004/0005 all respected. The single-logger-per-Epic pattern (`argent.trimmer`, `argent.security`) is now fully established across all five Epics. No ADR amendments required; this is an additive observability improvement within existing Epic boundaries.

---

## [2026-03-08] P6-T01/T02/T03 — Post-MVP Polish

### QA
Phase 6 covers three distinct concerns — a new example script, a thread pool injection field, and a depth-estimation algorithm rewrite — and the review surfaced meaningful gaps in each. Two findings fixed: (1) `test_backslash_at_end_of_payload_does_not_crash` and `test_unmatched_quote_under_counts_but_does_not_crash` added to `TestDepthLimitValidatorQuoteAwareness`, documenting the clean-exit and accepted-under-count behaviors for adversarial byte sequences; (2) `basic_agent.py` missing `NestingDepthError` catch and unguarded `response.content[0].text` access on a union-typed SDK field — both fixed with a typed `isinstance` guard. Standing rule established: any new byte-parsing algorithm must include tests for truncated inputs and malformed delimiters. Example scripts must guard all SDK union-type accesses with `isinstance` checks — copy-pasted examples propagate patterns into production code.

### UI/UX
SCOPE: SKIP — no template/route/form changes. DX review instead: two findings fixed in `basic_agent.py`: (1) `NestingDepthError` missing from ingress except clause (would produce raw Python traceback for a new developer); (2) no concrete usage illustration for the new `executor` field despite the docstring advertising it as the recommended path for concurrent deployments — added a commented `ThreadPoolExecutor` with-block in `run()`. Docstring clarified that `AsyncAnthropic` is used over the sync client for async correctness, and that production code should reuse a module-level client. Pattern to carry forward: new optional fields introduced in a library release should have at minimum a commented usage example in `basic_agent.py` or a companion example file.

### DevOps
Three findings fixed: (1) `_invoke_claude()` used the synchronous `anthropic.Anthropic` client, blocking the event loop during the HTTP round-trip — replaced with `AsyncAnthropic()` + `await`; (2) `anthropic>=0.25.0` had no upper bound; changed to `>=0.40.0,<2.0.0`; (3) `examples/` was entirely outside CI's ruff, mypy, and bandit scopes — all three extended. Also added `ERA001` to `examples/**/*` per-file-ignores (commented-out code is valid pedagogical technique in example scripts). `anthropic` added to `[dev]` extras so static analysis has access to types without requiring a live API key. Operational lesson: every new non-src/ directory containing Python must be added to CI's analysis scope at creation time, not as a follow-up.

### Architecture
Two findings fixed: (1) ADR-0004 amended with Decision 5 documenting the custom `Executor` injection pattern — lifecycle contract ("caller owns"), `ProcessPoolExecutor` pickling warning, and carry-over of the abandoned-thread caveat from Decision 2; (2) ADR-0005 Consequences updated to document the `examples` extra exemption: live API key scripts are exempt from the CI smoke-test requirement of clause (b), but static analysis (ruff, mypy, bandit) remains mandatory. Pattern established: any PR that changes behaviour described in an existing ADR Decision section must include the ADR amendment in the same branch.

---

## [2026-03-07] P5-T01/T02/T03/T04 — The Guard (Pluggable Security Policies)

### QA
The Phase 5 implementation has strong test hygiene: 245 tests at 99.18% coverage with all edge cases covered (None/empty string/non-string parsed_ast, multi-statement batch, whitespace obfuscation, sqlglot absent, ParseError, unexpected RuntimeError). Two findings fixed: (1) bare `except Exception` narrowed to `sqlglot.errors.ParseError`; outer fallback now emits a `[argent.security]` stderr diagnostic for unexpected errors — consistent with the telemetry module's established pattern; (2) a new test `test_handles_unexpected_sqlglot_error_with_stderr_diagnostic` covers the outer handler. House rule to carry forward: any security-layer except block that permits a payload through is a potential false-negative path and must emit at least a WARNING. This is now consistent across telemetry and security layers.

### UI/UX
Three DX findings fixed: (1) `SqlAstValidator.__init__` now raises `ImportError` (not `SecurityViolationError`) for missing sqlglot — correct stdlib convention for missing optional dependency; prevents startup misconfiguration from being silently caught by payload-rejection handlers; (2) error messages now use SQL keywords (`DROP`, `TRUNCATE`) via a `_STMT_TYPE_TO_KEYWORD` mapping rather than sqlglot internal class names (`Drop`, `TruncateTable`) — operators reading logs see standard SQL, not library internals; (3) `SecurityValidator` import in `__init__.py` moved to Security block with explanatory comment. Advisory: the outer except block now emits a stderr diagnostic for unexpected parse errors, which partially addresses the runtime observability gap.

### DevOps
PASS — all security and operational checks green. gitleaks: no leaks. bandit: 0 issues. pip-audit: no known vulnerabilities. No new logging surface that could leak payload content. The optional-extra dependency pattern (sqlglot in [project.optional-dependencies].sql + [project.dev]) is correctly structured. mypy overrides for sqlglot/* correct and minimal. Two advisories filed for P6: security violation events not observable without caller-side logging (ADV-006); sqlglot AST class names verified against 29.0.1 with no upper bound — silent break risk on major version bump (ADV-007).

### Architecture
Three findings fixed: (1) `security/base.py` deleted — redundant re-export that created three import paths for `SecurityValidator`; now accessible only at `from argent import SecurityValidator` with explanatory comment in `__init__.py`; (2) `SqlAstValidator.__init__` exception type corrected to `ImportError`; (3) `docs/adr/ADR-0005-optional-sql-dependency.md` created documenting the sqlglot optional-extra decision, fail-fast ImportError pattern, lazy-import + mypy override rationale, security_validators wiring in pre_execution stage, and standing guideline for future optional extras. The Protocol placement in `pipeline/pipeline.py` is confirmed correct (alongside `Middleware`) — prevents any upward Epic 1 → Epic 5 dependency per ADR-0004 Decision 4.

---

## [2026-03-07] P4-T00/T01/T02 — The Trimmer (Semantic Context Shaping)

### QA
Phase 4 continues the pattern of strong test hygiene established in earlier phases — edge cases (empty inputs, zero-budget floors, extreme budget forcing tombstones) are covered proactively without being prompted by failures. 178 tests at 99.27% coverage. Three advisory observations: (1) `pragma: no cover` on `json_trimmer.py:121` has a misleading comment — the line IS the post-break return path, not unreachable code; (2) `isinstance(x, Trimmer)` Protocol check only tested for `PythonTracebackTrimmer` — other three trimmer classes satisfy the Protocol structurally but are not explicitly runtime-tested; (3) `MarkdownTableTrimmer` normalises `\r\n` → `\n` on truncation path only, leaving idempotent path with original endings — latent inconsistency, not a bug. For Phase 5: establish a standing practice that any `pragma: no cover` annotation includes a correct mechanical justification.

### UI/UX
SKIP — pure backend library. No templates, routes, or interactive elements. Phase 4 is entirely string-transform middleware with no UI surface area.

### DevOps
Phase 4 is operationally clean: pure-Python string processing, no external I/O, no logging surface that could leak payload content, defensive early-return on all malformed input paths. `gitleaks` clean, `bandit` 0 issues, B405 nosec annotation correct. No new runtime or dev dependencies. Advisory: trimmer implementations produce no observability signal when truncation occurs; Phase 5 / future telemetry pass should emit a structured event (truncation type, chars_dropped) so operators can detect systemic budget pressure. The TYPE_CHECKING guard on the cross-epic import (ADR-0004 Decision 4) is a deliberate pattern; the cycle-audit check in ADR-0004 should be codified as a CI step as the import graph grows.

### Architecture
Phase 4 establishes a clean two-layer pattern in `trimmer/`: Protocol for composability + concrete strategy classes for format-specific logic. The TYPE_CHECKING guard for cross-epic annotation imports threads the needle between accurate type signatures and the hard dependency-direction constraint from ADR-0001; its documentation in ADR-0004 Decision 4 is exactly the right institutional response. All 12 architecture checklist items pass. One advisory: `_MIN_CHARS = 256` lacks inline rationale — a brief comment (e.g. "minimum legible error message length") would close the gap before it becomes institutional debt. Phase 5 (`security/`) will need the same TYPE_CHECKING pattern if it references `RequestBudget` or `ParsedPayload` — the pattern is now established and auditable.

---

## [2026-03-07] docs/readme-overhaul — README Overhaul

### QA
SKIP — pure documentation change (README.md only). No source code added, modified, or deleted. Coverage verified at 98.95% (131 tests). The new README makes factual claims about coverage, typing discipline, and methodology — all verifiable from the commit history and CI output. No inflated claims detected. The methodology section will need updating as the process evolves.

### UI/UX
SKIP — no template, route, or form changes. No UI surface area exists yet. The README references WCAG 2.1 AA as a future obligation, consistent with Priority 9 of the Constitution.

### DevOps
PASS — gitleaks clean (30 commits scanned, no leaks), bandit 0 issues. The README lists the security toolchain in the Running Tests section — good operational transparency. One advisory: the Installation section shows `pip install -e ".[dev]"` rather than `poetry install`; since the project uses Poetry for dependency management (per CLAUDE.md), future updates should show both options or note the canonical dev workflow.

### Architecture
SKIP — no structural changes in `src/`. The README accurately reflects the package topology from ADR-0001 and the dependency direction rule. All four ADRs are listed with correct phase attributions. Advisory filed: `.claude/agents/architecture-reviewer.md` scope gate still references the legacy resume-builder directories instead of the ARG topology (see Open Advisory Items table, ADV-002).

---

## [2026-03-07] P3-T03 — Wire ExecutionState Transitions in Pipeline.run()

### QA
Both prior FINDINGs are cleanly resolved: the assertion strengthening is meaningful and would catch real regressions, and the docstring now serves as an accurate contract that another engineer could implement against without reading the source. The state-machine coverage in TestExecutionStateTransitions is notably thorough — five tests for five distinct state outcomes in a four-state enum is good discipline. Future tests that run validators through pipeline.run() should assert COMPLETE (not PENDING) — the stale-assertion correction in test_ingress_validators.py is a useful precedent to remember.

### UI/UX
SKIP — no template, route, or form changes. This diff adds two enum assignment lines to Pipeline.run() and updates a docstring. No UI surface area exists in this project yet.

### DevOps
This task completes the ExecutionState wiring, giving the pipeline a clear, observable state machine contract — PENDING → RUNNING → COMPLETE (or RUNNING/HALTED on failure). From an operational standpoint, this is meaningful: state is now inspectable by external observers without requiring instrumentation inside the pipeline itself. The HALTED-preservation behavior is correctly not protected by a try/finally — that is a deliberate design choice, documented in the docstring, and the test suite confirms it. One pattern worth watching: as Epics 2-5 add middleware that may set HALTED directly, the documented dual-authority model (Pipeline sets RUNNING/COMPLETE, middleware sets HALTED) will need to remain consistent across all future middleware authors.

### Architecture
This diff resolves a meaningful dead-state problem: RUNNING and COMPLETE were defined in the enum but never assigned by any production code path, making the state machine decorative rather than functional. The fix is exactly the right size — two lines at the precise boundaries of the execution loop. The docstring-driven contract approach is a reasonable choice for a library of this scale, provided the docstring is kept synchronized with the implementation on every future change to run(). One ADR observation worth a future amendment: adding a note to ADR-0002 about the HALTED-on-exception convention would prevent drift as middleware authors in Phases 4-5 encounter this contract for the first time.

---

## [2026-03-07] P3-T01/T02 — RequestBudget & ToolExecutor (The Leash)

### QA
The three primary QA findings were all resolved: (1) the asymmetric token pre-check (`remaining_tokens < 0` vs `remaining_calls <= 0`) was eliminated by delegating all pre-call arithmetic to a new `RequestBudget.check_precall(token_cost)` method — the fix is at the source rather than patched in the executor; (2) both budget enforcement tests now assert `called == []` confirming the tool was never invoked on an exhausted budget; (3) `test_construction_with_limits` was strengthened to assert `max_calls` and `max_tokens` values, not just `isinstance`. Edge case coverage added: `TestEdgeCases` documents `max_calls=0` immediate raise and negative `tokens_used` accepted without validation (documented current behaviour). `TestCheckPrecall` adds 6 focused tests for the new pre-call guard method. Pattern to carry forward: when boundary conditions differ between a pre-check and a post-check, encapsulate both in the same object (here, `RequestBudget`) so the arithmetic stays consistent and is tested in isolation.

### UI/UX
SKIP — pure backend budget/execution middleware. No templates, routes, or interactive elements added. Forward-looking: `BudgetExhaustedError` and `ToolTimeoutError` exception messages are currently machine-readable. If a future UI layer surfaces them directly, they will need human-readable, actionable wording meeting WCAG 3.3.1 standards.

### DevOps
PASS — zero new dependencies; executor uses only stdlib `asyncio`. 131 tests, 98.95% branch coverage; budget subpackage and executor at 100%. Using `run_in_executor(None, ...)` (default thread pool) rather than a custom `ThreadPoolExecutor` simplifies lifecycle — no `shutdown()` call needed. One advisory: abandoned threads post-timeout continue until the tool returns naturally (asyncio/Python thread limitation); documented in ADR-0004, no action needed at this phase.

### Architecture
Five findings, all resolved: (1) **dependency-direction** — `budget: RequestBudget` removed from `AgentContext`; `ToolExecutor` now accepts `budget` as a direct constructor argument, restoring the `pipeline/` foundation invariant from ADR-0001; (2) **async-correctness** — `execute()` is now `async def`, using `asyncio.wait_for + run_in_executor`; compliant with ADR-0002's async middleware contract; (3) **abstraction-level** — `check_precall(token_cost)` added to `RequestBudget`, removing all budget arithmetic from the executor; (4) **interface-contracts** — `execute()` parameterised with `TypeVar _T` for type-safe return inference at call sites; (5) **adr-compliance** — ADR-0004 created documenting the Option A (budget off context) decision, async timeout strategy, and `check_precall` rationale. The dependency inversion was caught one commit after GREEN — exactly the window a fast architecture review should cover. Going forward: when a new Epic type appears as a field on `AgentContext`, treat it as an automatic architecture review trigger.

---

## [2026-03-06] P2-T01/T02 — Ingress Validators & SinglePassParser

### QA
The test discipline is strong: 89 tests, 98.48% coverage, all quality gates pass on the first GREEN commit. Three findings resolved: (1) the YAML except clause was broadened to `Exception` because `yaml.YAMLError` was not accessible from the outer except chain — restructured to `try/except ImportError/else` pattern so `yaml.YAMLError` is now properly scoped; (2) two boundary tests added (empty bytes for `DepthLimitValidator`, invalid UTF-8 bytes for `SinglePassParser`); (3) module docstring corrected to state telemetry fires only on final plaintext fallback. The `sys.stderr.write → logging.getLogger` migration also fixed the stderr-capture test, which was replaced with `caplog` — a more idiomatic and robust approach. Pattern to carry forward: use `caplog` fixtures for log assertions, not `sys.stderr` capture.

### UI/UX
SKIP — pure backend middleware library. No templates, routes, or interactive elements. Forward-looking concern: `PayloadTooLargeError` and `NestingDepthError` exception messages are currently machine-readable structured outputs. If any future UI layer surfaces them directly to end users, they will need human-readable, actionable wording meeting WCAG 3.3.1 standards.

### DevOps
Three findings resolved: (1) `sys.stderr.write` diagnostic calls replaced with `logging.getLogger(__name__)` — WARNING level; this closes the observability gap and prepares for PIIFilter integration when `src/argent/utils/` is scaffolded in a later phase; (2) `types-defusedxml>=0.7.0` and `types-PyYAML>=6.0` added to `[project.optional-dependencies].dev` with an explanatory comment about the cyclonedx/poetry constraint; (3) `.pre-commit-config.yaml` mypy hook already had the stubs listed. The parallel `sys.stderr.write` in `telemetry.py` (`[argent.telemetry]` diagnostic) is a pre-existing pattern from P1 — flagged as a forward-looking advisory for Phase 3 cleanup.

### Architecture
Two code findings and one documentation finding resolved: (1) `Telemetry._emit()` renamed to `emit()` — it was already the backbone dispatcher for `emit_start`/`emit_end` and had no reason to be private; the rename removes a cross-package private-method reach-across from `parser.py` and makes the public emit API explicit; (2) inline comment added at the `import defusedxml.ElementTree` line explaining why it is a hard runtime dep (security guarantee, not opt-in like pyyaml); (3) ADR-0003 created documenting the defusedxml selection, XXE/entity attack threat model, and rejected alternatives. The `ingress → pipeline` dependency direction (parser imports Telemetry) is acceptable given that `pipeline/` is the lowest-level shared foundation; no inversion required.

---

## [2026-03-04] P1-T01/T02/T03 — Core Pipeline & AgentContext

### QA
The three new modules are clean, well-typed, and the test structure is disciplined — 100% branch coverage. Two structural patterns are now established: first, the `__setattr__` immutability guard is intentionally soft (bypassed by `object.__setattr__`); this is documented as a known limitation with a test. If the pattern recurs in budget or security epics where enforcement matters more, the team should decide upfront whether to use `__slots__` or explicit documentation. Second, the "non-fatal but observable" failure mode — handler errors write a `[argent.telemetry]`-prefixed diagnostic to stderr and continue — should be the project-wide pattern for all future non-fatal side-car operations.

### UI/UX
SKIP — pure backend library. No templates, routes, or interactive elements were added. When `src/argent/templates/` first appears (API routes, resume preview), that surface carries WCAG 2.1 AA obligations and should be flagged for review.

### DevOps
The telemetry event schema makes a deliberate and correct security decision: it emits only the enum string from `execution_state` rather than any slice of `raw_payload` or `parsed_ast`. This closed-schema pattern should be documented as a project convention as ingress and security epics add richer context fields. `pip-audit` (ADV-001) has been added to dev extras and CI, `pip install --upgrade pip` is now applied uniformly across all CI jobs, and the upper bound `<3.0.0` has been added to the pip-audit pin.

### Architecture
The Middleware callable contract — async, exception-propagation, try/finally telemetry guarantee — is now captured in ADR-0002. This was the single most consequential design decision for downstream Epics. Locking it as synchronous at the foundation would have forced a breaking change at Epic 2; the cost of going async upfront is zero. The `register_handler` asymmetric replacement semantics were eliminated by splitting into `replace_handlers()` / `add_handler()` — explicit method names are a zero-cost fix that eliminates an invisible state-dependent contract.

---

## [2026-03-04] P0-T03/T04 — Directory Structure & CI Verification

### QA
This is a well-structured scaffolding commit: all tools agree the workspace is clean, coverage is 100%, and there is no dead code. The one pattern worth flagging for the team is the `assert mod is not None` idiom in `test_subpackages_importable` — it is a rubber-stamp assert that cannot fail after a successful import statement, which means it adds no safety margin over the bare import lines already at the top of the file. This is a low-risk issue at the scaffolding phase, but the pattern should not be copied into future tests where real logic is being exercised. As actual module-level symbols (classes, functions, constants) land in each subpackage, the corresponding tests should assert on those concrete names rather than on module object identity.

### UI/UX
This is a pure infrastructure scaffolding task with zero UI surface area, which is exactly what is expected at this stage. Notably, the `src/argent/templates/` and `src/argent/static/` directories do not yet exist, meaning accessibility work is entirely ahead of us. When templates are first introduced — particularly the resume output templates — that will be the highest-leverage moment for accessibility review: the document structure, heading hierarchy, color choices, and any interactive controls (upload forms, job description inputs) should be designed accessibility-first rather than retrofitted. The `ResumeBuilder/` legacy templates already present in the repository warrant a future out-of-band accessibility audit before any of their patterns are carried forward into `src/argent/templates/`.

### DevOps
The split between `[project.optional-dependencies]` and `[dependency-groups]` for dev tooling is the most operationally significant pattern in this diff. If `detect-secrets` is not reachable by the CI install command, the security job silently loses coverage without any failure signal — a gap that is easy to miss until a real secret slips through. As application logic begins landing in subsequent epics, the CI pipeline should be validated end-to-end with a dry run to confirm every security tool the pre-commit config invokes is also installed in CI. The fixture design is clean: generating the oversized payload at test time rather than committing a 2 MB file is exactly the right approach and sets a good precedent for future performance-boundary test fixtures.

### Architecture
This is a healthy Phase 0 commit: the stubs are minimal, the docstrings are precise, and the five Epic boundaries are clearly delineated. The structural concern was a documentation gap, not a code defect. The `CLAUDE.md` file was written for a resume-builder context while `pyproject.toml` and the phase backlog describe a general-purpose AI agent middleware library. These two descriptions coexisted without a reconciling document. An ADR created now, before Phase 1 implementation begins, will save significant re-contextualization cost for every future contributor and review agent. The `CLAUDE.md` File Placement Rules table has been amended to reflect the actual package topology so that it functions as a reliable navigation guide rather than a source of ambiguity.
