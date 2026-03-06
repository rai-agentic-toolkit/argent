# ADR-0003 — XML Security Dependency (defusedxml)

**Status:** Accepted
**Date:** 2026-03-06
**Deciders:** Argent core team
**Epic:** P2 — Ingress Hygiene (The Shield)

---

## Context

`src/argent/ingress/parser.py` (`SinglePassParser`) must parse XML payloads as
part of its multi-format detection chain.  Python's stdlib
`xml.etree.ElementTree` is known to be vulnerable to several XML-based attacks:

| Attack | Description |
|--------|-------------|
| **XXE (XML External Entity)** | Attacker injects `<!ENTITY>` declarations referencing external URLs or local file paths; the parser fetches or reads them. |
| **Billion Laughs / XML Bomb** | Deeply nested entity references that expand exponentially, exhausting memory. |
| **DTD Retrieval** | Parser fetches remote DTDs, enabling SSRF. |

Argent processes payloads from untrusted sources — this is the explicit design
goal of The Shield (Epic 2).  Using the stdlib XML parser would silently re-
introduce exactly the class of vulnerabilities The Shield exists to prevent.

---

## Decision

**Use `defusedxml>=0.7.0` as a hard runtime dependency for XML parsing.**

`defusedxml` is a well-established Python library that wraps `xml.etree` and
disables all known dangerous XML processing features (external entity
resolution, DTD fetching, entity expansion attacks).  Its return type
(`xml.etree.ElementTree.Element`) is identical to the stdlib parser, so all
downstream consumers of `context.parsed_ast` are unaffected.

`defusedxml` is treated as a **hard runtime dependency** (declared in
`pyproject.toml [project].dependencies`), not an opt-in like `pyyaml`:

- XML security is non-negotiable for a payload hygiene layer.
- Every deployment of Argent that parses XML *must* have the protection.
- Making it optional would create a silent degradation path where a missing
  package causes the code to fall back to the insecure stdlib parser.

---

## Alternatives Considered

### A — Use stdlib `xml.etree.ElementTree` with `#nosec`

Rejected.  Suppressing bandit B405/B314 with `#nosec` would silence a valid
security finding without fixing the underlying vulnerability.  CLAUDE.md
mandates "Security by default: PII protection is not optional, it's
foundational."

### B — Make defusedxml opt-in (like pyyaml)

Rejected.  If `defusedxml` is absent, the parser would need to either skip XML
entirely (breaking XML ingress) or fall back to the stdlib parser (introducing
the vulnerabilities listed above).  Neither outcome is acceptable.

### C — Use `defusedxml.defuse_stdlib()` globally

Rejected for now.  Calling `defuse_stdlib()` patches the stdlib XML modules
globally for the entire process, which may conflict with third-party libraries
that depend on specific stdlib XML behavior.  The scoped import
`import defusedxml.ElementTree as ET` is more precise.

---

## Consequences

- `defusedxml>=0.7.0` is a mandatory runtime dep.  Deployments without it will
  fail at import time for `argent.ingress.parser`.
- `types-defusedxml>=0.7.0` is declared in dev extras for mypy strict-mode
  compatibility.  (`poetry add` fails due to a `cyclonedx-python-lib`
  Python `<4.0` constraint; stubs are declared directly in
  `[project.optional-dependencies]`.)
- The `.pre-commit-config.yaml` mypy hook lists `defusedxml` and its stubs
  under `additional_dependencies` so the isolated hook environment has the same
  coverage as local runs and CI.
- Future Epics that need XML parsing (e.g. output trimmer for XML responses)
  **must** use `defusedxml`, not `xml.etree.ElementTree`.  This ADR serves as
  the standing guideline.
