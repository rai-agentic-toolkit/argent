"""Stateful execution budget enforcement — The Leash's call and token counter.

``RequestBudget`` maintains hard counters for tool calls and tokens consumed
within a single agent execution.  Both limits are absolute and non-resetable
(Business Rule BR-01): once either counter exceeds its configured maximum, a
``BudgetExhaustedError`` is raised and optional exhaustion callbacks are fired.

Zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from argent.budget.exceptions import BudgetExhaustedError

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class RequestBudget:
    """Stateful token and call budget enforcer.

    Args:
        max_calls: Maximum number of tool calls allowed in this execution.
        max_tokens: Maximum cumulative token spend allowed in this execution.

    Raises:
        BudgetExhaustedError: From :meth:`record_call` when either limit is
            exceeded after incrementing.  Both counters continue to reflect
            the violating values so callers can inspect the overage.
    """

    max_calls: int
    max_tokens: int
    _call_count: int = field(default=0, init=False, repr=False)
    _token_count: int = field(default=0, init=False, repr=False)
    _callbacks: list[Callable[[RequestBudget], None]] = field(
        default_factory=list, init=False, repr=False
    )

    @property
    def remaining_calls(self) -> int:
        """Remaining call budget (may be negative after exhaustion)."""
        return self.max_calls - self._call_count

    @property
    def remaining_tokens(self) -> int:
        """Remaining token budget (may be negative after exhaustion)."""
        return self.max_tokens - self._token_count

    def on_exhausted(self, fn: Callable[[RequestBudget], None]) -> None:
        """Register a callback to fire when either budget limit is crossed.

        Args:
            fn: Callable that receives this ``RequestBudget`` instance as its
                only argument.  All registered callbacks are invoked in
                registration order immediately before the
                ``BudgetExhaustedError`` is raised.
        """
        self._callbacks.append(fn)

    def record_call(self, tokens_used: int) -> None:
        """Increment both counters and enforce limits.

        Increments ``_call_count`` by 1 and ``_token_count`` by
        ``tokens_used``.  If either counter now exceeds its configured
        maximum, all registered callbacks are invoked and a
        ``BudgetExhaustedError`` is raised.

        The call limit is checked first; if both are violated the call-count
        error takes priority.

        Args:
            tokens_used: Number of tokens to add to the running total.

        Raises:
            BudgetExhaustedError: If ``_call_count > max_calls`` or
                ``_token_count > max_tokens`` after incrementing.
        """
        self._call_count += 1
        self._token_count += tokens_used

        if self._call_count > self.max_calls:
            self._fire_callbacks()
            raise BudgetExhaustedError(
                limit_kind="calls",
                current=self._call_count,
                limit=self.max_calls,
            )

        if self._token_count > self.max_tokens:
            self._fire_callbacks()
            raise BudgetExhaustedError(
                limit_kind="tokens",
                current=self._token_count,
                limit=self.max_tokens,
            )

    def check_precall(self, token_cost: int) -> None:
        """Raise BudgetExhaustedError if the next call would exceed either limit.

        Evaluates both counters *before* incrementing them — does **not**
        modify any counter.  Call :meth:`record_call` after the tool returns
        successfully to commit the charge.

        The call limit is checked first; if both would be violated the
        call-count error takes priority (mirrors :meth:`record_call` ordering).

        Args:
            token_cost: Token units that would be charged post-call.

        Raises:
            BudgetExhaustedError: If ``remaining_calls <= 0`` (one more call
                would push the call counter past ``max_calls``) or if
                ``token_cost > remaining_tokens`` (the projected token total
                would exceed ``max_tokens``).
        """
        if self.remaining_calls <= 0:
            raise BudgetExhaustedError(
                limit_kind="calls",
                current=self._call_count + 1,
                limit=self.max_calls,
            )
        if token_cost > self.remaining_tokens:
            raise BudgetExhaustedError(
                limit_kind="tokens",
                current=self._token_count + token_cost,
                limit=self.max_tokens,
            )

    def _fire_callbacks(self) -> None:
        """Invoke all registered exhaustion callbacks in registration order."""
        for cb in self._callbacks:
            cb(self)
