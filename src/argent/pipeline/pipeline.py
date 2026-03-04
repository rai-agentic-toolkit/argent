"""Four-stage middleware pipeline for the ARG execution wrapper.

Stages execute in strict order: ingress -> pre_execution -> execution -> egress.
Each stage is an ordered list of callables that mutate AgentContext in place.
Exceptions from middleware propagate -- the pipeline never swallows errors.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext
    from argent.pipeline.telemetry import Telemetry

Middleware = Callable[["AgentContext"], None]

_STAGE_NAMES = ("ingress", "pre_execution", "execution", "egress")


@dataclass
class Pipeline:
    """Composable four-stage middleware pipeline.

    Args:
        ingress: Middlewares that run first (payload validation, parsing).
        pre_execution: Middlewares that run after ingress (budget checks).
        execution: Middlewares that wrap the agent tool call itself.
        egress: Middlewares that run last (output trimming, telemetry flush).
        telemetry: Optional :class:`Telemetry` instance.  When provided,
            start/end events are emitted around every stage automatically.
    """

    ingress: list[Middleware] = field(default_factory=list)
    pre_execution: list[Middleware] = field(default_factory=list)
    execution: list[Middleware] = field(default_factory=list)
    egress: list[Middleware] = field(default_factory=list)
    telemetry: Telemetry | None = field(default=None)

    def run(self, context: AgentContext) -> AgentContext:
        """Execute all stages in order against *context*.

        Args:
            context: The shared agent execution context.

        Returns:
            The same *context* object, mutated in place by all middlewares.

        Raises:
            Exception: Any exception raised by a middleware propagates unchanged.
        """
        stages = (self.ingress, self.pre_execution, self.execution, self.egress)
        for name, middlewares in zip(_STAGE_NAMES, stages, strict=True):
            start_ms: float | None = None
            if self.telemetry is not None:
                start_ms = self.telemetry.emit_start(name, context)
            for middleware in middlewares:
                middleware(context)
            if self.telemetry is not None and start_ms is not None:
                self.telemetry.emit_end(name, context, start_ms)
        return context
