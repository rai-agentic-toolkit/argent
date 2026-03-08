# Argent — Agentic Runtime Gateway

**Coverage**: 99.41% · **Type checking**: mypy strict · **Python**: ≥ 3.11 · **Status**: All 6 delivery phases complete

---

## What This Is

Argent (ARG) is a deterministic, middleware-driven execution wrapper for AI agents. It sits between your LLM and the tools it wants to call, enforcing payload hygiene, execution budgets, format-aware output trimming, and pluggable security policies through a four-stage async pipeline.

It is a **library, not a framework**. You wire it into your agent loop. It does not manage your LLM calls, prompt templates, or orchestration. Zero vendor lock-in — works with any model provider.

## What This Is Not

- Not a LangChain alternative — no prompt abstractions, no chains, no agent executors.
- Not a hosted service — it's a Python package you install and configure.
- Not opinionated about your LLM — the `examples/` directory uses the Anthropic SDK; the library itself has no LLM dependency.

---

## Quick Start

```bash
git clone https://github.com/rai-agentic-toolkit/argent.git
cd argent
pip install -e ".[dev]"
```

Run the end-to-end example (requires `ANTHROPIC_API_KEY`):

```bash
pip install -e ".[examples]"
export ANTHROPIC_API_KEY=sk-ant-...
python examples/basic_agent.py
```

---

## What's Shipped

Every planned component is implemented, tested at ≥99% coverage, and documented with an ADR.

| Component | Epic | What It Does |
|-----------|------|--------------|
| `pipeline/` | Core | `AgentContext` state machine, four-stage async middleware chain (`ingress → pre_execution → execution → egress`), structured telemetry with try/finally guarantees, `SecurityValidator` protocol |
| `ingress/` | The Shield | Pre-allocation byte-size and nesting-depth validators (quote-aware bracket counting), single-pass format detection (JSON / YAML / XML / plaintext), `defusedxml` for XXE protection |
| `budget/` | The Leash | Stateful call and token counters with hard limits (BR-01), async `ToolExecutor` with timeout and recursion protection, optional custom thread pool injection for concurrent deployments |
| `trimmer/` | The Trimmer | Format-aware truncators for JSON arrays, JSON dicts, Markdown tables, and Python tracebacks; `ContextBudgetCalculator` for dynamic token-to-char allocation (BR-02) |
| `security/` | The Guard | `SecurityValidator` protocol, SQL AST validator via optional `sqlglot` extra blocking DROP / DELETE / TRUNCATE / ALTER (BR-03) |

---

## Architecture

```
src/argent/
├── pipeline/    → Foundation: AgentContext + async middleware chain (zero external deps)
├── ingress/     → Payload hygiene: validators + single-pass parser (defusedxml hard dep)
├── budget/      → Execution limits: counters + async tool wrapper (stdlib only)
├── trimmer/     → Output shaping: format-aware truncators + dynamic budget calculator
└── security/    → Security policies: SecurityValidator protocol + SQL AST validator
```

**Dependency direction** is strictly enforced per [ADR-0001](docs/adr/ADR-0001-package-topology.md): epic packages depend on `pipeline/`, never the reverse. Higher-numbered epics may reference lower-numbered ones via `TYPE_CHECKING` annotation guards; lateral cross-epic imports are forbidden.

**Async-first** per [ADR-0002](docs/adr/ADR-0002-middleware-contract.md): all middleware is `async def`. Synchronous tools are offloaded via `asyncio.run_in_executor`. This was a deliberate upfront decision — going sync at the foundation would have forced a breaking change at Epic 2.

### Business Rules

These are the inviolable constraints. A violation is a bug:

| ID | Rule | Enforced By |
|----|------|-------------|
| BR-01 | Absolute budget enforcement — halt on `max_calls` or `max_tokens` | `budget/` |
| BR-02 | No blind truncation — preserve structural integrity when compressing | `trimmer/` |
| BR-03 | Semantic over syntactic security — no naive substring blocking | `security/` |
| BR-04 | Pre-allocation limits — reject oversized inputs before parsing | `ingress/` |

---

## Usage

### Minimal wiring

