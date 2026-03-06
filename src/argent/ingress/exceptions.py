"""Custom exceptions for the ARG ingress layer.

These exceptions are raised by ingress middleware validators when a payload
violates a pre-configured limit.  Both exception types set the AgentContext
execution_state to HALTED before being raised.
"""

from __future__ import annotations


class PayloadTooLargeError(Exception):
    """Raised when a payload exceeds the configured byte-size limit.

    Attributes:
        actual: Actual payload size in bytes.
        limit: Configured maximum size in bytes.
    """

    def __init__(self, actual: int, limit: int) -> None:
        self.actual = actual
        self.limit = limit
        super().__init__(f"Payload size {actual} bytes exceeds limit of {limit} bytes")


class NestingDepthError(Exception):
    """Raised when a payload's estimated nesting depth exceeds the configured limit.

    The depth estimate is a fast heuristic based on bracket character counting
    — no parsing is performed.

    Attributes:
        estimated_depth: Estimated nesting depth (count of opening brackets).
        limit: Configured maximum depth.
    """

    def __init__(self, estimated_depth: int, limit: int) -> None:
        self.estimated_depth = estimated_depth
        self.limit = limit
        super().__init__(
            f"Payload nesting depth estimate {estimated_depth} exceeds limit of {limit}"
        )
