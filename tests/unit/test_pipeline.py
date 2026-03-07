"""Tests for the four-stage async middleware Pipeline.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/pipeline/pipeline.py exists.
"""

import pytest

from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline


async def _noop(ctx: AgentContext) -> None:
    """Async no-op middleware for use in tests that only need a placeholder."""


class TestPipelineInstantiation:
    """Tests for Pipeline construction."""

    async def test_empty_pipeline_is_valid(self) -> None:
        """Pipeline can be constructed with no middleware in any stage."""
        pipeline = Pipeline()
        ctx = AgentContext(raw_payload=b"data")
        result = await pipeline.run(ctx)
        assert result is ctx

    async def test_pipeline_accepts_middleware_lists(self) -> None:
        """Pipeline accepts async callables for all four stages."""
        call_count = 0

        async def counting(ctx: AgentContext) -> None:
            nonlocal call_count
            call_count += 1

        pipeline = Pipeline(
            ingress=[counting],
            pre_execution=[counting],
            execution=[counting],
            egress=[counting],
        )
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert call_count == 4


class TestPipelineExecution:
    """Tests for Pipeline.run() behaviour."""

    async def test_empty_pipeline_returns_context(self) -> None:
        """A pipeline with no middlewares returns the same context object unchanged."""
        ctx = AgentContext(raw_payload=b"hello")
        pipeline = Pipeline()
        result = await pipeline.run(ctx)
        assert result is ctx

    async def test_stage_order_is_ingress_pre_exec_exec_egress(self) -> None:
        """All four stages execute in strict ingress->pre_execution->execution->egress order."""
        order: list[str] = []

        async def ingress_mw(ctx: AgentContext) -> None:
            order.append("ingress")

        async def pre_exec_mw(ctx: AgentContext) -> None:
            order.append("pre_execution")

        async def exec_mw(ctx: AgentContext) -> None:
            order.append("execution")

        async def egress_mw(ctx: AgentContext) -> None:
            order.append("egress")

        pipeline = Pipeline(
            ingress=[ingress_mw],
            pre_execution=[pre_exec_mw],
            execution=[exec_mw],
            egress=[egress_mw],
        )
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert order == ["ingress", "pre_execution", "execution", "egress"]

    async def test_ingress_middleware_executed_before_pre_execution(self) -> None:
        """Ingress middlewares run before pre_execution middlewares."""
        order: list[str] = []

        async def ingress_mw(ctx: AgentContext) -> None:
            order.append("ingress")

        async def pre_exec_mw(ctx: AgentContext) -> None:
            order.append("pre_execution")

        pipeline = Pipeline(ingress=[ingress_mw], pre_execution=[pre_exec_mw])
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert order.index("ingress") < order.index("pre_execution")

    async def test_multiple_middlewares_in_same_stage_run_in_order(self) -> None:
        """Multiple middlewares within a stage run in list order."""
        order: list[str] = []

        async def first(ctx: AgentContext) -> None:
            order.append("first")

        async def second(ctx: AgentContext) -> None:
            order.append("second")

        async def third(ctx: AgentContext) -> None:
            order.append("third")

        pipeline = Pipeline(ingress=[first, second, third])
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert order == ["first", "second", "third"]

    async def test_middleware_can_mutate_context(self) -> None:
        """A middleware that sets parsed_ast is visible to subsequent middlewares."""
        seen_ast: list[object] = []

        async def setter(ctx: AgentContext) -> None:
            ctx.parsed_ast = {"tool": "search"}

        async def reader(ctx: AgentContext) -> None:
            seen_ast.append(ctx.parsed_ast)

        pipeline = Pipeline(pre_execution=[setter], execution=[reader])
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert seen_ast == [{"tool": "search"}]

    async def test_middleware_exception_propagates(self) -> None:
        """An exception raised inside a middleware is not swallowed by the pipeline."""

        async def exploding(ctx: AgentContext) -> None:
            raise ValueError("boom")

        pipeline = Pipeline(ingress=[exploding])
        with pytest.raises(ValueError, match="boom"):
            await pipeline.run(AgentContext(raw_payload=b"data"))

    async def test_pipeline_run_returns_the_context(self) -> None:
        """Pipeline.run() returns the AgentContext it received."""
        ctx = AgentContext(raw_payload=b"data")
        result = await Pipeline(ingress=[_noop]).run(ctx)
        assert result is ctx

    async def test_empty_stage_lists_are_skipped_silently(self) -> None:
        """Stages with no middlewares produce no side effects."""
        ctx = AgentContext(raw_payload=b"data")
        pipeline = Pipeline(ingress=[], pre_execution=[], execution=[], egress=[])
        result = await pipeline.run(ctx)
        assert result is ctx
        assert ctx.execution_state is ExecutionState.COMPLETE

    async def test_execution_state_mutation_visible_across_stages(self) -> None:
        """State set in ingress is visible in egress."""
        states_seen: list[ExecutionState] = []

        async def set_running(ctx: AgentContext) -> None:
            ctx.execution_state = ExecutionState.RUNNING

        async def read_state(ctx: AgentContext) -> None:
            states_seen.append(ctx.execution_state)

        pipeline = Pipeline(ingress=[set_running], egress=[read_state])
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert states_seen == [ExecutionState.RUNNING]


class TestExecutionStateTransitions:
    """Tests for Pipeline-managed ExecutionState lifecycle transitions."""

    async def test_execution_state_is_running_during_middleware(self) -> None:
        """context.execution_state is RUNNING while any middleware is executing."""
        states_seen: list[ExecutionState] = []

        async def capture(ctx: AgentContext) -> None:
            states_seen.append(ctx.execution_state)

        pipeline = Pipeline(
            ingress=[capture],
            pre_execution=[capture],
            execution=[capture],
            egress=[capture],
        )
        await pipeline.run(AgentContext(raw_payload=b"data"))
        assert all(s == ExecutionState.RUNNING for s in states_seen)
        assert len(states_seen) == 4

    async def test_execution_state_is_complete_after_successful_run(self) -> None:
        """context.execution_state is COMPLETE after Pipeline.run() returns cleanly."""
        ctx = AgentContext(raw_payload=b"data")
        await Pipeline().run(ctx)
        assert ctx.execution_state == ExecutionState.COMPLETE

    async def test_execution_state_is_pending_before_run(self) -> None:
        """context.execution_state starts as PENDING before Pipeline.run() is called."""
        ctx = AgentContext(raw_payload=b"data")
        assert ctx.execution_state == ExecutionState.PENDING

    async def test_execution_state_halted_preserved_when_middleware_raises(self) -> None:
        """HALTED set by a middleware is not overwritten when the exception propagates."""
        ctx = AgentContext(raw_payload=b"data")

        async def halting(context: AgentContext) -> None:
            context.execution_state = ExecutionState.HALTED
            raise RuntimeError("validator rejected payload")

        pipeline = Pipeline(ingress=[halting])
        with pytest.raises(RuntimeError):
            await pipeline.run(ctx)
        assert ctx.execution_state == ExecutionState.HALTED

    async def test_execution_state_not_complete_when_middleware_raises(self) -> None:
        """If a middleware raises without setting HALTED, state remains RUNNING."""
        ctx = AgentContext(raw_payload=b"data")

        async def exploding(context: AgentContext) -> None:
            raise ValueError("boom")

        pipeline = Pipeline(execution=[exploding])
        with pytest.raises(ValueError):
            await pipeline.run(ctx)
        assert ctx.execution_state == ExecutionState.RUNNING
