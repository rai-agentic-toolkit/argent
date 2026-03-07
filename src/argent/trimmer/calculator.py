"""Dynamic budget calculator for the egress trimming stage.

Reads ``RequestBudget.remaining_tokens`` to compute the maximum character
allowance the trimmer may produce.  The formula is intentionally simple:
``remaining_tokens * chars_per_token``, subject to a floor of 256 chars
so the trimmer is never starved to zero output.

A ``tiktoken``-based implementation could provide per-model accuracy but
is deliberately deferred to Phase 6 (optional extra).  The 4.0
chars-per-token default is a conservative approximation that holds well
for English text across GPT-* and Claude model families.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argent.budget.budget import RequestBudget

_MIN_CHARS: int = 256


class ContextBudgetCalculator:
    """Compute the egress trimmer's ``max_chars`` from the remaining token budget.

    Args:
        context_window_tokens: The model's full context window size in tokens.
            Informational; may be used by future tiktoken integration.
        chars_per_token: Approximate characters per token.  Defaults to
            ``4.0``, a reasonable estimate for English prose and code.
    """

    def __init__(
        self,
        context_window_tokens: int,
        chars_per_token: float = 4.0,
    ) -> None:
        self._context_window_tokens = context_window_tokens
        self._chars_per_token = chars_per_token

    def compute(self, budget: RequestBudget) -> int:
        """Return the maximum character allowance for the current egress step.

        Formula: ``int(budget.remaining_tokens * chars_per_token)``, floored
        at :data:`_MIN_CHARS` (256) so the trimmer always has a non-zero
        budget even when the token budget is exhausted.

        Args:
            budget: The active ``RequestBudget`` for this pipeline run.

        Returns:
            The maximum number of characters the trimmer may emit.
        """
        raw = int(budget.remaining_tokens * self._chars_per_token)
        return max(raw, _MIN_CHARS)
