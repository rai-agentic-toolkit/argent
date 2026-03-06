"""Unified single-pass ingress parser middleware — The Shield's format detector.

Detects and parses the format of ``AgentContext.raw_payload`` in a single
pass, attaching the result to ``context.parsed_ast``.  Supported formats:

* **JSON** — detected first via ``json.loads``; produces ``dict | list | ...``
* **YAML** — opt-in; attempted only when ``pyyaml`` is installed; produces
  ``dict | list | ...``
* **XML** — detected via ``defusedxml`` (hard runtime dep — XML security is
  non-negotiable for a payload hygiene layer; see ADR-0003); produces
  ``xml.etree.ElementTree.Element``
* **Plaintext** — fallback; stores ``raw_payload.decode("utf-8", errors="replace")``

The parser is **idempotent**: if ``context.parsed_ast`` is already set to any
non-``None`` value, the call is a no-op.

On any parse failure the parser:

1. Falls back to the raw decoded string.
2. Emits a WARNING via ``logging.getLogger("argent.ingress.parser")``.
3. Emits a structured ``parse_fallback`` warning event via ``Telemetry`` (if
   provided) **only when all structured formats fail** and the payload is
   stored as plaintext.  Intermediate format-specific failures (e.g. a YAML
   parse error that falls through to XML) do not emit a telemetry event.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

# defusedxml is a hard runtime dependency (declared in pyproject.toml).
# Unlike pyyaml (which is optional), XML security is non-negotiable for an
# ingress payload-hygiene layer: defusedxml guards against entity expansion
# (XXE) and billion-laughs attacks that the stdlib xml.etree.ElementTree
# does not protect against.  See ADR-0003.
import defusedxml.ElementTree as ET

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext
    from argent.pipeline.telemetry import Telemetry

logger = logging.getLogger(__name__)


class SinglePassParser:
    """Async middleware that detects format and populates ``context.parsed_ast``.

    Args:
        telemetry: Optional :class:`~argent.pipeline.telemetry.Telemetry`
            instance.  When provided, a ``parse_fallback`` warning event is
            emitted when all structured formats fail and the payload falls
            back to plaintext.
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
        except ImportError:
            pass
        else:
            try:
                result = yaml.safe_load(payload)
                if isinstance(result, (dict, list)):
                    context.parsed_ast = result
                    return
            except yaml.YAMLError as exc:
                # YAML parse failure — fall through to XML/plaintext
                logger.warning("YAML parse error (non-fatal): %r", exc)

        # --- attempt XML (defusedxml — guards against XXE and entity attacks) ---
        try:
            context.parsed_ast = ET.fromstring(payload)
            return
        except ET.ParseError:
            pass

        # --- fallback: raw decoded string ---
        decoded = payload.decode("utf-8", errors="replace")
        logger.warning(
            "could not parse payload as JSON/YAML/XML; "
            "falling back to plaintext (first 80 chars: %r)",
            decoded[:80],
        )
        if self._telemetry is not None:
            self._telemetry.emit(
                {
                    "event": "parse_fallback",
                    "level": "warning",
                    "reason": "payload is not valid JSON, YAML, or XML",
                    "fallback": "plaintext",
                }
            )
        context.parsed_ast = decoded
