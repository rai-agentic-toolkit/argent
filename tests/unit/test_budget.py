"""Tests for stateful token and call budget enforcement.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/budget/budget.py exists.
"""

from __future__ import annotations

import pytest

from argent.budget.budget import RequestBudget
from argent.budget.exceptions import BudgetExhaustedError
from argent.pipeline.context import AgentContext


class TestRequestBudgetConstruction:
    """Tests for RequestBudget construction and initial state."""

    def test_construction_with_limits(self) -> None:
        """RequestBudget is created with max_calls and max_tokens."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        assert isinstance(budget, RequestBudget)

    def test_remaining_calls_starts_at_max(self) -> None:
        """remaining_calls equals max_calls before any calls are recorded."""
        budget = RequestBudget(max_calls=5, max_tokens=500)
        assert budget.remaining_calls == 5

    def test_remaining_tokens_starts_at_max(self) -> None:
        """remaining_tokens equals max_tokens before any calls are recorded."""
        budget = RequestBudget(max_calls=5, max_tokens=500)
        assert budget.remaining_tokens == 500

    def test_no_reset_method(self) -> None:
        """RequestBudget has no reset() method — budget is immutable after construction."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        assert not hasattr(budget, "reset")


class TestRecordCall:
    """Tests for record_call counter increments."""

    def test_record_call_decrements_remaining_calls(self) -> None:
        """record_call(0) decrements remaining_calls by 1."""
        budget = RequestBudget(max_calls=5, max_tokens=500)
        budget.record_call(tokens_used=0)
        assert budget.remaining_calls == 4

    def test_record_call_decrements_remaining_tokens(self) -> None:
        """record_call(n) decrements remaining_tokens by n."""
        budget = RequestBudget(max_calls=5, max_tokens=500)
        budget.record_call(tokens_used=100)
        assert budget.remaining_tokens == 400

    def test_multiple_calls_accumulate(self) -> None:
        """Multiple record_call() invocations accumulate correctly."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        budget.record_call(tokens_used=200)
        budget.record_call(tokens_used=300)
        assert budget.remaining_calls == 8
        assert budget.remaining_tokens == 500

    def test_call_at_exact_limit_does_not_raise(self) -> None:
        """record_call that brings counts to exactly the limit does not raise."""
        budget = RequestBudget(max_calls=3, max_tokens=300)
        budget.record_call(tokens_used=100)
        budget.record_call(tokens_used=100)
        budget.record_call(tokens_used=100)  # exactly at limit — must not raise
        assert budget.remaining_calls == 0
        assert budget.remaining_tokens == 0


class TestBudgetExhaustion:
    """Tests for BudgetExhaustedError when limits are crossed."""

    def test_raises_on_max_calls_exceeded(self) -> None:
        """BudgetExhaustedError raised when call count exceeds max_calls."""
        budget = RequestBudget(max_calls=2, max_tokens=1000)
        budget.record_call(tokens_used=0)
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError):
            budget.record_call(tokens_used=0)  # 3rd call exceeds limit of 2

    def test_raises_on_max_tokens_exceeded(self) -> None:
        """BudgetExhaustedError raised when token count exceeds max_tokens."""
        budget = RequestBudget(max_calls=100, max_tokens=100)
        with pytest.raises(BudgetExhaustedError):
            budget.record_call(tokens_used=101)  # over token limit

    def test_error_identifies_calls_limit(self) -> None:
        """BudgetExhaustedError carries limit_kind='calls' when call limit hit."""
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            budget.record_call(tokens_used=0)
        assert exc_info.value.limit_kind == "calls"

    def test_error_identifies_tokens_limit(self) -> None:
        """BudgetExhaustedError carries limit_kind='tokens' when token limit hit."""
        budget = RequestBudget(max_calls=100, max_tokens=50)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            budget.record_call(tokens_used=51)
        assert exc_info.value.limit_kind == "tokens"

    def test_error_carries_current_and_max(self) -> None:
        """BudgetExhaustedError exposes current count and configured max."""
        budget = RequestBudget(max_calls=2, max_tokens=1000)
        budget.record_call(tokens_used=0)
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            budget.record_call(tokens_used=0)
        err = exc_info.value
        assert err.current == 3  # 3rd call attempted
        assert err.limit == 2

    def test_error_message_is_informative(self) -> None:
        """BudgetExhaustedError message includes limit kind and counts."""
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError) as exc_info:
            budget.record_call(tokens_used=0)
        msg = str(exc_info.value)
        assert "calls" in msg or "call" in msg


class TestExhaustionCallbacks:
    """Tests for on_exhausted callback registration and firing."""

    def test_callback_fires_on_call_exhaustion(self) -> None:
        """Registered callback is invoked when call limit is crossed."""
        fired: list[RequestBudget] = []
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        budget.on_exhausted(fired.append)
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError):
            budget.record_call(tokens_used=0)
        assert len(fired) == 1
        assert fired[0] is budget

    def test_callback_fires_on_token_exhaustion(self) -> None:
        """Registered callback is invoked when token limit is crossed."""
        fired: list[RequestBudget] = []
        budget = RequestBudget(max_calls=100, max_tokens=10)
        budget.on_exhausted(fired.append)
        with pytest.raises(BudgetExhaustedError):
            budget.record_call(tokens_used=11)
        assert len(fired) == 1

    def test_multiple_callbacks_all_fire(self) -> None:
        """Multiple registered callbacks all fire on exhaustion."""
        results: list[int] = []
        budget = RequestBudget(max_calls=1, max_tokens=1000)
        budget.on_exhausted(lambda _: results.append(1))
        budget.on_exhausted(lambda _: results.append(2))
        budget.on_exhausted(lambda _: results.append(3))
        budget.record_call(tokens_used=0)
        with pytest.raises(BudgetExhaustedError):
            budget.record_call(tokens_used=0)
        assert results == [1, 2, 3]

    def test_callback_not_called_on_successful_record(self) -> None:
        """Callback is not invoked when a call is recorded within limits."""
        fired: list[bool] = []
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        budget.on_exhausted(lambda _: fired.append(True))
        budget.record_call(tokens_used=100)
        assert fired == []


class TestAgentContextBudgetField:
    """Tests for the budget field added to AgentContext."""

    def test_agent_context_has_budget_field(self) -> None:
        """AgentContext exposes a budget attribute."""
        ctx = AgentContext(raw_payload=b"data")
        assert hasattr(ctx, "budget")

    def test_budget_defaults_to_none(self) -> None:
        """AgentContext.budget defaults to None (budget is optional)."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.budget is None

    def test_budget_can_be_set(self) -> None:
        """AgentContext.budget can be assigned a RequestBudget instance."""
        ctx = AgentContext(raw_payload=b"data")
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        ctx.budget = budget
        assert ctx.budget is budget
