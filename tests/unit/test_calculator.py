"""Tests for ContextBudgetCalculator.

P8-T01: reserved_tokens replaces context_window_tokens.
"""

from __future__ import annotations

import pytest

from argent.budget.budget import RequestBudget
from argent.trimmer.calculator import ContextBudgetCalculator


class TestContextBudgetCalculatorConstruction:
    """Tests for ContextBudgetCalculator instantiation."""

    def test_default_chars_per_token(self) -> None:
        """Default chars_per_token is 4.0."""
        calc = ContextBudgetCalculator()
        assert calc._chars_per_token == 4.0

    def test_custom_chars_per_token(self) -> None:
        """Custom chars_per_token is stored."""
        calc = ContextBudgetCalculator(chars_per_token=3.5)
        assert calc._chars_per_token == 3.5

    def test_default_reserved_tokens_is_zero(self) -> None:
        """reserved_tokens defaults to 0."""
        calc = ContextBudgetCalculator()
        assert calc._reserved_tokens == 0

    def test_custom_reserved_tokens_stored(self) -> None:
        """reserved_tokens is stored when provided."""
        calc = ContextBudgetCalculator(reserved_tokens=500)
        assert calc._reserved_tokens == 500

    def test_context_window_tokens_no_longer_exists(self) -> None:
        """Passing context_window_tokens raises TypeError (removed in v0.2.0)."""
        with pytest.raises(TypeError):
            ContextBudgetCalculator(context_window_tokens=4096)  # type: ignore[call-arg]


class TestContextBudgetCalculatorCompute:
    """Tests for ContextBudgetCalculator.compute(budget)."""

    def test_compute_returns_int(self) -> None:
        """compute() always returns an int."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        calc = ContextBudgetCalculator()
        result = calc.compute(budget)
        assert isinstance(result, int)

    def test_compute_correct_formula_no_reservation(self) -> None:
        """compute() returns remaining_tokens * chars_per_token when reserved_tokens=0."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        calc = ContextBudgetCalculator(chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 4000  # 1000 * 4.0

    def test_compute_subtracts_reserved_tokens(self) -> None:
        """compute() deducts reserved_tokens before multiplying."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        calc = ContextBudgetCalculator(reserved_tokens=200, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 3200  # (1000 - 200) * 4.0

    def test_compute_readme_example(self) -> None:
        """The README example ContextBudgetCalculator(reserved_tokens=500) works."""
        budget = RequestBudget(max_calls=10, max_tokens=4000)
        calc = ContextBudgetCalculator(reserved_tokens=500)
        result = calc.compute(budget)
        assert result == int((4000 - 500) * 4.0)  # 14000

    def test_compute_reflects_remaining_tokens(self) -> None:
        """compute() uses remaining_tokens, not max_tokens."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        budget.record_call(tokens_used=200)
        calc = ContextBudgetCalculator(chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 3200  # 800 remaining * 4.0

    def test_compute_reserved_tokens_exceeds_remaining_floors_to_min(self) -> None:
        """When reserved_tokens >= remaining_tokens, result is the 256-char floor."""
        budget = RequestBudget(max_calls=10, max_tokens=100)
        calc = ContextBudgetCalculator(reserved_tokens=500, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 256  # max(0, 100-500)*4 = 0, floored at 256

    def test_compute_minimum_256_at_zero_tokens(self) -> None:
        """compute() returns at least 256 even when remaining_tokens is 0."""
        budget = RequestBudget(max_calls=10, max_tokens=100)
        budget.record_call(tokens_used=100)
        calc = ContextBudgetCalculator()
        result = calc.compute(budget)
        assert result == 256

    def test_compute_minimum_256_enforced(self) -> None:
        """compute() never returns less than 256."""
        budget = RequestBudget(max_calls=10, max_tokens=10)
        calc = ContextBudgetCalculator(chars_per_token=4.0)
        result = calc.compute(budget)
        # 10 * 4.0 = 40, but minimum is 256
        assert result == 256

    def test_compute_custom_chars_per_token(self) -> None:
        """chars_per_token multiplier is used in the formula."""
        budget = RequestBudget(max_calls=10, max_tokens=500)
        calc = ContextBudgetCalculator(chars_per_token=3.0)
        result = calc.compute(budget)
        assert result == 1500  # 500 * 3.0

    def test_compute_large_budget(self) -> None:
        """compute() handles large token budgets correctly."""
        budget = RequestBudget(max_calls=100, max_tokens=100_000)
        calc = ContextBudgetCalculator(chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == 400_000

    def test_compute_reserved_and_depleted_budget(self) -> None:
        """reserved_tokens and partial token spend interact correctly."""
        budget = RequestBudget(max_calls=10, max_tokens=1000)
        budget.record_call(tokens_used=300)  # 700 remaining
        calc = ContextBudgetCalculator(reserved_tokens=200, chars_per_token=4.0)
        result = calc.compute(budget)
        assert result == int((700 - 200) * 4.0)  # 2000
