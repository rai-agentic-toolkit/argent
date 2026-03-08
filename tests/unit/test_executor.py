"""Tests for the ToolExecutor safe tool invocation wrapper.

All tests are async because ToolExecutor.execute() is an async method.
asyncio_mode = "auto" in pyproject.toml runs them without extra decorators.
"""

from __future__ import annotations

import concurrent.futures
import time

import pytest

from argent.budget.budget import RequestBudget
from argent.budget.exceptions import BudgetExhaustedError, ToolRecursionError, ToolTimeoutError
from argent.budget.executor import ToolExecutor


class TestBasicExecution:
    """Tests for normal (happy-path) tool invocation."""

    async def test_execute_returns_tool_result(self) -> None:
        """Normal tool invocation returns the tool's return value."""
        executor = ToolExecutor()
        result = await executor.execute(lambda: 42)
        assert result == 42

    async def test_execute_passes_args_and_kwargs(self) -> None:
        """execute() forwards *args and **kwargs to the tool."""
        executor = ToolExecutor()
        result = await executor.execute(lambda x, y=0: x + y, 3, y=4)
        assert result == 7

    async def test_execute_records_budget_on_success(self) -> None:
        """budget.record_call is called with the correct token_cost after success."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        executor = ToolExecutor(budget=budget)
        await executor.execute(lambda: None, token_cost=50)
        assert budget.remaining_tokens == 950
        assert budget.remaining_calls == 9

    async def test_execute_without_budget_does_not_raise(self) -> None:
        """ToolExecutor with budget=None runs the tool normally."""
        executor = ToolExecutor(budget=None)
        result = await executor.execute(lambda: "ok")
        assert result == "ok"

    async def test_execute_without_any_args_does_not_raise(self) -> None:
        """ToolExecutor with default constructor runs the tool normally."""
        executor = ToolExecutor()
        result = await executor.execute(lambda: "no-budget")
        assert result == "no-budget"

    async def test_default_timeout_is_thirty_seconds(self) -> None:
        """ToolExecutor default timeout_seconds is 30.0."""
        executor = ToolExecutor()
        assert executor.timeout_seconds == 30.0


class TestTimeoutEnforcement:
    """Tests for per-call timeout via asyncio.wait_for."""

    async def test_execute_raises_tool_timeout_error_on_slow_tool(self) -> None:
        """A tool that sleeps longer than timeout_seconds raises ToolTimeoutError."""

        def slow_tool() -> None:
            time.sleep(5)

        executor = ToolExecutor(timeout_seconds=0.05)
        with pytest.raises(ToolTimeoutError):
            await executor.execute(slow_tool)

    async def test_execute_completes_within_timeout(self) -> None:
        """A fast tool completes normally within the timeout window."""
        executor = ToolExecutor(timeout_seconds=5.0)
        result = await executor.execute(lambda: "fast")
        assert result == "fast"

    async def test_tool_timeout_error_is_raised_not_swallowed(self) -> None:
        """ToolTimeoutError propagates to the caller — not silently swallowed."""

        def stuck_tool() -> None:
            time.sleep(10)

        executor = ToolExecutor(timeout_seconds=0.05)
        with pytest.raises(ToolTimeoutError):
            await executor.execute(stuck_tool)


class TestRecursionProtection:
    """Tests for RecursionError trap and ToolRecursionError conversion."""

    async def test_execute_raises_tool_recursion_error_on_infinite_recursion(self) -> None:
        """A tool that causes RecursionError raises ToolRecursionError."""

        def recursive_bomb() -> None:
            return recursive_bomb()

        executor = ToolExecutor()
        with pytest.raises(ToolRecursionError):
            await executor.execute(recursive_bomb)

    async def test_tool_recursion_error_has_informative_message(self) -> None:
        """ToolRecursionError message identifies recursion as the cause."""

        def recursive_bomb() -> None:
            return recursive_bomb()

        executor = ToolExecutor()
        with pytest.raises(ToolRecursionError) as exc_info:
            await executor.execute(recursive_bomb)
        assert "recursion" in str(exc_info.value).lower()


class TestBudgetEnforcement:
    """Tests for pre-execution budget checks."""

    async def test_execute_blocked_on_exhausted_call_budget(self) -> None:
        """A pre-exhausted call budget raises BudgetExhaustedError before tool runs."""
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        budget.record_call(tokens_used=0)  # exhaust the 1 allowed call

        called: list[bool] = []
        executor = ToolExecutor(budget=budget)
        with pytest.raises(BudgetExhaustedError):
            await executor.execute(lambda: called.append(True))
        assert called == []  # tool was never invoked

    async def test_execute_blocked_on_exhausted_token_budget(self) -> None:
        """A pre-exhausted token budget raises BudgetExhaustedError before tool runs."""
        budget = RequestBudget(max_calls=100, max_tokens=0)

        called: list[bool] = []
        executor = ToolExecutor(budget=budget)
        with pytest.raises(BudgetExhaustedError):
            await executor.execute(lambda: called.append(True), token_cost=1)
        assert called == []  # tool was never invoked


class TestExceptionPropagation:
    """Tests that native tool exceptions are not wrapped or swallowed."""

    async def test_tool_value_error_propagates_unchanged(self) -> None:
        """A ValueError raised by the tool propagates as-is."""

        def bad_tool() -> None:
            raise ValueError("bad input")

        executor = ToolExecutor()
        with pytest.raises(ValueError, match="bad input"):
            await executor.execute(bad_tool)

    async def test_tool_runtime_error_propagates_unchanged(self) -> None:
        """A RuntimeError raised by the tool propagates as-is."""

        def failing_tool() -> None:
            raise RuntimeError("tool failed")

        executor = ToolExecutor()
        with pytest.raises(RuntimeError, match="tool failed"):
            await executor.execute(failing_tool)

    async def test_tool_exception_does_not_record_budget(self) -> None:
        """budget.record_call is NOT called when the tool raises an exception."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        executor = ToolExecutor(budget=budget)

        def bad_tool() -> None:
            raise ValueError("oops")

        with pytest.raises(ValueError):
            await executor.execute(bad_tool, token_cost=500)

        # Budget unchanged — record_call was never called
        assert budget.remaining_tokens == 1000
        assert budget.remaining_calls == 10