```python
import asyncio
from argent import (
    AgentContext,
    ByteSizeValidator,
    DepthLimitValidator,
    Pipeline,
    RequestBudget,
    SinglePassParser,
    ToolExecutor,
)

async def run(raw_bytes: bytes) -> None:
    # 1. Build ingress pipeline
    pipeline = Pipeline(
        ingress=[
            ByteSizeValidator(max_bytes=1024 * 1024),  # 1 MiB cap
            DepthLimitValidator(max_depth=20),           # no zip-bomb ASTs
            SinglePassParser(),                          # JSON/YAML/XML/text
        ]
    )

    # 2. Run ingress
    ctx = AgentContext(raw_payload=raw_bytes)
    await pipeline.run(ctx)                              # raises on violation

    # 3. Execute tools under budget
    budget = RequestBudget(max_calls=10, max_tokens=5_000)
    executor = ToolExecutor(budget=budget)
    result = await executor.execute(your_tool_fn, token_cost=50)

asyncio.run(run(b'{"action": "search", "query": "argent"}'))
```

### With security validation

```python
from argent import Pipeline, SqlAstValidator  # pip install argent[sql]

pipeline = Pipeline(
    ingress=[ByteSizeValidator(), DepthLimitValidator(), SinglePassParser()],
    security_validators=[SqlAstValidator()],   # blocks DROP/DELETE/TRUNCATE/ALTER
)
```

### With output trimming

```python
import json
from argent import JsonDictTrimmer, ContextBudgetCalculator, RequestBudget

budget = RequestBudget(max_calls=10, max_tokens=4_000)
calc = ContextBudgetCalculator(reserved_tokens=500)
char_budget = calc.compute(budget)

trimmer = JsonDictTrimmer(max_chars=char_budget)
safe_output = trimmer.trim(json.dumps(llm_response))
```

### Thread pool isolation (concurrent agents)

```python
import concurrent.futures
from argent import ToolExecutor, RequestBudget

budget = RequestBudget(max_calls=20, max_tokens=10_000)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    executor = ToolExecutor(budget=budget, executor=pool)
    result = await executor.execute(my_tool, token_cost=100)
```

---

## Installation

Not on PyPI. Install from source:

```bash
# Core library
pip install -e "."

# Development (tests, linters, type stubs)
pip install -e ".[dev]"

# SQL AST validation
pip install -e ".[sql]"

# End-to-end example (requires ANTHROPIC_API_KEY)
pip install -e ".[examples]"
```

---

## Running Tests

```bash
# Tests + coverage gate (≥90%)
poetry run pytest --cov=src/argent --cov-fail-under=90 -v

# All quality gates
poetry run pre-commit run --all-files
```

The pre-commit suite runs: ruff (lint + format), mypy (strict), bandit, detect-secrets, gitleaks, vulture, and commitizen — across `src/`, `tests/`, and `examples/`.

---

## Architecture Decision Records

| ADR | Decision | Phase |
|-----|----------|-------|
| [ADR-0001](docs/adr/ADR-0001-package-topology.md) | Epic-per-subpackage layout; no flat `models/` directory | P0 |
| [ADR-0002](docs/adr/ADR-0002-middleware-contract.md) | Async middleware contract; exception propagation; telemetry guarantee | P1 |
| [ADR-0003](docs/adr/ADR-0003-xml-security-dep.md) | `defusedxml` as hard runtime dependency (XXE protection) | P2 |
| [ADR-0004](docs/adr/ADR-0004-budget-context-coupling.md) | Budget off AgentContext; async executor; custom thread pool injection | P3/P6 |
| [ADR-0005](docs/adr/ADR-0005-optional-sql-dependency.md) | sqlglot as optional extra; fail-fast ImportError; examples extra exemption | P5/P6 |

---

## The Methodology

This section exists because the methodology is as much the point as the code. Argent is built almost entirely by an LLM coding agent (Claude) operating under a structured governance framework designed to answer one question: **can you get reliable, secure, well-tested code from an autonomous AI agent if you give it sufficiently rigorous constraints?**

After 7 phases and ~260 tests at 99%+ coverage, the early evidence says yes — with the caveats documented honestly below.

### Governance Documents

The developer defines requirements, reviews PRs, and merges to main. Everything between "here's the next task" and "here's a PR for review" is the AI agent:

