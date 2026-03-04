"""Tests for the four-stage middleware Pipeline.

CONSTITUTION Priority 3: TDD RED Phase — these tests must FAIL
before src/argent/pipeline/pipeline.py exists.
"""

import pytest

from argent.pipeline.context import AgentContext, ExecutionState
from argent.pipeline.pipeline import Pipeline


class TestPipelineInstantiation:
    """Tests for Pipeline construction."""

    def test_empty_pipeline_is_valid(self) -> None:
        """Pipeline can be constructed with no middleware in any stage."""
        pipeline = Pipeline()
        assert pipeline is not None

    def test_pipeline_accepts_middleware_lists(self) -> None:
        """Pipeline accepts callables for all four stages."""
        called: list[str] = []

        def noop(ctx: AgentContext) -> None:
            called.append("noop")

        pipeline = Pipeline(
            ingress=[noop],
            pre_execution=[noop],
            execution=[noop],
            egress=[noop],
        )
        assert pipeline is not None


class TestPipelineExecution:
    """Tests for Pipeline.run() behaviour."""

    def test_empty_pipeline_returns_context(self) -> None:
        """A pipeline with no middlewares returns the same context object unchanged."""
        ctx = AgentContext(raw_payload=b"hello")
        pipeline = Pipeline()
        result = pipeline.run(ctx)
        assert result is ctx

    def test_stage_order_is_ingress_pre_exec_exec_egress(self) -> None:
        """All four stages execute in strict ingress → pre_execution → execution → egress order."""
        order: list[str] = []

        def ingress_mw(ctx: AgentContext) -> None:
            order.append("ingress")

        def pre_exec_mw(ctx: AgentContext) -> None:
            order.append("pre_execution")

        def exec_mw(ctx: AgentContext) -> None:
            order.append("execution")

        def egress_mw(ctx: AgentContext) -> None:
            order.append("egress")

        pipeline = Pipeline(
            ingress=[ingress_mw],
            pre_execution=[pre_exec_mw],
            execution=[exec_mw],
            egress=[egress_mw],
        )
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert order == ["ingress", "pre_execution", "execution", "egress"]

    def test_ingress_middleware_executed_before_pre_execution(self) -> None:
        """Ingress middlewares run before pre_execution middlewares."""
        order: list[str] = []

        def ingress_mw(ctx: AgentContext) -> None:
            order.append("ingress")

        def pre_exec_mw(ctx: AgentContext) -> None:
            order.append("pre_execution")

        pipeline = Pipeline(ingress=[ingress_mw], pre_execution=[pre_exec_mw])
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert order.index("ingress") < order.index("pre_execution")

    def test_multiple_middlewares_in_same_stage_run_in_order(self) -> None:
        """Multiple middlewares within a stage run in list order."""
        order: list[str] = []

        def first(ctx: AgentContext) -> None:
            order.append("first")

        def second(ctx: AgentContext) -> None:
            order.append("second")

        def third(ctx: AgentContext) -> None:
            order.append("third")

        pipeline = Pipeline(ingress=[first, second, third])
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert order == ["first", "second", "third"]

    def test_middleware_can_mutate_context(self) -> None:
        """A middleware that sets parsed_ast is visible to subsequent middlewares."""
        seen_ast: list[object] = []

        def setter(ctx: AgentContext) -> None:
            ctx.parsed_ast = {"tool": "search"}

        def reader(ctx: AgentContext) -> None:
            seen_ast.append(ctx.parsed_ast)

        pipeline = Pipeline(pre_execution=[setter], execution=[reader])
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert seen_ast == [{"tool": "search"}]

    def test_middleware_exception_propagates(self) -> None:
        """An exception raised inside a middleware is not swallowed by the pipeline."""

        def exploding(ctx: AgentContext) -> None:
            raise ValueError("boom")

        pipeline = Pipeline(ingress=[exploding])
        with pytest.raises(ValueError, match="boom"):
            pipeline.run(AgentContext(raw_payload=b"data"))

    def test_pipeline_run_returns_the_context(self) -> None:
        """Pipeline.run() returns the AgentContext it received."""
        ctx = AgentContext(raw_payload=b"data")
        result = Pipeline(ingress=[lambda c: None]).run(ctx)
        assert result is ctx

    def test_empty_stage_lists_are_skipped_silently(self) -> None:
        """Stages with no middlewares produce no side effects."""
        ctx = AgentContext(raw_payload=b"data")
        pipeline = Pipeline(ingress=[], pre_execution=[], execution=[], egress=[])
        result = pipeline.run(ctx)
        assert result is ctx
        assert ctx.token_count == 0
        assert ctx.call_count == 0

    def test_execution_state_mutation_visible_across_stages(self) -> None:
        """State set in ingress is visible in egress."""
        states_seen: list[ExecutionState] = []

        def set_running(ctx: AgentContext) -> None:
            ctx.execution_state = ExecutionState.RUNNING

        def read_state(ctx: AgentContext) -> None:
            states_seen.append(ctx.execution_state)

        pipeline = Pipeline(ingress=[set_running], egress=[read_state])
        pipeline.run(AgentContext(raw_payload=b"data"))
        assert states_seen == [ExecutionState.RUNNING]
