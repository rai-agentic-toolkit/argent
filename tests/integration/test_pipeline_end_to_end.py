"""End-to-end integration tests for the ARG middleware pipeline.

MVP Definition of Done (REQUIREMENTS.md §6): validates that all five Epic
components compose correctly under realistic adversarial and happy-path scenarios.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL until all
Epics are assembled and the public API surface is wired in P5-T04.
"""

import json
import time

import pytest

from argent.budget.budget import RequestBudget
from argent.budget.exceptions import BudgetExhaustedError, ToolTimeoutError
from argent.budget.executor import ToolExecutor
from argent.ingress.exceptions import PayloadTooLargeError
from argent.ingress.parser import SinglePassParser
from argent.ingress.validators import ByteSizeValidator
from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline
from argent.security.exceptions import SecurityViolationError
from argent.security.sql_validator import SqlAstValidator


class TestOversizedPayload:
    """Test 1: ByteSizeValidator rejects oversized payloads with HALTED state."""

    async def test_oversized_payload_halts_pipeline(self) -> None:
        """A payload exceeding max_bytes raises PayloadTooLargeError and sets HALTED."""
        validator = ByteSizeValidator(max_bytes=100)
        pipeline = Pipeline(ingress=[validator])
        ctx = AgentContext(raw_payload=b"x" * 200)

        with pytest.raises(PayloadTooLargeError):
            await pipeline.run(ctx)

        assert ctx.execution_state == ExecutionState.HALTED

    async def test_payload_within_limit_passes_through(self) -> None:
        """A payload within max_bytes passes ByteSizeValidator without error."""
        validator = ByteSizeValidator(max_bytes=1024)
        pipeline = Pipeline(ingress=[validator])
        ctx = AgentContext(raw_payload=b"small")
        result = await pipeline.run(ctx)
        assert result.execution_state == ExecutionState.COMPLETE


class TestSqlInjectionBlock:
    """Test 2: SqlAstValidator blocks destructive SQL payloads."""

    async def test_sql_injection_raises_security_violation(self) -> None:
        """DROP TABLE payload blocked by SqlAstValidator; exception propagates cleanly."""
        sql_validator = SqlAstValidator()

        async def inject_sql(ctx: AgentContext) -> None:
            ctx.parsed_ast = "DROP TABLE users"

        pipeline = Pipeline(
            ingress=[inject_sql],
            security_validators=[sql_validator],
        )

        with pytest.raises(SecurityViolationError):
            await pipeline.run(AgentContext(raw_payload=b"DROP TABLE users"))

    async def test_safe_sql_passes_validation(self) -> None:
        """A SELECT statement passes SqlAstValidator without error."""
        sql_validator = SqlAstValidator()

        async def set_sql(ctx: AgentContext) -> None:
            ctx.parsed_ast = "SELECT id FROM users"

        pipeline = Pipeline(
            ingress=[set_sql],
            security_validators=[sql_validator],
        )
        ctx = AgentContext(raw_payload=b"SELECT id FROM users")
        result = await pipeline.run(ctx)
        assert result.execution_state == ExecutionState.COMPLETE


class TestInfiniteLoopToolTimeout:
    """Test 3: ToolExecutor raises ToolTimeoutError for a blocking tool; budget not charged."""

    async def test_infinite_loop_tool_raises_timeout(self) -> None:
        """A tool that sleeps past the timeout raises ToolTimeoutError."""
        budget = RequestBudget(max_calls=10, max_tokens=10_000)
        executor = ToolExecutor(budget=budget, timeout_seconds=0.1)

        calls_before = budget.remaining_calls
        with pytest.raises(ToolTimeoutError):
            await executor.execute(time.sleep, 5)

        # Budget must not be charged on timeout
        assert budget.remaining_calls == calls_before

    async def test_fast_tool_does_not_timeout(self) -> None:
        """A tool completing within the timeout does not raise ToolTimeoutError."""
        budget = RequestBudget(max_calls=5, max_tokens=1000)
        executor = ToolExecutor(budget=budget, timeout_seconds=5.0)
        result = await executor.execute(lambda: "ok", token_cost=10)
        assert result == "ok"
        assert budget.max_calls - budget.remaining_calls == 1


