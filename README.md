# Argent — Agentic Runtime Gateway

**Status**: Work in progress. Phases 0–2 complete, Phase 3 in progress, Phases 4–6 not started.
**Coverage**: 98.95% branch · **Type checking**: mypy strict · **Python**: ≥ 3.11

---

## What This Is

Argent (ARG) is a deterministic, middleware-driven execution wrapper for AI agents. It sits between an untrusted LLM agent and the tools/data it wants to touch, enforcing payload hygiene, execution budgets, and output compression through a four-stage async pipeline.

It is a **library**, not a framework. You wire it into your agent loop. It does not manage your LLM calls, prompt templates, or orchestration.

## What This Is Not

- Not a LangChain alternative. No prompt abstractions, no chains, no agent executors.
- Not production-ready. The core pipeline and two of five epics are implemented. The remaining three (output trimming, security policies, end-to-end integration) are specified but unbuilt.
- Not a hosted service. It's a Python package you install and configure.

## What Works Today

| Component | Epic | Status | What It Does |
|-----------|------|--------|--------------|
| `pipeline/` | Core | ✅ Complete | `AgentContext` state machine, four-stage async middleware chain (`ingress → pre_execution → execution → egress`), structured telemetry with try/finally guarantees |
| `ingress/` | The Shield | ✅ Complete | Pre-allocation byte-size and nesting-depth validators, single-pass format detection (JSON/YAML/XML/plaintext), `defusedxml` for XXE protection |
| `budget/` | The Leash | 🔧 In Progress | Stateful call and token counters with hard limits (BR-01), async tool executor with timeout enforcement and recursion traps. ExecutionState wiring is the remaining task. |
| `trimmer/` | The Trimmer | ⬚ Not Started | Format-aware output truncation (Markdown tables, Python tracebacks, JSON structures) |
| `security/` | The Guard | ⬚ Not Started | Pluggable security validators, SQL AST analysis via optional `sqlglot` |

## Architecture

```
src/argent/
├── pipeline/    → Foundation: AgentContext + middleware chain (zero external deps)
├── ingress/     → Payload hygiene: validators + single-pass parser (defusedxml)
├── budget/      → Execution limits: counters + async tool wrapper (stdlib only)
├── trimmer/     → Output shaping (not yet implemented)
└── security/    → Security policies (not yet implemented)
```

Dependency direction is strictly enforced: epic packages depend on `pipeline/`, never the reverse. This is documented in [ADR-0001](docs/adr/ADR-0001-package-topology.md) and was actively corrected when a violation was introduced in Phase 3 (see [ADR-0004](docs/adr/ADR-0004-budget-context-coupling.md)).

The pipeline is async-first ([ADR-0002](docs/adr/ADR-0002-middleware-contract.md)). All middleware is `async def`. Synchronous tools are wrapped via `asyncio.run_in_executor`. This was a deliberate upfront decision — going sync at the foundation would have forced a breaking change at Epic 2.

### Business Rules

These are the inviolable constraints. If the framework violates any of them, it's a bug:

| ID | Rule | Enforced By |
|----|------|-------------|
| BR-01 | Absolute budget enforcement — halt on `max_calls` or `max_tokens` | `budget/` |
| BR-02 | No blind truncation — preserve structural integrity when compressing | `trimmer/` (not yet) |
| BR-03 | Semantic over syntactic security — no naive substring blocking | `security/` (not yet) |
| BR-04 | Pre-allocation limits — reject oversized inputs before parsing | `ingress/` |

## Installation

Not published to PyPI. Clone and install in development mode:

```bash
git clone https://github.com/rai-agentic-toolkit/argent.git
cd argent
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest --cov=src/argent --cov-fail-under=90 -v
```

All quality gates (run via pre-commit):

```bash
pre-commit run --all-files
```

This runs ruff (lint + format), mypy (strict), bandit, detect-secrets, gitleaks, vulture, and commitizen.

---

## The Methodology: AI-Driven Development Under Governance

This section exists because the methodology is as much the point as the code. Argent is being built almost entirely by an LLM coding agent (Claude) operating under a structured governance framework. The framework is designed to answer a specific question: **can you get reliable, secure, well-tested code from an autonomous AI agent if you give it sufficiently rigorous constraints?**

The early evidence says yes, with caveats.

### How It Works

The developer (a human) defines requirements, reviews pull requests, and merges to main. Everything between "here's the next task" and "here's a PR for review" is executed by the AI agent, operating under three governance documents:

1. **[CONSTITUTION.md](CONSTITUTION.md)** — A priority-ordered rule hierarchy (Priority 0: Security, Priority 1: Quality Gates, Priority 3: TDD, etc.). When rules conflict, the lower-numbered priority wins. The agent cannot bypass quality gates, skip tests, or commit secrets. These aren't suggestions — the agent is instructed to halt and report a blocker rather than violate any rule.

