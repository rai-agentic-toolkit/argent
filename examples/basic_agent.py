"""End-to-end example: wrapping a Claude API call with ARG.

This script demonstrates the full ARG middleware pipeline around a live Claude
API call:

    1. Ingress  — ByteSizeValidator + DepthLimitValidator + SinglePassParser
    2. Execution — ToolExecutor with RequestBudget (call and token limits)
    3. Egress   — JsonDictTrimmer to cap oversized responses

Usage::

    export ANTHROPIC_API_KEY=sk-ant-...
    poetry run python examples/basic_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import anthropic

from argent import (
    AgentContext,
    BudgetExhaustedError,
    ByteSizeValidator,
    DepthLimitValidator,
    JsonDictTrimmer,
    NestingDepthError,
    PayloadTooLargeError,
    Pipeline,
    RequestBudget,
    SinglePassParser,
    ToolExecutor,
    ToolTimeoutError,
)

# ── Configuration ──────────────────────────────────────────────────────────────

_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
_MODEL = "claude-sonnet-4-6"

# Fictional prompt — no PII
_PROMPT = (
    "List three fictional medieval kingdoms as a JSON object.  "
    "Each key is the kingdom name; each value is an object with fields "
    "'capital' (string), 'exports' (list of strings), and 'founded' (integer year).  "
    "Respond with JSON only — no markdown fences, no prose."
)


# ── Stage 1: Ingress pipeline ──────────────────────────────────────────────────


def _build_pipeline() -> Pipeline:
    """Return an ARG Pipeline with ingress validation and parsing wired."""
    return Pipeline(
        ingress=[
            # Reject payloads larger than 64 KiB before any parsing work.
            ByteSizeValidator(max_bytes=64 * 1024),
            # Reject deeply nested structures to prevent zip-bomb ASTs.
            DepthLimitValidator(max_depth=20),
            # Detect format (JSON / YAML / XML / plaintext) and populate
            # context.parsed_ast for downstream consumers.
            SinglePassParser(),
        ]
    )


# ── Stage 2: Claude API call ───────────────────────────────────────────────────


async def _invoke_claude() -> bytes:
    """Call the Claude API asynchronously and return the response as raw bytes.

    Uses AsyncAnthropic so the event loop is never blocked during the network
    round-trip.  In production code, instantiate a module-level client for
    connection reuse rather than creating a new one per call.
    """
    client = anthropic.AsyncAnthropic(api_key=_API_KEY)
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": _PROMPT}],
    )
    # Guard the union type: content[0] may be TextBlock, ToolUseBlock, etc.
    if not response.content or not isinstance(response.content[0], anthropic.types.TextBlock):
        block_type = type(response.content[0]).__name__ if response.content else "empty"
        raise RuntimeError(
            f"Expected TextBlock as first content block, got {block_type}. "
            "Adjust the prompt or check stop_reason."
        )
    return response.content[0].text.encode()


# ── Stage 3: Fictional tool execution via ToolExecutor ────────────────────────


def _lookup_kingdom(name: str) -> dict[str, object]:
    """Return hard-coded lore for a fictional kingdom (simulates a real tool)."""
    lore: dict[str, dict[str, object]] = {
        "Valdris": {"capital": "Stonegate", "founded": 342, "note": "Iron trade hub"},
        "Mirefall": {"capital": "Duskholm", "founded": 501, "note": "Amber exports"},
    }
    return lore.get(name, {"note": f"No records found for '{name}'"})


# ── Main async pipeline ────────────────────────────────────────────────────────


async def run() -> None:
    """Execute the full ARG-wrapped agent pipeline."""

    # 1. Fetch response from Claude — wrap as AgentContext for ingress.
    print(f"[ARG] Calling {_MODEL} …")
    raw_bytes = await _invoke_claude()
    ctx = AgentContext(raw_payload=raw_bytes)

    # 2. Run ingress pipeline: validate + parse.
    pipeline = _build_pipeline()
    try:
        await pipeline.run(ctx)
    except (PayloadTooLargeError, NestingDepthError) as exc:
        print(f"[ARG] Ingress blocked: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[ARG] Ingress passed — parsed_ast type: {type(ctx.parsed_ast).__name__}")

    # 3. Execute a tool under budget control.
    #    For concurrent deployments that run many agents in the same process,
    #    pass a dedicated thread pool for isolation:
    #        import concurrent.futures
    #        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    #            executor = ToolExecutor(budget=budget, executor=pool)
    #    The caller owns the pool lifecycle; ToolExecutor does not shut it down.
    budget = RequestBudget(max_calls=5, max_tokens=200)
    executor = ToolExecutor(budget=budget)

    try:
        tool_result = await executor.execute(
            _lookup_kingdom,
            "Valdris",  # positional arg forwarded to the tool
            token_cost=10,
        )
        print(f"[ARG] Tool result: {tool_result}")
    except BudgetExhaustedError as exc:
        print(f"[ARG] Budget exhausted before tool ran: {exc}", file=sys.stderr)
        sys.exit(1)
    except ToolTimeoutError as exc:
        print(f"[ARG] Tool timed out: {exc}", file=sys.stderr)
        sys.exit(1)

    # 4. Egress: trim the Claude response to fit a 600-char budget.
    if isinstance(ctx.parsed_ast, dict):
        trimmer = JsonDictTrimmer(max_chars=600)
        output = trimmer.trim(json.dumps(ctx.parsed_ast, indent=2))
    else:
        output = str(ctx.parsed_ast)

    print("\n[ARG] Pipeline complete — egress output:")
    print(output)
    print(
        f"\n[ARG] Budget remaining — calls: {budget.remaining_calls}, "
        f"tokens: {budget.remaining_tokens}"
    )


def main() -> None:
    if not _API_KEY:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it with:  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
