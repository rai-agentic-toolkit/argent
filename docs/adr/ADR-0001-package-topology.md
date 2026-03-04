# ADR-0001: Package Topology for Argent (ARG Middleware)

**Status**: Accepted
**Date**: 2026-03-04
**Deciders**: Project team
**Triggered by**: Architecture review of P0-T03/T04 (Phase 0 scaffold)

---

## Context

`argent` is the **Agentic Runtime Gateway (ARG)** — a deterministic,
middleware-driven execution wrapper for AI agents. It is a general-purpose
library, not a domain application.

The `CLAUDE.md` file was partially inherited from a prior resume-builder project
and contains a File Placement Rules table listing `models/`, `parsers/`,
`generators/`, `agents/`, `agents/tools/`, `api/`, `utils/`, `templates/`, and
`static/` as canonical subpackage directories. Those directories describe the
**domain agent layer that consumes ARG**, not the ARG framework itself.

At Phase 0 scaffolding, the five Epic subpackages were committed as the
authoritative package map. This ADR records that decision.

---

## Decision

The canonical top-level subpackage layout for `src/argent/` is:

| Subpackage | Epic | Responsibility |
|---|---|---|
| `pipeline/` | Epic 1 | `AgentContext` state machine and middleware chain |
| `ingress/` | Epic 2 | Payload hygiene and single-pass parsing (The Shield) |
| `budget/` | Epic 3 | Token/call counters and execution isolation (The Leash) |
| `trimmer/` | Epic 4 | Format-aware output truncation and context shaping (The Trimmer) |
| `security/` | Epic 5 | Pluggable security policies and semantic validation (The Guard) |

Sub-modules within each Epic subpackage follow the standard `snake_case.py`
naming convention from `CLAUDE.md`. Example: `pipeline/context.py`,
`ingress/parser.py`, `budget/counter.py`.

### What This Means for CLAUDE.md File Placement Rules

The directories listed in `CLAUDE.md` (`models/`, `parsers/`, `agents/`, etc.)
**do not apply to this repository**. They describe the resume-builder domain
layer. The `CLAUDE.md` Architecture section has been amended (see below) to
reflect the ARG topology.

If ARG eventually needs internal domain models (e.g., a Pydantic model for
`AgentContext`), those live **inside the relevant Epic subpackage**:
- `pipeline/context.py` — not a top-level `models/` directory.
- `ingress/schema.py` — not a top-level `models/` directory.

A top-level `models/` directory should **not** be created unless multiple Epic
subpackages share models that cannot be owned by any single Epic.

---

## Consequences

- Future contributors must use the five Epic subpackages as the navigation map,
  not the directory table in CLAUDE.md's File Placement Rules section.
- The CLAUDE.md File Placement Rules table is amended to list the ARG topology.
- Any new cross-cutting concern (logging utilities, shared exceptions) goes in a
  top-level `utils/` or `exceptions/` subpackage, created only when a second
  consumer exists. One-off utilities live inside their Epic subpackage.

---

## Alternatives Considered

**Keep CLAUDE.md directory table and create those directories**: Rejected.
Creating `models/`, `agents/`, `parsers/` etc. would impose a resume-builder
architecture on a middleware library. The Epic boundary (pipeline/ingress/budget/
trimmer/security) is a better fit for ARG's layered middleware design.

**Single flat `src/argent/` with no subpackages**: Rejected. Five distinct
Epics with different concerns benefit from namespace isolation. Import paths like
`argent.ingress.parser` are self-documenting.
