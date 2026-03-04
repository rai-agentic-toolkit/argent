# Retrospective Log

Living ledger of review retrospective notes, appended after each completed task.

---

## Open Advisory Items

| ID | Advisory | Target Task | Source |
|----|----------|-------------|--------|
| ADV-001 | Add `pip-audit` to dev extras and CI `security` job to enable automated dependency vulnerability scanning before application logic lands | P1-T01 (first Epic 1 task) | DevOps review, P0-T03/T04 |

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
