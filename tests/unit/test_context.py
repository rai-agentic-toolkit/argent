"""Tests for AgentContext state machine object.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/pipeline/context.py exists.
"""

import pytest

from argent.pipeline.context import AgentContext, ExecutionState


class TestExecutionState:
    """Tests for the ExecutionState enum."""

    def test_has_pending(self) -> None:
        """ExecutionState exposes a PENDING variant."""
        assert ExecutionState.PENDING

    def test_has_running(self) -> None:
        """ExecutionState exposes a RUNNING variant."""
        assert ExecutionState.RUNNING

    def test_has_halted(self) -> None:
        """ExecutionState exposes a HALTED variant."""
        assert ExecutionState.HALTED

    def test_has_complete(self) -> None:
        """ExecutionState exposes a COMPLETE variant."""
        assert ExecutionState.COMPLETE

    def test_values_are_distinct(self) -> None:
        """All four ExecutionState variants have distinct values."""
        states = [
            ExecutionState.PENDING,
            ExecutionState.RUNNING,
            ExecutionState.HALTED,
            ExecutionState.COMPLETE,
        ]
        assert len(set(states)) == 4


class TestAgentContextInstantiation:
    """Tests for AgentContext construction and defaults."""

    def test_instantiation_with_required_fields(self) -> None:
        """AgentContext is created with raw_payload provided."""
        ctx = AgentContext(raw_payload=b"hello")
        assert isinstance(ctx, AgentContext)
        assert ctx.raw_payload == b"hello"

    def test_raw_payload_stored_as_bytes(self) -> None:
        """raw_payload field is bytes, not str."""
        ctx = AgentContext(raw_payload=b"test payload")
        assert isinstance(ctx.raw_payload, bytes)
        assert ctx.raw_payload == b"test payload"

    def test_parsed_ast_defaults_to_none(self) -> None:
        """parsed_ast is None until a parser middleware populates it."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.parsed_ast is None

    def test_token_count_defaults_to_zero(self) -> None:
        """token_count starts at 0."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.token_count == 0

    def test_call_count_defaults_to_zero(self) -> None:
        """call_count starts at 0."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.call_count == 0

    def test_execution_state_defaults_to_pending(self) -> None:
        """execution_state defaults to PENDING."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.execution_state is ExecutionState.PENDING

    def test_empty_bytes_payload_is_valid(self) -> None:
        """AgentContext accepts an empty bytes payload."""
        ctx = AgentContext(raw_payload=b"")
        assert ctx.raw_payload == b""

    def test_large_payload_is_accepted(self) -> None:
        """AgentContext accepts a large payload without truncation."""
        payload = b"x" * 10_000
        ctx = AgentContext(raw_payload=payload)
        assert len(ctx.raw_payload) == 10_000


class TestAgentContextMutability:
    """Tests for AgentContext field mutability constraints."""

    def test_parsed_ast_can_be_set(self) -> None:
        """parsed_ast can be updated by middleware."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.parsed_ast = {"key": "value"}
        assert ctx.parsed_ast == {"key": "value"}

    def test_execution_state_can_be_updated(self) -> None:
        """execution_state can transition to RUNNING."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.execution_state = ExecutionState.RUNNING
        assert ctx.execution_state is ExecutionState.RUNNING

    def test_token_count_can_be_incremented(self) -> None:
        """token_count can be incremented by budget middleware."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.token_count += 42
        assert ctx.token_count == 42

    def test_call_count_can_be_incremented(self) -> None:
        """call_count can be incremented by budget middleware."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.call_count += 1
        assert ctx.call_count == 1

    def test_raw_payload_is_immutable_after_construction(self) -> None:
        """raw_payload cannot be reassigned via normal attribute assignment."""
        ctx = AgentContext(raw_payload=b"original")
        with pytest.raises(AttributeError):
            ctx.raw_payload = b"tampered"  # type: ignore[misc]

    def test_raw_payload_immutability_guard_is_bypassed_by_object_setattr(self) -> None:
        """object.__setattr__() bypasses the immutability guard — known limitation.

        The __setattr__ guard protects against accidental reassignment in normal
        Python code.  Callers who invoke object.__setattr__() directly are
        operating outside the public API contract.  This is a deliberate design
        trade-off: we trust our own middleware code.  See TODO(P2-T01) in
        context.py for a potential __slots__-based fix.
        """
        ctx = AgentContext(raw_payload=b"original")
        object.__setattr__(ctx, "raw_payload", b"bypassed")
        assert ctx.raw_payload == b"bypassed"  # bypass succeeds — known limitation


class TestAgentContextStateTransitions:
    """Tests for execution state transition semantics."""

    def test_full_lifecycle(self) -> None:
        """Context can transition through the full PENDING->RUNNING->COMPLETE lifecycle."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.execution_state is ExecutionState.PENDING
        ctx.execution_state = ExecutionState.RUNNING
        assert ctx.execution_state is ExecutionState.RUNNING
        ctx.execution_state = ExecutionState.COMPLETE
        assert ctx.execution_state is ExecutionState.COMPLETE

    def test_halted_lifecycle(self) -> None:
        """Context can transition to HALTED from RUNNING."""
        ctx = AgentContext(raw_payload=b"data")
        ctx.execution_state = ExecutionState.RUNNING
        ctx.execution_state = ExecutionState.HALTED
        assert ctx.execution_state is ExecutionState.HALTED
