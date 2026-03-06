"""Unified single-pass ingress parser middleware — The Shield's format detector.

Detects and parses the format of ``AgentContext.raw_payload`` in a single
pass, attaching the result to ``context.parsed_ast``.  Supported formats:

* **JSON** — detected first via ``json.loads``; produces ``dict | list | ...``
* **YAML** — opt-in; attempted only when ``pyyaml`` is installed; produces
  ``dict | list | ...``
* **XML** — detected via ``defusedxml``; produces
  ``xml.etree.ElementTree.Element`` (safe against XML entity attacks)
* **Plaintext** — fallback; stores ``raw_payload.decode("utf-8", errors="replace")``

The parser is **idempotent**: if ``context.parsed_ast`` is already set to any
non-``None`` value, the call is a no-op.

On any parse failure the parser:

1. Falls back to the raw decoded string.
2. Writes a one-line diagnostic to ``stderr``.
3. Emits a structured ``parse_fallback`` warning event via ``Telemetry`` (if
   provided).
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext
    from argent.pipeline.telemetry import Telemetry


class SinglePassParser:
    """Async middleware that detects format and populates ``context.parsed_ast``.

    Args:
        telemetry: Optional :class:`~argent.pipeline.telemetry.Telemetry`
            instance.  When provided, a ``parse_fallback`` warning event is
            emitted whenever the payload cannot be parsed as JSON/YAML/XML.
    """

    def __init__(self, telemetry: Telemetry | None = None) -> None:
        self._telemetry = telemetry

    async def __call__(self, context: AgentContext) -> None:
        """Parse ``context.raw_payload`` and set ``context.parsed_ast``.

        Args:
            context: The agent execution context carrying the raw payload.
        """
        if context.parsed_ast is not None:
            return

        payload = context.raw_payload
        if not payload:
            context.parsed_ast = ""
            return

        # --- attempt JSON ---
        try:
            context.parsed_ast = json.loads(payload)
            return
        except (json.JSONDecodeError, ValueError):
            pass

        # --- attempt YAML (opt-in: pyyaml must be installed) ---
        try:
            import yaml  # noqa: PLC0415

            result = yaml.safe_load(payload)
            if isinstance(result, (dict, list)):
                context.parsed_ast = result
                return
        except ImportError:
            pass
        except Exception as exc:
            # YAML parse failure — fall through to XML/plaintext
            sys.stderr.write(f"[argent.parser] YAML parse error (non-fatal): {exc!r}\n")

        # --- attempt XML (via defusedxml — safe against entity expansion attacks) ---
        try:
            context.parsed_ast = ET.fromstring(payload)
            return
        except ET.ParseError:
            pass

        # --- fallback: raw decoded string ---
        decoded = payload.decode("utf-8", errors="replace")
        sys.stderr.write(
            f"[argent.parser] could not parse payload as JSON/YAML/XML; "
            f"falling back to plaintext (first 80 chars: {decoded[:80]!r})\n"
        )
        if self._telemetry is not None:
            self._telemetry._emit(
                {
                    "event": "parse_fallback",
                    "level": "warning",
                    "reason": "payload is not valid JSON, YAML, or XML",
                    "fallback": "plaintext",
                }
            )
        context.parsed_ast = decoded
