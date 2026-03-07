"""Tests for SecurityValidator Protocol and SecurityViolationError.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/security/base.py and src/argent/security/exceptions.py exist.
"""

import pytest

from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline
from argent.security.base import SecurityValidator
from argent.security.exceptions import SecurityViolationError


class TestSecurityViolationError:
    """Tests for the SecurityViolationError exception class."""

    def test_has_policy_name_and_reason(self) -> None:
        """SecurityViolationError carries policy_name and reason fields."""
        err = SecurityViolationError(policy_name="TestPolicy", reason="test reason")
        assert err.policy_name == "TestPolicy"
        assert err.reason == "test reason"

    def test_is_exception_subclass(self) -> None:
        """SecurityViolationError is a subclass of Exception."""
        assert issubclass(SecurityViolationError, Exception)

    def test_str_includes_policy_name_and_reason(self) -> None:
        """String representation includes both policy_name and reason."""
        err = SecurityViolationError(policy_name="SqlPolicy", reason="DROP TABLE blocked")
        s = str(err)
        assert "SqlPolicy" in s
        assert "DROP TABLE blocked" in s

    def test_can_be_raised_and_caught(self) -> None:
        """SecurityViolationError can be raised and caught as Exception."""
        with pytest.raises(SecurityViolationError) as exc_info:
            raise SecurityViolationError(policy_name="P", reason="R")
        assert exc_info.value.policy_name == "P"
        assert exc_info.value.reason == "R"


class TestSecurityValidatorProtocol:
    """Tests for the SecurityValidator structural Protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """A class with validate(context) -> None satisfies SecurityValidator."""

        class MyValidator:
            def validate(self, context: AgentContext) -> None:
                pass

        assert isinstance(MyValidator(), SecurityValidator)

    def test_object_without_validate_does_not_satisfy_protocol(self) -> None:
        """An object without a validate method does not satisfy SecurityValidator."""
        assert not isinstance(object(), SecurityValidator)

    def test_class_with_validate_method_name_accepted_at_runtime(self) -> None:
        """Runtime isinstance only checks method name presence, not signature."""

        class WrongSig:
            def validate(self) -> None:  # no context param
                pass

        # Runtime check only verifies method name exists — type-checkers catch mismatches
        assert isinstance(WrongSig(), SecurityValidator)


class TestPipelineSecurityIntegration:
    """Tests for Pipeline security_validators wiring."""

    async def test_empty_validators_list_is_noop(self) -> None:
        """Pipeline with no validators runs normally and returns context."""
        ctx = AgentContext(raw_payload=b"data")
        result = await Pipeline(security_validators=[]).run(ctx)
        assert result is ctx

    async def test_validator_receives_context(self) -> None:
        """Validator's validate() is called with the AgentContext."""
        received: list[AgentContext] = []

        class Capturing:
            def validate(self, context: AgentContext) -> None:
                received.append(context)

        ctx = AgentContext(raw_payload=b"data")
        await Pipeline(security_validators=[Capturing()]).run(ctx)
        assert received == [ctx]

    async def test_validators_run_before_execution_stage(self) -> None:
        """Security validators run before the execution-stage middlewares."""
        order: list[str] = []

        class OrderChecker:
            def validate(self, context: AgentContext) -> None:
                order.append("validate")

        async def exec_mw(ctx: AgentContext) -> None:
            order.append("execute")

        pipeline = Pipeline(security_validators=[OrderChecker()], execution=[exec_mw])
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert order.index("validate") < order.index("execute")

    async def test_security_violation_propagates_from_pipeline(self) -> None:
        """A SecurityViolationError raised by a validator propagates from Pipeline.run()."""

        class Blocker:
            def validate(self, context: AgentContext) -> None:
                raise SecurityViolationError(policy_name="Blocker", reason="blocked")

        with pytest.raises(SecurityViolationError, match="blocked"):
            await Pipeline(security_validators=[Blocker()]).run(AgentContext(raw_payload=b"data"))

    async def test_halted_state_preserved_when_validator_raises(self) -> None:
        """HALTED set by a validator is not overwritten when the exception propagates."""

        class Halting:
            def validate(self, context: AgentContext) -> None:
                context.execution_state = ExecutionState.HALTED
                raise SecurityViolationError(policy_name="H", reason="halt")

        ctx = AgentContext(raw_payload=b"data")
        with pytest.raises(SecurityViolationError):
            await Pipeline(security_validators=[Halting()]).run(ctx)
        assert ctx.execution_state == ExecutionState.HALTED

    async def test_multiple_validators_all_called_when_passing(self) -> None:
        """All validators are called when none raise."""
        call_count = 0

        class Counter:
            def validate(self, context: AgentContext) -> None:
                nonlocal call_count
                call_count += 1

        await Pipeline(security_validators=[Counter(), Counter(), Counter()]).run(
            AgentContext(raw_payload=b"data")
        )
        assert call_count == 3

    async def test_first_violation_stops_subsequent_validators(self) -> None:
        """After a validator raises, subsequent validators are not called."""
        second_called = False

        class First:
            def validate(self, context: AgentContext) -> None:
                raise SecurityViolationError(policy_name="First", reason="stop")

        class Second:
            def validate(self, context: AgentContext) -> None:
                nonlocal second_called
                second_called = True

        with pytest.raises(SecurityViolationError):
            await Pipeline(security_validators=[First(), Second()]).run(
                AgentContext(raw_payload=b"data")
            )
        assert not second_called

    async def test_pipeline_without_security_validators_has_empty_default(self) -> None:
        """Pipeline constructed without security_validators defaults to empty list."""
        pipeline = Pipeline()
        assert pipeline.security_validators == []
