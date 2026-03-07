"""Four-stage async middleware pipeline for the ARG execution wrapper.

Stages execute in strict order: ingress -> pre_execution -> execution -> egress.
Each stage is an ordered list of async callables that mutate AgentContext in place.
Exceptions from middleware propagate unchanged.  Telemetry end events are always
emitted via try/finally so stage_start is never orphaned.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from argent.pipeline.context import ExecutionState

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext
    from argent.pipeline.telemetry import Telemetry

Middleware = Callable[["AgentContext"], Awaitable[None]]

_STAGE_NAMES = ("ingress", "pre_execution", "execution", "egress")


@dataclass
class Pipeline:
    """Composable four-stage async middleware pipeline.

    Args:
        ingress: Middlewares that run first (payload validation, parsing).
        pre_execution: Middlewares that run after ingress (budget checks).
        execution: Middlewares that wrap the agent tool call itself.
        egress: Middlewares that run last (output trimming, telemetry flush).
        telemetry: Optional :class:`Telemetry` instance.  When provided,
            start/end events are emitted around every stage automatically.
            Telemetry end events are guaranteed via try/finally — stage_start
            events are never orphaned even when middleware raises.
    """

    ingress: list[Middleware] = field(default_factory=list)
    pre_execution: list[Middleware] = field(default_factory=list)
    execution: list[Middleware] = field(default_factory=list)
    egress: list[Middleware] = field(default_factory=list)
    telemetry: Telemetry | None = field(default=None)

    async def run(self, context: AgentContext) -> AgentContext:
        """Execute all stages in order against *context*.

        State machine contract:

        - ``context.execution_state`` is set to :attr:`ExecutionState.RUNNING`
          before the first stage begins.
        - ``context.execution_state`` is set to :attr:`ExecutionState.COMPLETE`
          after all stages finish without raising.
        - If any middleware raises, the exception propagates unchanged and
          ``COMPLETE`` is never set.  The state remains ``RUNNING`` unless the
          middleware itself explicitly set it to ``HALTED`` before raising.

        Args:
            context: The shared agent execution context.

        Returns:
            The same *context* object, mutated in place by all middlewares.

        Raises:
            Exception: Any exception raised by a middleware propagates unchanged.
                Telemetry ``stage_end`` is still emitted before the exception
                propagates (try/finally guarantee).
        """
        context.execution_state = ExecutionState.RUNNING
        stages = (self.ingress, self.pre_execution, self.execution, self.egress)
        for name, middlewares in zip(_STAGE_NAMES, stages, strict=True):
            start_ms: float | None = None
            if self.telemetry is not None:
                start_ms = self.telemetry.emit_start(name, context)
            try:
                for middleware in middlewares:
                    await middleware(context)
            finally:
                if self.telemetry is not None and start_ms is not None:
                    self.telemetry.emit_end(name, context, start_ms)
        context.execution_state = ExecutionState.COMPLETE
        return context
