# Retrospective Log

Living ledger of review retrospective notes, appended after each completed task.

---

## Open Advisory Items

| ID | Advisory | Target Task | Source |
|----|----------|-------------|--------|
| — | *(no open items)* | — | — |

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
