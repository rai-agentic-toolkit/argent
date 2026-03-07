"""Tests for ContextBudgetCalculator.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/trimmer/calculator.py exists.
"""

from __future__ import annotations

from argent.budget.budget import RequestBudget
from argent.trimmer.calculator import ContextBudgetCalculator


class TestContextBudgetCalculatorConstruction:
    """Tests for ContextBudgetCalculator instantiation."""

    def test_default_chars_per_token(self) -> None:
        """Default chars_per_token is 4.0."""
        calc = ContextBudgetCalculator(context_window_tokens=4096)
        assert calc._chars_per_token == 4.0

    def test_custom_chars_per_token(self) -> None:
        """Custom chars_per_token is stored."""
        calc = ContextBudgetCalculator(context_window_tokens=4096, chars_per_token=3.5)
        assert calc._chars_per_token == 3.5


class TestContextBudgetCalculatorCompute:
    """Tests for ContextBudgetCalculator.compute(budget)."""

    def test_compute_returns_int(self) -> None:
        """compute() always returns an int."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        calc = ContextBudgetCalculator(context_window_tokens=4096)
        result = calc.compute(budget)
        assert isinstance(result, int)

    def test_compute_correct_formula(self) -> None:
        """compute() returns remaining_tokens * chars_per_token as int."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        calc = ContextBudgetCalculator(context_window_tokens=4096, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 4000  # 1000 * 4.0

    def test_compute_reflects_remaining_tokens(self) -> None:
        """compute() uses remaining_tokens, not max_tokens."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        budget.record_call(tokens_used=200)
        calc = ContextBudgetCalculator(context_window_tokens=4096, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 3200  # 800 remaining * 4.0

    def test_compute_minimum_256_at_zero_tokens(self) -> None:
        """compute() returns at least 256 even when remaining_tokens is 0."""
        budget = RequestBudget(max_calls=10, max_tokens=100)
        # Exhaust all tokens
        budget.record_call(tokens_used=100)
        calc = ContextBudgetCalculator(context_window_tokens=4096)
        result = calc.compute(budget)
        assert result == 256

    def test_compute_minimum_256_enforced(self) -> None:
        """compute() never returns less than 256."""
        budget = RequestBudget(max_calls=10, max_tokens=10)
        calc = ContextBudgetCalculator(context_window_tokens=4096, chars_per_token=4.0)
        result = calc.compute(budget)
        # 10 * 4.0 = 40, but minimum is 256
        assert result == 256

    def test_compute_custom_chars_per_token(self) -> None:
        """chars_per_token multiplier is used in the formula."""
        budget = RequestBudget(max_calls=10, max_tokens=500)
        calc = ContextBudgetCalculator(context_window_tokens=4096, chars_per_token=3.0)
        result = calc.compute(budget)
        assert result == 1500  # 500 * 3.0

    def test_compute_large_budget(self) -> None:
        """compute() handles large token budgets correctly."""
        budget = RequestBudget(max_calls=100, max_tokens=100_000)
        calc = ContextBudgetCalculator(context_window_tokens=128_000, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 400_000