class TestCustomExecutor:
    """Tests for P6-T02: configurable thread pool Executor in ToolExecutor.

    CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
    until ToolExecutor gains an `executor` field.
    """

    async def test_executor_field_defaults_to_none(self) -> None:
        """ToolExecutor.executor defaults to None (process-default pool)."""
        executor = ToolExecutor()
        assert executor.executor is None

    async def test_custom_executor_is_used_and_returns_result(self) -> None:
        """ToolExecutor accepts a custom ThreadPoolExecutor and returns tool result."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            executor = ToolExecutor(executor=pool)
            result = await executor.execute(lambda: "from-custom-pool")
        assert result == "from-custom-pool"

    async def test_custom_executor_does_not_affect_timeout(self) -> None:
        """Timeout enforcement still works with a custom executor."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            executor = ToolExecutor(executor=pool, timeout_seconds=0.05)
            with pytest.raises(ToolTimeoutError):
                await executor.execute(lambda: time.sleep(5))

    async def test_custom_executor_with_budget_records_correctly(self) -> None:
        """Budget is recorded correctly when a custom executor is provided."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            executor = ToolExecutor(budget=budget, executor=pool)
            await executor.execute(lambda: None, token_cost=100)
        assert budget.remaining_tokens == 900
        assert budget.remaining_calls == 9

    async def test_none_executor_uses_default_pool(self) -> None:
        """ToolExecutor(executor=None) behaves identically to ToolExecutor()."""
        executor = ToolExecutor(executor=None)
        result = await executor.execute(lambda: "default-pool")
        assert result == "default-pool"
