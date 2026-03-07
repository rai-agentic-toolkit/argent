"""AgentContext state machine for the ARG middleware pipeline.

Provides the shared mutable context object passed through every pipeline
stage, tracking execution state and parsed payload data.
"""

from __future__ import annotations

import enum
import xml.etree.ElementTree as ET  # nosec B405 — type annotation only; no XML is parsed here
from dataclasses import dataclass, field
from typing import Any, TypeAlias


class ExecutionState(enum.Enum):
    """Lifecycle states for a single agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    HALTED = "halted"
    COMPLETE = "complete"


ParsedPayload: TypeAlias = dict[str, Any] | list[Any] | ET.Element | str | None

_IMMUTABLE_FIELDS = frozenset({"raw_payload"})


@dataclass
class AgentContext:
    """Shared context object threaded through every middleware stage.

    Attributes:
        raw_payload: The original bytes submitted to the pipeline.
            Immutable after construction.  Note: ``object.__setattr__``
            bypasses this guard — callers who use it directly operate
            outside the public API contract (known limitation).
        parsed_ast: Structured representation produced by parser middleware.
            None until populated by ingress middleware.
        token_count: Running total of tokens consumed.  Orphaned field —
            scheduled for removal in P4-T02 (budget state lives in
            ``RequestBudget``; see ADR-0004).
        call_count: Running total of tool calls issued.  Orphaned field —
            scheduled for removal in P4-T02 (see ADR-0004).
        execution_state: Current lifecycle state of this execution.
    """

    raw_payload: bytes
    parsed_ast: ParsedPayload = field(default=None)
    token_count: int = field(default=0)
    call_count: int = field(default=0)
    execution_state: ExecutionState = field(default=ExecutionState.PENDING)

    def __setattr__(self, name: str, value: object) -> None:
        """Block accidental reassignment of immutable fields after construction."""
        if name in _IMMUTABLE_FIELDS and hasattr(self, name):
            raise AttributeError(f"'{type(self).__name__}.{name}' is immutable after construction")
        super().__setattr__(name, value)
