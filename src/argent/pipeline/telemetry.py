"""Lightweight structured telemetry for ARG pipeline stage transitions.

Emits a 'stage_start' event before each stage and a 'stage_end' event after.
The default handler writes JSON lines to stderr.  Custom handlers can be
registered via :meth:`Telemetry.replace_handlers` and :meth:`Telemetry.add_handler`.

Handler errors produce a diagnostic line on stderr but do not interrupt
pipeline execution — telemetry is non-fatal by design.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext

TelemetryHandler = Callable[[dict[str, object]], None]


def _default_handler(event: dict[str, object]) -> None:
    """Write *event* as a single JSON line to stderr."""
    sys.stderr.write(json.dumps(event) + "\n")


@dataclass
class Telemetry:
    """Structured event emitter for pipeline stage transitions.

    Usage::

        tel = Telemetry()
        tel.replace_handlers(my_handler)       # replace default stderr handler
        tel.add_handler(another_handler)        # keep existing + add more
        pipeline = Pipeline(ingress=[...], telemetry=tel)
    """

    _handlers: list[TelemetryHandler] = field(
        default_factory=lambda: [_default_handler], init=False, repr=False
    )

    def replace_handlers(self, *handlers: TelemetryHandler) -> None:
        """Replace all current handlers with *handlers*.

        Args:
            *handlers: One or more handler callables that each accept a single
                event dict.  Handler errors produce a diagnostic line on stderr
                but do not interrupt pipeline execution.
        """
        self._handlers = list(handlers)

    def add_handler(self, handler: TelemetryHandler) -> None:
        """Append *handler* without removing existing handlers.

        Args:
            handler: Callable that receives a single event dict.  Handler
                errors produce a diagnostic line on stderr but do not
                interrupt pipeline execution.
        """
        self._handlers.append(handler)

    def emit(self, event: dict[str, object]) -> None:
        """Dispatch *event* to all registered handlers.

        This is the core public dispatcher used by :meth:`emit_start`,
        :meth:`emit_end`, and any middleware that needs to emit an
        arbitrary structured event (e.g. a parse-fallback warning).

        Handler errors are caught individually: a diagnostic line is written
        to stderr and the next handler continues.  This ensures telemetry
        failures never crash the pipeline while remaining observable.
        """
        for handler in self._handlers:
            try:
                handler(event)
            except Exception as exc:
                sys.stderr.write(
                    f"[argent.telemetry] handler {handler!r} raised {exc!r}; skipping\n"
                )

    def emit_start(self, stage: str, context: AgentContext) -> float:
        """Emit a 'stage_start' event and return the start timestamp (ms).

        Args:
            stage: Name of the pipeline stage beginning.
            context: Current agent context (snapshot is included in the event).

        Returns:
            Monotonic start time in milliseconds (for computing duration).
        """
        start_ms = time.monotonic() * 1000
        self.emit(
            {
                "event": "stage_start",
                "stage": stage,
                "timestamp_ms": time.time() * 1000,
                "context_state": context.execution_state.value,
            }
        )
        return start_ms

    def emit_end(self, stage: str, context: AgentContext, start_ms: float) -> None:
        """Emit a 'stage_end' event with duration.

        Args:
            stage: Name of the pipeline stage that just completed.
            context: Current agent context.
            start_ms: Monotonic start time returned by :meth:`emit_start`.
        """
        duration_ms = time.monotonic() * 1000 - start_ms
        self.emit(
            {
                "event": "stage_end",
                "stage": stage,
                "timestamp_ms": time.time() * 1000,
                "duration_ms": duration_ms,
                "context_state": context.execution_state.value,
            }
        )