2. **[AUTONOMOUS_DEVELOPMENT_PROMPT.md](AUTONOMOUS_DEVELOPMENT_PROMPT.md)** — The operational workflow. Defines exactly how the agent discovers tasks, plans work, writes failing tests first, implements, runs quality gates, spawns parallel review subagents, creates PRs, and updates retrospective logs. Versioned (currently 1.4.0) and amended when the process itself has a gap.

3. **[CLAUDE.md](CLAUDE.md)** — Project-specific operational directives: file placement rules, naming conventions, PII protection procedures, emergency procedures for accidentally staged secrets.

### The TDD Loop

Every feature follows RED → GREEN → REVIEW, committed separately:

```
test: add failing tests for [feature] (RED)     ← tests import symbols that don't exist yet
feat: implement [feature] (GREEN)                ← minimal code to pass
review(qa): [task] — PASS/FINDING                ← QA subagent review
review(ui-ux): [task] — SKIP                     ← UI/UX subagent (skips on backend work)
review(devops): [task] — PASS/FINDING            ← DevOps subagent review
review(arch): [task] — PASS/FINDING              ← Architecture subagent review
docs: update RETRO_LOG for [task]                ← retrospective entry
```

You can verify the TDD discipline by diffing any RED commit — the test files import classes that won't exist until the GREEN commit. This isn't aspirational; it's the actual commit history.

### The Review Subagents

After the GREEN phase, four specialized review subagents are spawned in parallel, each with a defined checklist:

- **QA** — Dead code, exception specificity, edge cases, meaningful assertions, docstring accuracy, type annotation correctness
- **UI/UX** — WCAG 2.1 AA compliance (skipped on pure backend work, which is everything so far)
- **DevOps** — Hardcoded credentials, PII in logs, blocking async calls, dependency audit, CI health
- **Architecture** — File placement, dependency direction, async correctness, ADR compliance

Each subagent produces a structured finding (PASS / FINDING / SKIP per checklist item) and a Retrospective Note. Findings are fixed before merge; retrospective notes are appended to [docs/RETRO_LOG.md](docs/RETRO_LOG.md).

### What the Retro Log Actually Contains

Not boilerplate. Specific, actionable observations from each phase. Examples:

- P3 Architecture review caught that `RequestBudget` was added as a field on `AgentContext`, creating an upward dependency from `pipeline/` → `budget/`. Fixed in the same PR cycle, documented in [ADR-0004](docs/adr/ADR-0004-budget-context-coupling.md).
- P2 QA review identified that `yaml.YAMLError` was inaccessible from an outer except chain due to scoping. Restructured to `try/except ImportError/else` pattern.
- P1 DevOps review noted the telemetry event schema deliberately emits only enum strings, never raw payload slices — a security-by-design pattern.

### The Honest Caveats

**The context overhead is real.** The Constitution + autonomous prompt + CLAUDE.md total over 1,200 lines of instructions. That's a significant chunk of the agent's context window consumed by process governance before any code is written. The tradeoff is intentional — the developer is trading context budget for output reliability — but it's a nontrivial cost.

**The velocity is modest.** 45 commits across 3 days produced ~836 lines of production code. A significant portion of the commit history is review evidence and documentation. If you measure productivity by lines shipped per day, this process is slow. If you measure it by defect rate and architectural coherence, it's competitive.

**The review subagents are simulated reviewers, not independent humans.** They're the same LLM with different system prompts. The findings are real (they've caught actual bugs and design violations), but the independence has limits. The developer is aware of this — the process includes a loop-prevention mechanism that escalates to a human after 3 consecutive review cycles on the same issue.

---

## Architecture Decision Records

| ADR | Decision | Phase |
|-----|----------|-------|
| [ADR-0001](docs/adr/ADR-0001-package-topology.md) | Epic-per-subpackage layout, no flat `models/` directory | P0 |
| [ADR-0002](docs/adr/ADR-0002-middleware-contract.md) | Async middleware contract for all pipeline stages | P1 |
| [ADR-0003](docs/adr/ADR-0003-xml-security-dep.md) | `defusedxml` as hard runtime dependency (XXE protection) | P2 |
| [ADR-0004](docs/adr/ADR-0004-budget-context-coupling.md) | Budget kept off AgentContext; async executor strategy | P3 |

## Project Tracking

- [BACKLOG.md](BACKLOG.md) — Master phase tracker with dependency graph
- [docs/backlog/](docs/backlog/) — Detailed per-phase task specifications
- [docs/RETRO_LOG.md](docs/RETRO_LOG.md) — Living retrospective log

## License

MIT
