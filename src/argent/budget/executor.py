"""Safe tool execution wrapper — The Leash's invocation guard.

``ToolExecutor`` wraps native tool calls with three layers of protection:

1. **Budget pre-check**: refuses to run a tool if the attached budget is
   already exhausted (call or token count already at the limit).
2. **Timeout enforcement**: each call runs in a ``ThreadPoolExecutor`` thread;
   if it does not return within ``timeout_seconds`` a ``ToolTimeoutError`` is
   raised and the thread is abandoned.
3. **Recursion trap**: ``RecursionError`` from the tool is caught and re-raised
   as ``ToolRecursionError`` with a descriptive message.

All other native exceptions propagate unchanged to the caller — the executor
does not swallow or wrap them.

Budget recording (``context.budget.record_call(token_cost)``) is performed
**after** successful tool completion.  If the tool raises, the budget is not
charged.

Zero external dependencies (uses stdlib ``concurrent.futures`` only).
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from argent.budget.exceptions import BudgetExhaustedError, ToolRecursionError, ToolTimeoutError

if TYPE_CHECKING:
    from argent.pipeline.context import AgentContext

_DEFAULT_TIMEOUT: float = 30.0


@dataclass
class ToolExecutor:
    """Safe wrapper for synchronous tool invocations.

    Args:
        context: Optional agent context.  When provided, ``context.budget``
            is consulted before each call and charged after a successful
            return.  If ``None`` or ``context.budget`` is ``None``, the
            executor operates without budget enforcement (timeout and
            recursion protection still apply).
        timeout_seconds: Maximum time a tool call may take before a
            ``ToolTimeoutError`` is raised.  Defaults to 30 seconds.
    """

    context: AgentContext | None = field(default=None)
    timeout_seconds: float = field(default=_DEFAULT_TIMEOUT)

    def execute(
        self,
        tool: Callable[..., Any],
        /,
        *args: Any,
        token_cost: int = 0,
        **kwargs: Any,
    ) -> Any:
        """Invoke *tool* with protection against timeouts, recursion, and budget overrun.

        Args:
            tool: Callable to invoke.
            *args: Positional arguments forwarded to *tool*.
            token_cost: Token units to charge against the budget after a
                successful call.  Ignored if no budget is attached.
            **kwargs: Keyword arguments forwarded to *tool*.

        Returns:
            Whatever *tool* returns.

        Raises:
            BudgetExhaustedError: If the attached budget is already exhausted
                before invocation, or if ``budget.record_call()`` raises after
                the tool returns.
            ToolTimeoutError: If the tool does not complete within
                ``timeout_seconds``.
            ToolRecursionError: If the tool triggers a ``RecursionError``.
            Exception: Any other exception raised by *tool* propagates as-is.
        """
        budget = self.context.budget if self.context is not None else None

        # Pre-call budget check: refuse if already exhausted
        if budget is not None and (budget.remaining_calls <= 0 or budget.remaining_tokens < 0):
            raise BudgetExhaustedError(
                limit_kind="calls" if budget.remaining_calls <= 0 else "tokens",
                current=budget.max_calls - budget.remaining_calls,
                limit=budget.max_calls if budget.remaining_calls <= 0 else budget.max_tokens,
            )

        # Execute tool in a thread for timeout enforcement
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(tool, *args, **kwargs)
            try:
                result = future.result(timeout=self.timeout_seconds)
            except concurrent.futures.TimeoutError as err:
                raise ToolTimeoutError(self.timeout_seconds) from err
            except RecursionError as err:
                raise ToolRecursionError() from err

        # Post-call: record budget usage (raises BudgetExhaustedError if now over limit)
        if budget is not None:
            budget.record_call(tokens_used=token_cost)

        return result
