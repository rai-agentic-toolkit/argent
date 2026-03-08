"""Safe tool execution wrapper — The Leash's invocation guard.

``ToolExecutor`` wraps native tool calls with three layers of protection:

1. **Budget pre-check**: refuses to run a tool if the attached budget is
   already exhausted (call or token count already at the limit), delegating
   all pre-call arithmetic to ``RequestBudget.check_precall()``.
2. **Timeout enforcement**: each call runs in a thread via
   ``asyncio.get_running_loop().run_in_executor()``; if it does not return
   within ``timeout_seconds`` a ``ToolTimeoutError`` is raised.
3. **Recursion trap**: ``RecursionError`` from the tool is caught and
   re-raised as ``ToolRecursionError`` with a descriptive message.

All other native exceptions propagate unchanged to the caller — the executor
does not swallow or wrap them.

Budget recording (``budget.record_call(token_cost)``) is performed **after**
successful tool completion.  If the tool raises, the budget is not charged.

Zero external dependencies (uses stdlib ``asyncio`` only).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    import concurrent.futures
    from collections.abc import Callable

    from argent.budget.budget import RequestBudget

from argent.budget.exceptions import ToolRecursionError, ToolTimeoutError

_DEFAULT_TIMEOUT: float = 30.0
_T = TypeVar("_T")


@dataclass
class ToolExecutor:
    """Safe async wrapper for synchronous tool invocations.

    Args:
        budget: Optional execution budget.  When provided,
            ``budget.check_precall()`` is consulted before each call and
            ``budget.record_call()`` is charged after a successful return.
            If ``None``, the executor operates without budget enforcement
            (timeout and recursion protection still apply).
        timeout_seconds: Maximum time a tool call may take before a
            ``ToolTimeoutError`` is raised.  Defaults to 30 seconds.
        executor: Optional ``concurrent.futures.Executor`` to use for running
            tools in a thread.  When ``None`` (default), the process-wide
            default thread pool is used (``run_in_executor(None, ...)``).
            Pass a dedicated ``ThreadPoolExecutor`` for concurrent-agent
            deployments that need thread pool isolation.  The caller owns
            the executor's lifecycle — ``ToolExecutor`` does not shut it down.
    """

    budget: RequestBudget | None = field(default=None)
    timeout_seconds: float = field(default=_DEFAULT_TIMEOUT)
    executor: concurrent.futures.Executor | None = field(default=None)

    async def execute(
        self,
        tool: Callable[..., _T],
        /,
        *args: Any,
        token_cost: int = 0,
        **kwargs: Any,
    ) -> _T:
        """Invoke *tool* with protection against timeouts, recursion, and budget overrun.

        Args:
            tool: Callable to invoke (runs in a thread-pool thread).
            *args: Positional arguments forwarded to *tool*.
            token_cost: Token units to charge against the budget after a
                successful call.  Ignored if no budget is attached.
            **kwargs: Keyword arguments forwarded to *tool*.

        Returns:
            Whatever *tool* returns.

        Raises:
            BudgetExhaustedError: If the attached budget is already exhausted
                before invocation (via ``check_precall``), or if
                ``budget.record_call()`` raises after the tool returns.
            ToolTimeoutError: If the tool does not complete within
                ``timeout_seconds``.
            ToolRecursionError: If the tool triggers a ``RecursionError``.
            Exception: Any other exception raised by *tool* propagates as-is.
        """
        # Pre-call budget check: refuse if already (or would be) exhausted
        if self.budget is not None:
            self.budget.check_precall(token_cost)

        # Execute tool in a thread so the event loop is never blocked.
        # self.executor=None uses the process-wide default pool (unchanged default
        # behaviour); a custom Executor gives concurrent deployments thread isolation.
        loop = asyncio.get_running_loop()
        try:
            result: _T = await asyncio.wait_for(
                loop.run_in_executor(self.executor, lambda: tool(*args, **kwargs)),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as err:
            raise ToolTimeoutError(self.timeout_seconds) from err
        except RecursionError as err:
            raise ToolRecursionError() from err

        # Post-call: record budget usage (raises BudgetExhaustedError if now over limit)
        if self.budget is not None:
            self.budget.record_call(tokens_used=token_cost)

        return result
