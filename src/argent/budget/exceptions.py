"""Custom exceptions for the ARG budget and execution layer — The Leash.

These exceptions are raised by budget enforcement and tool execution
middleware when a configured limit is violated.
"""

from __future__ import annotations


class BudgetExhaustedError(Exception):
    """Raised when a call or token budget limit is crossed.

    Attributes:
        limit_kind: Which limit was hit — ``"calls"`` or ``"tokens"``.
        current: The counter value that triggered the violation.
        limit: The configured maximum for the exhausted resource.
    """

    def __init__(self, limit_kind: str, current: int, limit: int) -> None:
        self.limit_kind = limit_kind
        self.current = current
        self.limit = limit
        super().__init__(
            f"Budget exhausted: {limit_kind} limit of {limit} exceeded (current={current})"
        )


class ToolTimeoutError(Exception):
    """Raised when a tool call exceeds the configured per-call timeout.

    Attributes:
        timeout_seconds: The configured timeout that was exceeded.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Tool call exceeded timeout of {timeout_seconds}s")


class ToolRecursionError(Exception):
    """Raised when a tool call triggers a Python RecursionError.

    Wraps the stdlib RecursionError so callers can distinguish between
    recursion-caused failures and other kinds of tool exceptions.
    """

    def __init__(self) -> None:
        super().__init__("Tool call caused infinite recursion (RecursionError detected)")
