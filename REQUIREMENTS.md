# Product Requirements Document: Agentic Runtime Gateway (ARG)

## 1. Problem Statement
Current AI agent architectures suffer from systemic fragility. Agents are permitted to ingest maliciously large payloads, execute tools in infinite loops, and blind themselves by overflowing their own context windows with bloated stdout. Existing solutions (like the legacy `rai-agentic-toolkit`) address these issues via fragmented micro-libraries, resulting in redundant AST parsing, severe CPU overhead, and brittle, substring-based security evaluations.

## 2. Product Vision
ARG is a deterministic, middleware-driven execution wrapper for AI agents. It acts as a single, highly optimized checkpoint that guarantees payload hygiene, enforces strict execution budgets, and physically compresses output payloads to mathematically guarantee context-window compliance.

## 3. Non-Functional Requirements (NFRs)
- **Zero-Copy / Single-Pass Parsing:** Payloads must be parsed structurally (e.g., into a JSON AST) exactly once per cycle to conserve compute. This is a hard requirement for deployments running on resource-constrained hardware, such as multi-node home server racks used for local AI experimentation, where memory allocation overhead must be aggressively minimized.
- **Graceful Degradation:** If structural parsing fails (e.g., malformed JSON), the system must silently fall back to plaintext slicing. It must never crash the host event loop.
- **Zero-Dependency Core:** The core pipeline must rely only on the Python standard library. Heavy parsers (e.g., `sqlglot`, `tiktoken`) must be strictly opt-in extras.

## 4. Overarching Business Rules (The "Must-Haves")
These are the inviolable laws of the framework.

| Rule ID | Name | Description |
|---|---|---|
| BR-01 | Absolute Budget Enforcement | The system must halt agent execution immediately upon hitting a defined `max_calls` or `max_tokens` limit. No exceptions. |
| BR-02 | No Blind Truncation | When compressing payloads, structural integrity (e.g., Markdown table headers, Python exception tails) must be preserved if structurally possible. |
| BR-03 | Semantic Over Syntactic Security | The system shall deprecate naive substring matching for security (e.g., blocking the string "DROP"). Security policies must be evaluated semantically via AST parsing or dedicated classifier models. |
| BR-04 | Pre-Allocation Limits | The system must reject oversized inputs (byte-size) before attempting structural memory allocation to prevent Out-of-Memory (OOM) crashes. |

## 5. Project Chunking (Epics & Features)
To build this methodically, we will break the architecture into sequential Epics.

### Epic 1: The Core Pipeline & AgentContext State Machine
*The foundation. We build the highway before we build the toll booths.*
- **Feature 1.1:** Define the `AgentContext` object to hold the raw payload, parsed AST, token counts, and execution state.
- **Feature 1.2:** Implement the Base Middleware Pipeline (Ingress -> Pre-Execution -> Execution -> Egress).
- **Feature 1.3:** Build the Telemetry/Observability hooks (OpenTelemetry ready) for standardized logging of all pipeline events.

### Epic 2: Ingress Hygiene (The Shield)
*Replacing `secure-ingest`.*
- **Feature 2.1:** Implement raw byte-size and depth-limit validators (executes before JSON/YAML parsing).
- **Feature 2.2:** Build the unified Single-Pass Parser (JSON, YAML, XML) that attaches the parsed object to the `AgentContext`.

### Epic 3: Budgeting & Execution Isolation (The Leash)
*Replacing `tool-leash`.*
- **Feature 3.1:** Implement stateful token and call counters.
- **Feature 3.2:** Build the tool execution wrapper (handles timeouts, traps infinite recursion, and catches native tool exceptions).

### Epic 4: Semantic Context Shaping (The Trimmer)
*Replacing `output-trimmer` and `context-diet`.*
- **Feature 4.1:** Implement format-aware output truncators (Python Traceback, Markdown Table, JSON Array/Dict squashers).
- **Feature 4.2:** Build the dynamic budget calculator (evaluates remaining LLM context window and automatically calculates the `max_chars` allowance for the truncators).

### Epic 5: Pluggable Security Policies (The Guard)
*Replacing the flawed `CallGuard`.*
- **Feature 5.1:** Define the `SecurityValidator` protocol.
- **Feature 5.2:** Implement the SQL AST Validator (requires optional `sqlglot` dependency) to semantically block destructive queries.

## 6. Definition of Done (DoD) for the MVP
The MVP is complete when a developer can wrap an untrusted, autonomous LLM agent with the ARG framework, feed it a 50MB malformed payload, instruct it to execute a destructive tool in an infinite loop, and the framework safely traps, logs, and terminates the operation without a single memory leak or unhandled host exception.
