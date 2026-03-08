"""Tests for AgentContext state machine object.

P8-T04: Remove enum existence theater; add meaningful lifecycle test.
"""

import pytest

from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline


class TestExecutionState:
    """Tests for the ExecutionState enum."""

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
        trade-off: we trust our own middleware code.
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

    async def test_execution_state_lifecycle(self) -> None:
        """ADR-0002 state machine: PENDING → RUNNING → COMPLETE; stays RUNNING on raise.

        Three invariants from the state machine contract:
        1. A fresh AgentContext starts at PENDING.
        2. After pipeline.run() completes without raising, state is COMPLETE.
        3. When a middleware raises without setting HALTED, state stays RUNNING.
        """
        # Invariant 1: fresh context starts at PENDING
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.execution_state is ExecutionState.PENDING

        # Invariant 2: successful run → COMPLETE
        pipeline = Pipeline()
        await pipeline.run(ctx)
        assert ctx.execution_state is ExecutionState.COMPLETE

        # Invariant 3: middleware raises → state stays RUNNING (not COMPLETE)
        async def raising_middleware(c: AgentContext) -> None:
            raise RuntimeError("injected failure")

        ctx2 = AgentContext(raw_payload=b"data")
        pipeline2 = Pipeline(ingress=[raising_middleware])
        with pytest.raises(RuntimeError):
            await pipeline2.run(ctx2)
        assert ctx2.execution_state is ExecutionState.RUNNING
