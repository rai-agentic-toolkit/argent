"""Lightweight structured telemetry for ARG pipeline stage transitions.

Emits a 'stage_start' event before each stage and a 'stage_end' event after.
The default handler writes JSON lines to stderr.  Custom handlers can be
registered via :meth:`Telemetry.register_handler`.

Handler errors are caught and silenced so that telemetry failures never
interrupt pipeline execution (telemetry is non-fatal by design).
"""

from __future__ import annotations

import contextlib
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
        tel.register_handler(my_handler)
        pipeline = Pipeline(ingress=[...], telemetry=tel)
    """

    _handlers: list[TelemetryHandler] = field(
        default_factory=lambda: [_default_handler], init=False, repr=False
    )

    def register_handler(self, handler: TelemetryHandler) -> None:
        """Replace the default handler list with *handler*.

        The first call replaces the built-in stderr handler.  Subsequent calls
        append additional handlers so every registered handler receives every
        event.

        Args:
            handler: Callable that receives a single event dict.
        """
        if self._handlers == [_default_handler]:
            self._handlers = [handler]
        else:
            self._handlers.append(handler)

    def _emit(self, event: dict[str, object]) -> None:
        """Dispatch *event* to all registered handlers, swallowing errors."""
        for handler in self._handlers:
            with contextlib.suppress(Exception):
                handler(event)

    def emit_start(self, stage: str, context: AgentContext) -> float:
        """Emit a 'stage_start' event and return the start timestamp (ms).

        Args:
            stage: Name of the pipeline stage beginning.
            context: Current agent context (snapshot is included in the event).

        Returns:
            Monotonic start time in milliseconds (for computing duration).
        """
        start_ms = time.monotonic() * 1000
        self._emit(
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
        self._emit(
            {
                "event": "stage_end",
                "stage": stage,
                "timestamp_ms": time.time() * 1000,
                "duration_ms": duration_ms,
                "context_state": context.execution_state.value,
            }
        )
