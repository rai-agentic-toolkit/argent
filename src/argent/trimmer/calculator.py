"""Dynamic budget calculator for the egress trimming stage.

Reads ``RequestBudget.remaining_tokens`` to compute the maximum character
allowance the trimmer may produce.  The formula is intentionally simple:
``max(0, remaining_tokens - reserved_tokens) * chars_per_token``, subject to
a floor of 256 chars so the trimmer is never starved to zero output.

The 4.0 chars-per-token default is a conservative approximation that holds
well for English text across GPT-* and Claude model families.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argent.budget.budget import RequestBudget

# 256 chars is the minimum legible error message / JSON fragment an LLM can act on;
# below this threshold the trimmer output would be too truncated to be useful.
_MIN_CHARS: int = 256


class ContextBudgetCalculator:
    """Compute the egress trimmer's ``max_chars`` from the remaining token budget.

    Args:
        reserved_tokens: Tokens to hold back from ``budget.remaining_tokens``
            before computing the character budget.  Use this to reserve
            headroom for the model's own completion so the trimmer does not
            consume the entire available context.  Defaults to ``0``.
        chars_per_token: Approximate characters per token.  Defaults to
            ``4.0``, a reasonable estimate for English prose and code.

    Example::

        calc = ContextBudgetCalculator(reserved_tokens=500)
        max_chars = calc.compute(budget)  # (remaining_tokens - 500) * 4.0
    """

    def __init__(
        self,
        reserved_tokens: int = 0,
        chars_per_token: float = 4.0,
    ) -> None:
        self._reserved_tokens = reserved_tokens
        self._chars_per_token = chars_per_token

    def compute(self, budget: RequestBudget) -> int:
        """Return the maximum character allowance for the current egress step.

        Formula: ``int(max(0, budget.remaining_tokens - reserved_tokens) *
        chars_per_token)``, floored at :data:`_MIN_CHARS` (256) so the
        trimmer always has a non-zero budget even when the token budget is
        exhausted or fully reserved.

        Args:
            budget: The active ``RequestBudget`` for this pipeline run.

        Returns:
            The maximum number of characters the trimmer may emit.
        """
        raw = int(max(0, budget.remaining_tokens - self._reserved_tokens) * self._chars_per_token)
        return max(raw, _MIN_CHARS)
