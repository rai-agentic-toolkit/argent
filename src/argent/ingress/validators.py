"""Ingress pre-parse validators — The Shield's fast rejection layer.

Both validators implement the async Middleware protocol:
``Callable[[AgentContext], Awaitable[None]]``

They run at the very beginning of the ingress stage, before any structural
parser is invoked, so a maliciously crafted payload is rejected with minimal
memory and CPU cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from argent.ingress.exceptions import NestingDepthError, PayloadTooLargeError
from argent.pipeline.context import ExecutionState

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext

_DEFAULT_MAX_BYTES: int = 1_048_576  # 1 MiB
_DEFAULT_MAX_DEPTH: int = 20


class ByteSizeValidator:
    """Async middleware that rejects payloads exceeding a byte-size limit.

    The check is O(1) — it reads ``len(context.raw_payload)`` without
    copying or parsing any content.

    Args:
        max_bytes: Maximum allowed payload size in bytes.
            Defaults to 1 MiB (1_048_576).

    Raises:
        PayloadTooLargeError: If ``len(raw_payload) > max_bytes``.
            Context ``execution_state`` is set to ``HALTED`` before raising.
    """

    def __init__(self, max_bytes: int = _DEFAULT_MAX_BYTES) -> None:
        self._max_bytes = max_bytes

    async def __call__(self, context: AgentContext) -> None:
        """Validate payload size against the configured limit.

        Args:
            context: The agent execution context carrying the raw payload.

        Raises:
            PayloadTooLargeError: If the payload exceeds ``max_bytes``.
        """
        actual = len(context.raw_payload)
        if actual > self._max_bytes:
            context.execution_state = ExecutionState.HALTED
            raise PayloadTooLargeError(actual=actual, limit=self._max_bytes)


class DepthLimitValidator:
    """Async middleware that rejects payloads with excessive nesting depth.

    Uses a fast bracket-counting heuristic (O(n) character scan, no parsing):
    the maximum concurrent open-bracket count (``{`` or ``[``) approximates
    the structural nesting depth.  This intentionally over-estimates depth
    to err on the side of caution.

    Args:
        max_depth: Maximum estimated nesting depth allowed.
            Defaults to 20.

    Raises:
        NestingDepthError: If the estimated depth exceeds ``max_depth``.
            Context ``execution_state`` is set to ``HALTED`` before raising.
    """

    def __init__(self, max_depth: int = _DEFAULT_MAX_DEPTH) -> None:
        self._max_depth = max_depth

    async def __call__(self, context: AgentContext) -> None:
        """Validate payload nesting depth against the configured limit.

        Args:
            context: The agent execution context carrying the raw payload.

        Raises:
            NestingDepthError: If the estimated nesting depth exceeds ``max_depth``.
        """
        depth = self._estimate_depth(context.raw_payload)
        if depth > self._max_depth:
            context.execution_state = ExecutionState.HALTED
            raise NestingDepthError(estimated_depth=depth, limit=self._max_depth)

    @staticmethod
    def _estimate_depth(payload: bytes) -> int:
        """Estimate nesting depth via bracket character counting.

        Tracks the maximum concurrent open-bracket count as a proxy for
        structural depth.  Both ``{``/``}`` and ``[``/``]`` are counted
        together since they both represent nesting in JSON/YAML/etc.

        Args:
            payload: Raw bytes to scan.

        Returns:
            Maximum estimated depth encountered.
        """
        current = 0
        max_depth = 0
        for byte in payload:
            if byte in (ord("{"), ord("[")):
                current += 1
                max_depth = max(max_depth, current)
            elif byte in (ord("}"), ord("]")):
                if current > 0:
                    current -= 1
        return max_depth