class TestBudgetExhaustion:
    """Test 4: Budget exhaustion blocks subsequent calls before the tool runs."""

    async def test_budget_exhaustion_blocks_second_call(self) -> None:
        """After max_calls=1 is reached, the second call raises BudgetExhaustedError."""
        budget = RequestBudget(max_calls=1, max_tokens=10_000)
        executor = ToolExecutor(budget=budget, timeout_seconds=5.0)

        # First call succeeds
        await executor.execute(lambda: None, token_cost=10)
        assert budget.max_calls - budget.remaining_calls == 1

        # Second call must be blocked pre-execution
        with pytest.raises(BudgetExhaustedError) as exc_info:
            await executor.execute(lambda: None, token_cost=10)
        assert exc_info.value.limit_kind == "calls"
        assert (
            budget.max_calls - budget.remaining_calls == 1
        )  # budget not incremented by failed pre-check

    async def test_token_budget_exhaustion_blocks_call(self) -> None:
        """Token budget exhaustion raises BudgetExhaustedError before tool runs."""
        budget = RequestBudget(max_calls=100, max_tokens=50)
        executor = ToolExecutor(budget=budget, timeout_seconds=5.0)

        # First call spends all tokens
        await executor.execute(lambda: None, token_cost=50)

        # Next call would exceed token budget
        with pytest.raises(BudgetExhaustedError) as exc_info:
            await executor.execute(lambda: None, token_cost=1)
        assert exc_info.value.limit_kind == "tokens"


class TestHappyPathFullPipeline:
    """Test 5: Full pipeline happy path — all components assembled, COMPLETE state."""

    async def test_happy_path_full_pipeline_completes(self) -> None:
        """Valid JSON payload passes all components; execution_state is COMPLETE."""
        budget = RequestBudget(max_calls=5, max_tokens=1_000)
        executor = ToolExecutor(budget=budget, timeout_seconds=5.0)
        tool_results: list[object] = []

        async def run_tool(ctx: AgentContext) -> None:
            result = await executor.execute(lambda: {"status": "ok"}, token_cost=10)
            tool_results.append(result)

        pipeline = Pipeline(
            ingress=[ByteSizeValidator(max_bytes=4096), SinglePassParser()],
            execution=[run_tool],
        )

        payload = json.dumps({"query": "SELECT 1"}).encode()
        ctx = AgentContext(raw_payload=payload)
        result = await pipeline.run(ctx)

        assert result is ctx
        assert ctx.execution_state == ExecutionState.COMPLETE
        assert isinstance(ctx.parsed_ast, dict)
        assert ctx.parsed_ast == {"query": "SELECT 1"}
        assert tool_results == [{"status": "ok"}]
        assert budget.max_calls - budget.remaining_calls == 1

    async def test_happy_path_with_security_validator(self) -> None:
        """Full pipeline with SqlAstValidator passes a safe SELECT payload end-to-end."""

        sql_validator = SqlAstValidator()
        budget = RequestBudget(max_calls=5, max_tokens=1_000)
        executor = ToolExecutor(budget=budget, timeout_seconds=5.0)

        async def run_tool(ctx: AgentContext) -> None:
            await executor.execute(lambda: None, token_cost=5)

        pipeline = Pipeline(
            ingress=[ByteSizeValidator(max_bytes=4096), SinglePassParser()],
            security_validators=[sql_validator],
            execution=[run_tool],
        )

        # Plain SQL string as payload — parser will store it as plaintext
        ctx = AgentContext(raw_payload=b"SELECT id FROM users")
        result = await pipeline.run(ctx)

        assert result.execution_state == ExecutionState.COMPLETE
