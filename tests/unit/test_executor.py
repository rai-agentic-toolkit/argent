"""Tests for the ToolExecutor safe tool invocation wrapper.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/budget/executor.py exists.
"""

from __future__ import annotations

import time

import pytest

from argent.budget.budget import RequestBudget
from argent.budget.exceptions import BudgetExhaustedError, ToolRecursionError, ToolTimeoutError
from argent.budget.executor import ToolExecutor
from argent.pipeline.context import AgentContext


class TestBasicExecution:
    """Tests for normal (happy-path) tool invocation."""

    def test_execute_returns_tool_result(self) -> None:
        """Normal tool invocation returns the tool's return value."""
        executor = ToolExecutor()
        result = executor.execute(lambda: 42)
        assert result == 42

    def test_execute_passes_args_and_kwargs(self) -> None:
        """execute() forwards *args and **kwargs to the tool."""
        executor = ToolExecutor()
        result = executor.execute(lambda x, y=0: x + y, 3, y=4)
        assert result == 7

    def test_execute_records_budget_on_success(self) -> None:
        """budget.record_call is called with the correct token_cost after success."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        ctx = AgentContext(raw_payload=b"data")
        ctx.budget = budget
        executor = ToolExecutor(context=ctx)
        executor.execute(lambda: None, token_cost=50)
        assert budget.remaining_tokens == 950
        assert budget.remaining_calls == 9

    def test_execute_without_budget_does_not_raise(self) -> None:
        """ToolExecutor without a budget (context.budget=None) runs the tool normally."""
        ctx = AgentContext(raw_payload=b"data")
        executor = ToolExecutor(context=ctx)
        result = executor.execute(lambda: "ok")
        assert result == "ok"

    def test_execute_without_context_does_not_raise(self) -> None:
        """ToolExecutor without any context runs the tool normally."""
        executor = ToolExecutor()
        result = executor.execute(lambda: "no-context")
        assert result == "no-context"

    def test_default_timeout_is_thirty_seconds(self) -> None:
        """ToolExecutor default timeout_seconds is 30.0."""
        executor = ToolExecutor()
        assert executor.timeout_seconds == 30.0


class TestTimeoutEnforcement:
    """Tests for per-call timeout via ThreadPoolExecutor."""

    def test_execute_raises_tool_timeout_error_on_slow_tool(self) -> None:
        """A tool that sleeps longer than timeout_seconds raises ToolTimeoutError."""

        def slow_tool() -> None:
            time.sleep(5)

        executor = ToolExecutor(timeout_seconds=0.05)
        with pytest.raises(ToolTimeoutError):
            executor.execute(slow_tool)

    def test_execute_completes_within_timeout(self) -> None:
        """A fast tool completes normally within the timeout window."""
        executor = ToolExecutor(timeout_seconds=5.0)
        result = executor.execute(lambda: "fast")
        assert result == "fast"

    def test_tool_timeout_error_is_raised_not_swallowed(self) -> None:
        """ToolTimeoutError propagates to the caller — not silently swallowed."""

        def stuck_tool() -> None:
            time.sleep(10)

        executor = ToolExecutor(timeout_seconds=0.05)
        with pytest.raises(ToolTimeoutError):
            executor.execute(stuck_tool)


class TestRecursionProtection:
    """Tests for RecursionError trap and ToolRecursionError conversion."""

    def test_execute_raises_tool_recursion_error_on_infinite_recursion(self) -> None:
        """A tool that causes RecursionError raises ToolRecursionError."""

        def recursive_bomb() -> None:
            return recursive_bomb()

        executor = ToolExecutor()
        with pytest.raises(ToolRecursionError):
            executor.execute(recursive_bomb)

    def test_tool_recursion_error_has_informative_message(self) -> None:
        """ToolRecursionError message identifies recursion as the cause."""

        def recursive_bomb() -> None:
            return recursive_bomb()

        executor = ToolExecutor()
        with pytest.raises(ToolRecursionError) as exc_info:
            executor.execute(recursive_bomb)
        assert "recursion" in str(exc_info.value).lower()


class TestBudgetEnforcement:
    """Tests for pre-execution budget checks."""

    def test_execute_blocked_on_exhausted_call_budget(self) -> None:
        """A pre-exhausted call budget raises BudgetExhaustedError before tool runs."""
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        ctx = AgentContext(raw_payload=b"data")
        ctx.budget = budget
        budget.record_call(tokens_used=0)  # exhaust the 1 allowed call

        called: list[bool] = []
        executor = ToolExecutor(context=ctx)
        with pytest.raises(BudgetExhaustedError):
            executor.execute(lambda: called.append(True))
        assert called == []  # tool was never invoked

    def test_execute_blocked_on_exhausted_token_budget(self) -> None:
        """A pre-exhausted token budget raises BudgetExhaustedError before tool runs."""
        budget = RequestBudget(max_calls=100, max_tokens=0)
        ctx = AgentContext(raw_payload=b"data")
        ctx.budget = budget
        executor = ToolExecutor(context=ctx)
        with pytest.raises(BudgetExhaustedError):
            executor.execute(lambda: None, token_cost=1)


class TestExceptionPropagation:
    """Tests that native tool exceptions are not wrapped or swallowed."""

    def test_tool_value_error_propagates_unchanged(self) -> None:
        """A ValueError raised by the tool propagates as-is."""

        def bad_tool() -> None:
            raise ValueError("bad input")

        executor = ToolExecutor()
        with pytest.raises(ValueError, match="bad input"):
            executor.execute(bad_tool)

    def test_tool_runtime_error_propagates_unchanged(self) -> None:
        """A RuntimeError raised by the tool propagates as-is."""

        def failing_tool() -> None:
            raise RuntimeError("tool failed")

        executor = ToolExecutor()
        with pytest.raises(RuntimeError, match="tool failed"):
            executor.execute(failing_tool)

    def test_tool_exception_does_not_record_budget(self) -> None:
        """budget.record_call is NOT called when the tool raises an exception."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        ctx = AgentContext(raw_payload=b"data")
        ctx.budget = budget
        executor = ToolExecutor(context=ctx)

        def bad_tool() -> None:
            raise ValueError("oops")

        with pytest.raises(ValueError):
            executor.execute(bad_tool, token_cost=500)

        # Budget unchanged — record_call was never called
        assert budget.remaining_tokens == 1000
        assert budget.remaining_calls == 10