1. **[CONSTITUTION.md](CONSTITUTION.md)** — Priority-ordered rule hierarchy. Priority 0: Security. Priority 1: Quality gates. Priority 3: TDD. When rules conflict, lower number wins. The agent halts and reports a blocker rather than violate any rule.

2. **[AUTONOMOUS_DEVELOPMENT_PROMPT.md](AUTONOMOUS_DEVELOPMENT_PROMPT.md)** — Exact operational workflow: task discovery, failing-tests-first, quality gates, parallel review subagents, PR creation, retrospective logging.

3. **[CLAUDE.md](CLAUDE.md)** — Project-specific directives: file placement, naming conventions, PII protection, emergency procedures for accidentally staged secrets.

### The TDD Loop

Every feature follows RED → GREEN → REVIEW, committed separately:

```
test: add failing tests for [feature]         ← tests import symbols that don't exist yet
feat: implement [feature]                     ← minimal code to pass, all gates green
fix: address review findings                  ← findings fixed before merge
review(qa): [task] — PASS/FINDING            ← QA subagent structured checklist
review(ui-ux): [task] — SKIP                 ← UI/UX subagent (skips backend-only work)
review(devops): [task] — PASS/FINDING        ← DevOps subagent structured checklist
review(arch): [task] — PASS/FINDING          ← Architecture subagent structured checklist
docs: update RETRO_LOG for [task]            ← retrospective entry + advisory tracking
```

You can verify the TDD discipline by diffing any RED commit — test files import classes that don't exist until GREEN. This is the actual commit history, not aspirational documentation.

### The Review Subagents

Four specialized subagents run in parallel after each GREEN phase:

- **QA** — Dead code, exception specificity, edge cases, meaningful assertions, type annotation accuracy, docstring correctness
- **UI/UX** — WCAG 2.1 AA compliance; DX review (error messages, API ergonomics, onboarding clarity) when no UI surface exists
- **DevOps** — Hardcoded credentials, PII in logs, blocking async calls, dependency audits, CI health, secrets hygiene
- **Architecture** — File placement, dependency direction, async contract compliance, ADR drift

Each agent produces a structured finding (PASS / FINDING / SKIP per item) and a Retrospective Note. Findings are fixed before merge. Notes go to [docs/RETRO_LOG.md](docs/RETRO_LOG.md).

### Findings That Caught Real Bugs

The review process has caught substantive issues across every phase:

| Phase | Finding | Action |
|-------|---------|--------|
| P3 | `RequestBudget` added to `AgentContext` — upward dependency violation | Fixed same PR; ADR-0004 created |
| P2 | `yaml.YAMLError` inaccessible from outer except due to scoping | Restructured to try/except ImportError/else |
| P5 | `SqlAstValidator.__init__` raised wrong exception type for missing dep | Corrected to `ImportError` |
| P5 | `security/base.py` created three import paths for one type | Deleted; single canonical path |
| P6 | Sync `Anthropic` client in `async def run()` — event loop blocked | Replaced with `AsyncAnthropic` + `await` |
| P6 | `response.content[0].text` without type guard on union SDK field | `isinstance(…, TextBlock)` guard added |
| P6 | ADR-0004 Decision 2 became stale when executor wiring changed | Decision 5 appended same sprint |

### The Honest Caveats

**Context overhead is real.** The governance documents total ~1,200 lines consumed from the agent's context window before any code is written. The tradeoff is intentional, but non-trivial.

**Velocity is modest by lines-of-code metrics.** ~260 tests and ~850 lines of production code across 7 phases. A significant fraction of the commit history is review evidence and documentation. Measured by defect rate, architectural coherence, and test quality, the output is competitive.

**Review subagents are not independent humans.** They're the same LLM with different system prompts. Findings are real and have caught actual bugs and design violations, but the independence has limits the developer is aware of.

---

## Project Tracking

- [BACKLOG.md](BACKLOG.md) — Master phase tracker with dependency graph
- [docs/backlog/](docs/backlog/) — Detailed per-phase task specifications
- [docs/RETRO_LOG.md](docs/RETRO_LOG.md) — Living retrospective log (open advisories + phase notes)
- [docs/adr/](docs/adr/) — Architecture decision records

---

## License

MIT
